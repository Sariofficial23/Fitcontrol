"""Activation (redeem a code to create a club) and subscription status.

These endpoints are intentionally NOT behind the subscription gate: redeeming a
code and reading the current status must work for a brand-new or expired club.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth, get_current_user, require_club
from app.core.enums import Role
from app.db.session import get_db
from app.models import User
from app.schemas import (
    ActivationRedeemIn,
    ClubMembershipOut,
    ClubOut,
    SubscriptionStatusOut,
)
from app.services import activation as activation_svc

router = APIRouter()


@router.post("/activation/redeem", response_model=ClubMembershipOut, status_code=201, tags=["activation"])
async def redeem(
    payload: ActivationRedeemIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClubMembershipOut:
    """Redeem an activation code and create the club (caller becomes owner)."""
    club = await activation_svc.redeem_code(
        db, code=payload.code, user=user, club_name=payload.name
    )
    await db.commit()
    await db.refresh(club)
    return ClubMembershipOut(club=ClubOut.model_validate(club), role=Role.club_owner)


@router.get("/subscription/status", response_model=SubscriptionStatusOut, tags=["activation"])
async def subscription_status(
    ctx: AuthContext = Depends(get_auth),
) -> SubscriptionStatusOut:
    """Effective subscription status of the active club (works even if expired,
    so the Mini App can render a 'renew access' screen)."""
    require_club(ctx)
    access = activation_svc.effective_access(ctx.club)
    return SubscriptionStatusOut(
        club_id=ctx.club.id,
        status=access.status,
        allowed=access.allowed,
        expires_at=access.expires_at,
        days_left=access.days_left,
    )
