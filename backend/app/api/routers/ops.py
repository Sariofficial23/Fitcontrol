"""Operational endpoints for serverless hosting (Vercel).

On Vercel there is no shell, no background worker and no long-running process,
so the jobs that used to run there are exposed as protected HTTP endpoints:

  * ``GET /ops/cron/notifications`` — one notification cycle (called by Vercel
    Cron, which sends ``Authorization: Bearer <CRON_SECRET>``).
  * ``GET /ops/setup?key=<CRON_SECRET>`` — one-time/idempotent setup after a
    deploy: apply DB migrations, register the Telegram webhook and the bot's
    menu button. Safe to call again after every deploy.

Both require ``CRON_SECRET`` (compared in constant time). Without it configured
they are disabled, so they can never be open by accident.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
from pathlib import Path

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger("fitcontrol.ops")

router = APIRouter(prefix="/ops", tags=["ops"], include_in_schema=False)

_BACKEND_DIR = Path(__file__).resolve().parents[3]


def _check_secret(authorization: str | None, key: str | None) -> None:
    expected = settings.cron_secret
    if not expected:
        raise AppError("CRON_SECRET is not configured", code="ops_disabled", status_code=503)
    provided = key or ""
    if authorization and authorization.startswith("Bearer "):
        provided = authorization[len("Bearer "):]
    if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
        raise AppError("Invalid secret", code="unauthorized", status_code=401)


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


@router.get("/cron/notifications")
async def cron_notifications(
    authorization: str | None = Header(default=None),
    key: str | None = Query(default=None),
) -> dict:
    _check_secret(authorization, key)
    from app.bot.notifications import _build_sender, run_due_jobs

    sender = _build_sender()
    try:
        # Vercel Hobby cron fires once a day, so don't wait for the exact hour.
        totals = await run_due_jobs(sender, any_hour=settings.on_vercel)
    finally:
        await sender.close()
    logger.info("Cron notifications: %s", totals)
    return {"ok": True, "sent": totals}


@router.get("/setup")
async def setup(
    authorization: str | None = Header(default=None),
    key: str | None = Query(default=None),
) -> JSONResponse:
    _check_secret(authorization, key)
    steps: dict[str, str] = {}

    try:
        await asyncio.to_thread(_run_migrations)
        steps["migrations"] = "ok"
    except Exception as exc:  # noqa: BLE001 - report every step
        logger.exception("Migrations failed")
        steps["migrations"] = f"error: {exc}"

    if not settings.telegram_bot_token:
        steps["webhook"] = "error: TELEGRAM_BOT_TOKEN is not set"
    elif not settings.public_api_url:
        steps["webhook"] = "error: PUBLIC_API_URL is not set"
    else:
        from aiogram.types import MenuButtonWebApp, WebAppInfo

        from app.bot.main import build_bot

        bot = build_bot()
        try:
            url = settings.public_api_url.rstrip("/") + settings.webhook_path
            await bot.set_webhook(
                url=url,
                secret_token=settings.effective_webhook_secret,
                drop_pending_updates=False,
            )
            steps["webhook"] = f"ok: {url}"
            if settings.webapp_url:
                await bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(
                        text="FitControl", web_app=WebAppInfo(url=settings.webapp_url)
                    )
                )
                steps["menu_button"] = f"ok: {settings.webapp_url}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("Webhook setup failed")
            steps["webhook"] = f"error: {exc}"
        finally:
            await bot.session.close()

    ok = all(v.startswith("ok") for v in steps.values())
    return JSONResponse(status_code=200 if ok else 500, content={"ok": ok, "steps": steps})
