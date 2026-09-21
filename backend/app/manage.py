"""Small management CLI.

Usage:
  python -m app.manage grant-admin <telegram_id>     # make a user platform_admin
  python -m app.manage revoke-admin <telegram_id>
  python -m app.manage list-admins
  python -m app.manage set-webhook                   # register Telegram webhook
  python -m app.manage delete-webhook
  python -m app.manage webhook-info
  python -m app.manage gen-code [days] [--trial] [--tier basic] [--uses 1]
                                                     # issue an activation code
  python -m app.manage list-codes

Notes:
  * platform_admin is the "support" role for account recovery. It is granted
    only here (server-side), never via the API — a Telegram ID can never
    self-escalate.
  * set-webhook uses PUBLIC_API_URL + TELEGRAM_WEBHOOK_SECRET from the env.
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_sessionmaker
from app.models import User


async def _grant_admin(telegram_id: int, value: bool) -> None:
    sm = get_sessionmaker()
    async with sm() as db:
        user = (
            await db.execute(select(User).where(User.telegram_id == telegram_id))
        ).scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, first_name=f"Admin{telegram_id}")
            db.add(user)
        user.is_platform_admin = value
        await db.commit()
        print(f"{'Granted' if value else 'Revoked'} platform_admin for telegram_id={telegram_id}")


async def _list_admins() -> None:
    sm = get_sessionmaker()
    async with sm() as db:
        rows = (
            await db.execute(select(User).where(User.is_platform_admin.is_(True)))
        ).scalars().all()
        if not rows:
            print("No platform admins.")
            return
        for u in rows:
            print(f"  user_id={u.id} telegram_id={u.telegram_id} name={u.first_name}")


async def _set_webhook() -> None:
    from app.bot.main import build_bot

    if not settings.public_api_url:
        raise SystemExit("PUBLIC_API_URL is not set")
    if not settings.telegram_webhook_secret:
        raise SystemExit("TELEGRAM_WEBHOOK_SECRET is not set")
    url = settings.public_api_url.rstrip("/") + settings.webhook_path
    bot = build_bot()
    try:
        await bot.set_webhook(
            url=url,
            secret_token=settings.telegram_webhook_secret,
            drop_pending_updates=True,
        )
        print(f"Webhook set to {url}")
    finally:
        await bot.session.close()


async def _delete_webhook() -> None:
    from app.bot.main import build_bot

    bot = build_bot()
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        print("Webhook deleted.")
    finally:
        await bot.session.close()


async def _webhook_info() -> None:
    from app.bot.main import build_bot

    bot = build_bot()
    try:
        info = await bot.get_webhook_info()
        print(f"url={info.url!r} pending={info.pending_update_count}")
    finally:
        await bot.session.close()


async def _gen_code(days: int, is_trial: bool, tier: str, uses: int) -> None:
    from app.services import activation as activation_svc

    sm = get_sessionmaker()
    async with sm() as db:
        ac = await activation_svc.generate_code(
            db,
            actor_user_id=None,
            plan_tier=tier,
            duration_days=days,
            is_trial=is_trial,
            max_uses=uses,
        )
        await db.commit()
        kind = "TRIAL" if is_trial else "PAID"
        print(f"Activation code: {ac.code}  ({kind}, tier={ac.plan_tier}, {days} days, uses={uses})")


async def _list_codes() -> None:
    from sqlalchemy import select

    from app.models import ActivationCode

    sm = get_sessionmaker()
    async with sm() as db:
        rows = (
            await db.execute(
                select(ActivationCode).order_by(ActivationCode.created_at.desc()).limit(50)
            )
        ).scalars().all()
        if not rows:
            print("No activation codes.")
            return
        for a in rows:
            print(
                f"  {a.code}  tier={a.plan_tier} days={a.duration_days} "
                f"trial={a.is_trial} uses={a.uses_count}/{a.max_uses} status={a.status}"
            )


def _parse_gen_code_args(args: list[str]) -> tuple[int, bool, str, int]:
    days = 30
    is_trial = False
    tier = "basic"
    uses = 1
    i = 0
    positional_used = False
    while i < len(args):
        a = args[i]
        if a == "--trial":
            is_trial = True
        elif a == "--tier":
            tier = args[i + 1]
            i += 1
        elif a == "--uses":
            uses = int(args[i + 1])
            i += 1
        elif not positional_used and a.isdigit():
            days = int(a)
            positional_used = True
        i += 1
    return days, is_trial, tier, uses


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        raise SystemExit(1)
    cmd = args[0]
    if cmd == "gen-code":
        days, is_trial, tier, uses = _parse_gen_code_args(args[1:])
        asyncio.run(_gen_code(days, is_trial, tier, uses))
        return
    if cmd == "list-codes":
        asyncio.run(_list_codes())
        return
    if cmd == "grant-admin":
        asyncio.run(_grant_admin(int(args[1]), True))
    elif cmd == "revoke-admin":
        asyncio.run(_grant_admin(int(args[1]), False))
    elif cmd == "list-admins":
        asyncio.run(_list_admins())
    elif cmd == "set-webhook":
        asyncio.run(_set_webhook())
    elif cmd == "delete-webhook":
        asyncio.run(_delete_webhook())
    elif cmd == "webhook-info":
        asyncio.run(_webhook_info())
    else:
        print(__doc__)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
