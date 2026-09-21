"""Activation codes, trials, and the server-side subscription gate."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.enums import ClubSubscriptionStatus, Role
from app.db.session import get_sessionmaker
from app.models import Club
from tests.conftest import ApiUser, seed_club, seed_membership, seed_user

pytestmark = pytest.mark.asyncio


async def _set_subscription(club_id: int, *, status: str, expires_at):
    sm = get_sessionmaker()
    async with sm() as s:
        club = (await s.execute(select(Club).where(Club.id == club_id))).scalar_one()
        club.subscription_status = status
        club.expires_at = expires_at
        await s.commit()


async def _admin(client) -> ApiUser:
    await seed_user(9999, is_platform_admin=True)
    return ApiUser(client, telegram_id=9999)


async def test_trial_code_marks_club_as_trial(client):
    admin = await _admin(client)
    r = await admin.post(
        "/api/v1/platform/activation-codes",
        json={"plan_tier": "trial", "duration_days": 14, "is_trial": True},
    )
    code = r.json()["code"]
    user = ApiUser(client, telegram_id=6001)
    r = await user.post("/api/v1/activation/redeem", json={"code": code, "name": "Trial Gym"})
    assert r.status_code == 201, r.text
    assert r.json()["club"]["subscription_status"] == "trial"


async def test_invalid_code_rejected(client):
    user = ApiUser(client, telegram_id=6002)
    r = await user.post("/api/v1/activation/redeem", json={"code": "FC-NOPE12345", "name": "X"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "code_not_found"


async def test_expired_subscription_blocks_club_endpoints(client):
    # Club with a past expiry: all club data endpoints are blocked server-side.
    owner = await seed_user(6100)
    club = await seed_club("Expired Gym")
    await seed_membership(owner.id, club.id, Role.club_owner)
    await _set_subscription(
        club.id,
        status=ClubSubscriptionStatus.active.value,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    u = ApiUser(client, telegram_id=6100, club_id=club.id)

    r = await u.get("/api/v1/clients")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "subscription_inactive"

    # But the subscription status endpoint stays readable (for the renew screen).
    r = await u.get("/api/v1/subscription/status")
    assert r.status_code == 200
    assert r.json()["status"] == "expired"
    assert r.json()["allowed"] is False


async def test_suspend_and_extend_flow(client):
    owner = await seed_user(6200)
    club = await seed_club("Flow Gym")
    await seed_membership(owner.id, club.id, Role.club_owner)
    # Active with a future expiry -> works.
    await _set_subscription(
        club.id,
        status=ClubSubscriptionStatus.active.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=5),
    )
    u = ApiUser(client, telegram_id=6200, club_id=club.id)
    assert (await u.get("/api/v1/clients")).status_code == 200

    admin = await _admin(client)
    # Suspend -> blocked.
    assert (await admin.post(f"/api/v1/platform/clubs/{club.id}/suspend")).status_code == 200
    assert (await u.get("/api/v1/clients")).status_code == 403

    # Resume -> allowed again.
    assert (await admin.post(f"/api/v1/platform/clubs/{club.id}/resume")).status_code == 200
    assert (await u.get("/api/v1/clients")).status_code == 200

    # Expire it, then extend -> unblocks.
    await _set_subscription(
        club.id,
        status=ClubSubscriptionStatus.active.value,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    assert (await u.get("/api/v1/clients")).status_code == 403
    r = await admin.post(f"/api/v1/platform/clubs/{club.id}/extend", json={"days": 30})
    assert r.status_code == 200
    assert r.json()["days_left"] >= 29
    assert (await u.get("/api/v1/clients")).status_code == 200


async def test_platform_endpoints_require_platform_admin(client):
    # A normal club owner cannot reach platform endpoints.
    owner = await seed_user(6300)
    club = await seed_club("RBAC Gym")
    await seed_membership(owner.id, club.id, Role.club_owner)
    u = ApiUser(client, telegram_id=6300, club_id=club.id)
    assert (await u.get("/api/v1/platform/clubs")).status_code == 403
    assert (
        await u.post("/api/v1/platform/activation-codes", json={"duration_days": 30})
    ).status_code == 403


async def test_platform_admin_can_list_clubs(client):
    owner = await seed_user(6400)
    club = await seed_club("Listed Gym")
    await seed_membership(owner.id, club.id, Role.club_owner)
    admin = await _admin(client)
    r = await admin.get("/api/v1/platform/clubs")
    assert r.status_code == 200
    names = {c["name"] for c in r.json()}
    assert "Listed Gym" in names
