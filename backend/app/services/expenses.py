"""Club expenses: create, void, and period aggregates (for profit reporting)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationErrorApp
from app.models import Expense
from app.services.audit import record_audit


async def create_expense(
    db: AsyncSession,
    *,
    club_id: int,
    amount: int,
    category: str,
    spent_at: date,
    comment: str | None,
    actor_user_id: int | None,
) -> Expense:
    if amount <= 0:
        raise ValidationErrorApp("Expense amount must be greater than 0")
    if not category or not category.strip():
        raise ValidationErrorApp("Expense category is required")
    exp = Expense(
        club_id=club_id,
        amount=amount,
        category=category.strip()[:40],
        spent_at=spent_at,
        comment=comment,
        created_by=actor_user_id,
    )
    db.add(exp)
    await db.flush()
    await record_audit(
        db,
        club_id=club_id,
        actor_user_id=actor_user_id,
        action="expense.create",
        entity_type="expense",
        entity_id=exp.id,
        meta={"amount": amount, "category": exp.category},
    )
    return exp


async def void_expense(
    db: AsyncSession, *, club_id: int, expense_id: int, actor_user_id: int | None
) -> Expense:
    exp = (
        await db.execute(
            select(Expense).where(Expense.id == expense_id, Expense.club_id == club_id)
        )
    ).scalar_one_or_none()
    if exp is None:
        raise NotFoundError("Expense not found")
    if exp.is_void:
        raise ConflictError("Expense is already voided")
    exp.is_void = True
    await db.flush()
    await record_audit(
        db,
        club_id=club_id,
        actor_user_id=actor_user_id,
        action="expense.void",
        entity_type="expense",
        entity_id=exp.id,
        meta={"amount": exp.amount, "category": exp.category},
    )
    return exp


async def total_in_period(db: AsyncSession, *, club_id: int, start: date, end: date) -> int:
    total = (
        await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.club_id == club_id,
                Expense.is_void.is_(False),
                Expense.spent_at >= start,
                Expense.spent_at <= end,
            )
        )
    ).scalar_one()
    return int(total or 0)


async def by_category(
    db: AsyncSession, *, club_id: int, start: date, end: date
) -> list[tuple[str, int, int]]:
    rows = (
        await db.execute(
            select(Expense.category, func.coalesce(func.sum(Expense.amount), 0), func.count(Expense.id))
            .where(
                Expense.club_id == club_id,
                Expense.is_void.is_(False),
                Expense.spent_at >= start,
                Expense.spent_at <= end,
            )
            .group_by(Expense.category)
            .order_by(func.sum(Expense.amount).desc())
        )
    ).all()
    return [(cat, int(total or 0), int(cnt)) for cat, total, cnt in rows]
