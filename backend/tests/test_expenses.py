"""Club expenses + profit reporting."""
from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import ApiUser

pytestmark = pytest.mark.asyncio


async def _seed_paid_client(owner: ApiUser) -> None:
    rc = await owner.post("/api/v1/clients", json={"first_name": "Payer"})
    cid = rc.json()["id"]
    await owner.post("/api/v1/payments", json={"client_id": cid, "amount": 300000})


async def test_create_list_and_void_expense(owner_ctx: ApiUser):
    r = await owner_ctx.post(
        "/api/v1/expenses",
        json={"amount": 50000, "category": "Аренда", "comment": "Сентябрь"},
    )
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    assert r.json()["spent_at"] == date.today().isoformat()

    r = await owner_ctx.get("/api/v1/expenses", params={"period": "month"})
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Void -> disappears from the active list.
    r = await owner_ctx.post(f"/api/v1/expenses/{eid}/void")
    assert r.status_code == 200
    assert r.json()["is_void"] is True
    r = await owner_ctx.get("/api/v1/expenses", params={"period": "month"})
    assert len(r.json()) == 0

    # Double void blocked.
    r = await owner_ctx.post(f"/api/v1/expenses/{eid}/void")
    assert r.status_code == 409


async def test_negative_expense_rejected(owner_ctx: ApiUser):
    r = await owner_ctx.post("/api/v1/expenses", json={"amount": 0, "category": "X"})
    assert r.status_code == 422


async def test_profit_equals_income_minus_expenses(owner_ctx: ApiUser):
    await _seed_paid_client(owner_ctx)  # 300000 income today
    await owner_ctx.post("/api/v1/expenses", json={"amount": 120000, "category": "Зарплата"})

    r = await owner_ctx.get("/api/v1/reports/income", params={"period": "today"})
    body = r.json()
    assert body["total_income"] == 300000
    assert body["total_expenses"] == 120000
    assert body["profit"] == 180000

    r = await owner_ctx.get("/api/v1/reports/expenses", params={"period": "today"})
    rep = r.json()
    assert rep["total"] == 120000
    assert rep["by_category"][0]["category"] == "Зарплата"
    assert rep["by_category"][0]["total"] == 120000


async def test_expenses_require_admin(client):
    from app.core.enums import Role
    from tests.conftest import seed_club, seed_membership, seed_user

    club = await seed_club("Exp Gym")
    trainer = await seed_user(7701)
    await seed_membership(trainer.id, club.id, Role.trainer)
    t = ApiUser(client, telegram_id=7701, club_id=club.id)
    assert (await t.get("/api/v1/expenses")).status_code == 403
    assert (
        await t.post("/api/v1/expenses", json={"amount": 1000, "category": "X"})
    ).status_code == 403
