"""Telegram webhook integration for the FastAPI backend (alternative to polling).

Enable by setting ``TELEGRAM_UPDATE_MODE=webhook`` (forced on Vercel). The secret
is ``TELEGRAM_WEBHOOK_SECRET`` or, when unset, one derived from the bot token.
Telegram delivers updates to ``{PUBLIC_API_URL}{API_V1_PREFIX}/telegram/webhook``
and includes the secret in the ``X-Telegram-Bot-Api-Secret-Token`` header, which
we verify in constant time before processing.

The handler always responds 200 quickly (processing errors are logged, not
surfaced) so Telegram does not retry-storm. Register/remove the webhook with
``python -m app.manage set-webhook`` / ``delete-webhook``.
"""
from __future__ import annotations

import hmac
import logging

from aiogram.types import Update
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.bot.main import build_bot, dp
from app.core.config import settings

logger = logging.getLogger("fitcontrol.webhook")

router = APIRouter()

_bot = None


def _get_bot():
    global _bot
    if _bot is None:
        _bot = build_bot()
    return _bot


@router.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> JSONResponse:
    if settings.telegram_update_mode != "webhook":
        return JSONResponse(status_code=404, content={"error": {"code": "webhook_disabled"}})

    secret = settings.effective_webhook_secret
    if not secret or not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, secret
    ):
        return JSONResponse(status_code=403, content={"error": {"code": "bad_secret"}})

    # Serverless runtimes may run each request on a fresh event loop, so a
    # cached Bot (whose HTTP session is bound to the old loop) can't be reused.
    bot = None
    try:
        payload = await request.json()
        update = Update.model_validate(payload)
        bot = build_bot() if settings.on_vercel else _get_bot()
        await dp.feed_update(bot, update)
    except Exception as exc:  # noqa: BLE001 - never make Telegram retry-storm
        logger.warning("Failed to process webhook update: %s", exc)
    finally:
        if settings.on_vercel and bot is not None:
            await bot.session.close()
    # Always 200 so Telegram considers the update delivered.
    return JSONResponse(status_code=200, content={"ok": True})
