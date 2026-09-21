"""Platform access control: activation codes + club subscription windows.

Clubs are provisioned only by redeeming an :class:`ActivationCode` (or directly
by a platform_admin). Each club carries a subscription window; when it lapses,
the club is blocked server-side until a platform_admin extends it or the client
redeems a renewal code.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ClubSubscriptionStatus, Role
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationErrorApp
from app.models import ActivationCode, Club, ClubMembership, User
from app.services import clubs as clubs_svc
from app.services.audit import record_audit


@dataclass
class ClubAccess:
    status: str          # effective status: trial|active|expired|suspended
    allowed: bool
    expires_at: datetime | None
    days_left: int | None


def effective_access(club: Club, now: datetime | None = None) -> ClubAccess:
    """Compute a club's effective access. ``expires_at is None`` = unlimited."""
    now = now or datetime.now(timezone.utc)
    if club.subscription_status == ClubSubscriptionStatus.suspended.value:
        return ClubAccess(ClubSubscriptionStatus.suspended.value, False, club.expires_at, None)

    exp = club.expires_at
    if exp is not None:
        # Normalize naive datetimes (SQLite) to UTC for comparison.
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            return ClubAccess(ClubSubscriptionStatus.expired.value, False, club.expires_at, 0)
        days_left = max(0, (exp - now).days)
    else:
        days_left = None

    # Not suspended and not past expiry -> honor stored status (trial/active).
    status = club.subscription_status
    if status not in (ClubSubscriptionStatus.trial.value, ClubSubscriptionStatus.active.value):
        status = ClubSubscriptionStatus.active.value
    return ClubAccess(status, True, club.expires_at, days_left)


def _new_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "FC-" + "".join(secrets.choice(alphabet) for _ in range(10))


async def generate_code(
    db: AsyncSession,
    *,
    actor_user_id: int | None,
    plan_tier: str,
    duration_days: int,
    is_trial: bool,
    max_uses: int = 1,
    valid_days: int | None = None,
    note: str | None = None,
) -> ActivationCode:
    if duration_days <= 0 or duration_days > 3650:
        raise ValidationErrorApp("duration_days must be between 1 and 3650")
    if max_uses <= 0 or max_uses > 1000:
        raise ValidationErrorApp("max_uses must be between 1 and 1000")

    code = _new_code()
    for _ in range(5):
        exists = (
            await db.execute(select(ActivationCode).where(ActivationCode.code == code))
        ).scalar_one_or_none()
        if exists is None:
            break
        code = _new_code()

    valid_until = (
        datetime.now(timezone.utc) + timedelta(days=valid_days) if valid_days else None
    )
    ac = ActivationCode(
        code=code,
        plan_tier=plan_tier or "basic",
        duration_days=duration_days,
        is_trial=is_trial,
        max_uses=max_uses,
        uses_count=0,
        valid_until=valid_until,
        status="active",
        note=note,
        created_by=actor_user_id,
    )
    db.add(ac)
    await db.flush()
    # Audit is club-scoped elsewhere; platform actions have no club, so we skip
    # the club-scoped AuditLog here and rely on created_by + timestamps.
    return ac


async def redeem_code(db: AsyncSession, *, code: str, user: User, club_name: str) -> Club:
    """Redeem an activation code, creating a club owned by ``user``."""
    if not club_name or not club_name.strip():
        raise ValidationErrorApp("Club name is required")

    ac = (
        await db.execute(
            select(ActivationCode).where(ActivationCode.code == code.strip().upper())
        )
    ).scalar_one_or_none()
    if ac is None:
        raise NotFoundError("Activation code not found", code="code_not_found")
    if ac.status != "active":
        raise ConflictError("Activation code is revoked", code="code_revoked")
    if ac.uses_count >= ac.max_uses:
        raise ConflictError("Activation code already used", code="code_used")
    if ac.valid_until is not None:
        vu = ac.valid_until
        if vu.tzinfo is None:
            vu = vu.replace(tzinfo=timezone.utc)
        if vu < datetime.now(timezone.utc):
            raise ConflictError("Activation code has expired", code="code_expired")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=ac.duration_days)
    status = (
        ClubSubscriptionStatus.trial.value
        if ac.is_trial
        else ClubSubscriptionStatus.active.value
    )
    club = await clubs_svc.create_club(
        db,
        owner=user,
        name=club_name,
        subscription_status=status,
        plan_tier=ac.plan_tier,
        expires_at=expires_at,
        activated_at=now,
    )
    ac.uses_count += 1
    await db.flush()
    await record_audit(
        db,
        club_id=club.id,
        actor_user_id=user.id,
        action="activation.redeem",
        entity_type="club",
        entity_id=club.id,
        meta={
            "code": ac.code,
            "plan_tier": ac.plan_tier,
            "is_trial": ac.is_trial,
            "expires_at": expires_at.isoformat(),
        },
    )
    return club


async def _get_club(db: AsyncSession, club_id: int) -> Club:
    club = (await db.execute(select(Club).where(Club.id == club_id))).scalar_one_or_none()
    if club is None:
        raise NotFoundError("Club not found")
    return club


async def extend_club(
    db: AsyncSession, *, actor_user_id: int | None, club_id: int, days: int, plan_tier: str | None = None
) -> Club:
    if days <= 0 or days > 3650:
        raise ValidationErrorApp("days must be between 1 and 3650")
    club = await _get_club(db, club_id)
    now = datetime.now(timezone.utc)
    base = club.expires_at
    if base is not None and base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    # Extend from the later of now / current expiry, so unused days are kept.
    start = base if (base is not None and base > now) else now
    club.expires_at = start + timedelta(days=days)
    club.subscription_status = ClubSubscriptionStatus.active.value
    if plan_tier:
        club.plan_tier = plan_tier
    if club.activated_at is None:
        club.activated_at = now
    await db.flush()
    await record_audit(
        db,
        club_id=club.id,
        actor_user_id=actor_user_id,
        action="subscription.extend",
        entity_type="club",
        entity_id=club.id,
        meta={"days": days, "new_expires_at": club.expires_at.isoformat()},
    )
    return club


async def set_club_status(
    db: AsyncSession, *, actor_user_id: int | None, club_id: int, suspend: bool
) -> Club:
    club = await _get_club(db, club_id)
    if suspend:
        club.subscription_status = ClubSubscriptionStatus.suspended.value
    else:
        # Resume: back to active (or expired if the window already lapsed).
        club.subscription_status = ClubSubscriptionStatus.active.value
    await db.flush()
    await record_audit(
        db,
        club_id=club.id,
        actor_user_id=actor_user_id,
        action="subscription.suspend" if suspend else "subscription.resume",
        entity_type="club",
        entity_id=club.id,
    )
    return club


def assert_platform_admin(user: User) -> None:
    if not user.is_platform_admin:
        raise ForbiddenError("Platform administrator access required", code="not_platform_admin")
