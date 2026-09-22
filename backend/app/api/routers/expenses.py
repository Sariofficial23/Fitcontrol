"""Club expenses (owner/admin only) and the expenses-by-category report."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_admin
from app.api.routers.dashboard import _resolve_period
from app.db.session import get_db
from app.models import Expense
from app.schemas import (
    ExpenseCategoryRow,
    ExpenseCreate,
    ExpenseOut,
    ExpenseReportOut,
)
from app.services import expenses as exp_svc

router = APIRouter()


@router.get("/expenses", response_model=list[ExpenseOut], tags=["expenses"])
async def list_expenses(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
    period: str = Query(default="month"),
    start: date | None = None,
    end: date | None = None,
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
) -> list[ExpenseOut]:
    today = date.today()
    p_start, p_end = _resolve_period(period, start, end, today)
    conditions = [
        Expense.club_id == ctx.club_id,
        Expense.is_void.is_(False),
        Expense.spent_at >= p_start,
        Expense.spent_at <= p_end,
    ]
    if category:
        conditions.append(Expense.category == category)
    rows = (
        await db.execute(
            select(Expense)
            .where(*conditions)
            .order_by(Expense.spent_at.desc(), Expense.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [ExpenseOut.model_validate(e) for e in rows]


@router.post("/expenses", response_model=ExpenseOut, status_code=201, tags=["expenses"])
async def create_expense(
    payload: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> ExpenseOut:
    exp = await exp_svc.create_expense(
        db,
        club_id=ctx.club_id,
        amount=payload.amount,
        category=payload.category,
        spent_at=payload.spent_at or date.today(),
        comment=payload.comment,
        actor_user_id=ctx.user.id,
    )
    await db.commit()
    return ExpenseOut.model_validate(exp)


@router.post("/expenses/{expense_id}/void", response_model=ExpenseOut, tags=["expenses"])
async def void_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
) -> ExpenseOut:
    exp = await exp_svc.void_expense(
        db, club_id=ctx.club_id, expense_id=expense_id, actor_user_id=ctx.user.id
    )
    await db.commit()
    return ExpenseOut.model_validate(exp)


@router.get("/reports/expenses", response_model=ExpenseReportOut, tags=["expenses"])
async def report_expenses(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(require_admin),
    period: str = Query(default="month"),
    start: date | None = None,
    end: date | None = None,
) -> ExpenseReportOut:
    today = date.today()
    p_start, p_end = _resolve_period(period, start, end, today)
    total = await exp_svc.total_in_period(db, club_id=ctx.club_id, start=p_start, end=p_end)
    rows = await exp_svc.by_category(db, club_id=ctx.club_id, start=p_start, end=p_end)
    return ExpenseReportOut(
        period_start=p_start,
        period_end=p_end,
        total=total,
        by_category=[ExpenseCategoryRow(category=c, total=t, count=n) for c, t, n in rows],
    )
