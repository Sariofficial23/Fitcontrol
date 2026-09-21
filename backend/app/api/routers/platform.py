"""Platform-owner endpoints (platform_admin only): activation codes and
club subscription control. This is how you provision and bill customers.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_platform_admin
from app.core.enums import Role
from app.db.session import get_db
from app.models import ActivationCode, Club, ClubMembership, User
from app.schemas import (
    ActivationCodeCreate,
    ActivationCodeOut,
    ClubExtendIn,
    PlatformClubOut,
)
from app.services import activation as activation_svc

router = APIRouter(prefix="/platform", tags=["platform"])


@router.post("/activation-codes", response_model=ActivationCodeOut, status_code=201)
async def create_code(
    payload: ActivationCodeCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> ActivationCodeOut:
    ac = await activation_svc.generate_code(
        db,
        actor_user_id=admin.id,
        plan_tier=payload.plan_tier,
        duration_days=payload.duration_days,
        is_trial=payload.is_trial,
        max_uses=payload.max_uses,
        valid_days=payload.valid_days,
        note=payload.note,
    )
    await db.commit()
    return ActivationCodeOut.model_validate(ac)


@router.get("/activation-codes", response_model=list[ActivationCodeOut])
async def list_codes(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> list[ActivationCodeOut]:
    rows = (
        await db.execute(
            select(ActivationCode).order_by(ActivationCode.created_at.desc()).limit(200)
        )
    ).scalars().all()
    return [ActivationCodeOut.model_validate(a) for a in rows]


@router.post("/activation-codes/{code_id}/revoke", response_model=ActivationCodeOut)
async def revoke_code(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> ActivationCodeOut:
    ac = (
        await db.execute(select(ActivationCode).where(ActivationCode.id == code_id))
    ).scalar_one_or_none()
    if ac is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Activation code not found")
    ac.status = "revoked"
    await db.commit()
    return ActivationCodeOut.model_validate(ac)


async def _owner_telegram_id(db: AsyncSession, club_id: int) -> int | None:
    row = (
        await db.execute(
            select(User.telegram_id)
            .join(ClubMembership, ClubMembership.user_id == User.id)
            .where(
                ClubMembership.club_id == club_id,
                ClubMembership.role == Role.club_owner.value,
                ClubMembership.is_active.is_(True),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return int(row) if row is not None else None


@router.get("/clubs", response_model=list[PlatformClubOut])
async def list_clubs(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> list[PlatformClubOut]:
    clubs = (
        await db.execute(select(Club).order_by(Club.created_at.desc()))
    ).scalars().all()
    out: list[PlatformClubOut] = []
    for c in clubs:
        access = activation_svc.effective_access(c)
        out.append(
            PlatformClubOut(
                id=c.id,
                name=c.name,
                subscription_status=access.status,
                plan_tier=c.plan_tier,
                expires_at=c.expires_at,
                days_left=access.days_left,
                owner_telegram_id=await _owner_telegram_id(db, c.id),
                created_at=c.created_at,
            )
        )
    return out


@router.post("/clubs/{club_id}/extend", response_model=PlatformClubOut)
async def extend_club(
    club_id: int,
    payload: ClubExtendIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> PlatformClubOut:
    club = await activation_svc.extend_club(
        db, actor_user_id=admin.id, club_id=club_id, days=payload.days, plan_tier=payload.plan_tier
    )
    await db.commit()
    access = activation_svc.effective_access(club)
    return PlatformClubOut(
        id=club.id,
        name=club.name,
        subscription_status=access.status,
        plan_tier=club.plan_tier,
        expires_at=club.expires_at,
        days_left=access.days_left,
        owner_telegram_id=await _owner_telegram_id(db, club.id),
        created_at=club.created_at,
    )


@router.post("/clubs/{club_id}/suspend", response_model=PlatformClubOut)
async def suspend_club(
    club_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> PlatformClubOut:
    return await _set_status(db, admin, club_id, suspend=True)


@router.post("/clubs/{club_id}/resume", response_model=PlatformClubOut)
async def resume_club(
    club_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> PlatformClubOut:
    return await _set_status(db, admin, club_id, suspend=False)


async def _set_status(db: AsyncSession, admin: User, club_id: int, *, suspend: bool) -> PlatformClubOut:
    club = await activation_svc.set_club_status(
        db, actor_user_id=admin.id, club_id=club_id, suspend=suspend
    )
    await db.commit()
    access = activation_svc.effective_access(club)
    return PlatformClubOut(
        id=club.id,
        name=club.name,
        subscription_status=access.status,
        plan_tier=club.plan_tier,
        expires_at=club.expires_at,
        days_left=access.days_left,
        owner_telegram_id=await _owner_telegram_id(db, club.id),
        created_at=club.created_at,
    )
