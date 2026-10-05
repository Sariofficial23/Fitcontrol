"""Anti-sleep self-ping for free PaaS tiers.

Free hosting tiers (e.g. Render free web services) spin the instance down after
a few minutes without inbound HTTP traffic. The first request after that incurs
a cold start, and a Telegram webhook delivery can be missed entirely.

This background task periodically GETs the app's own ``/health`` endpoint over
its public URL. Because the request travels through the host's router it counts
as inbound traffic and resets the idle timer, keeping the instance warm.

Note: the self-ping only runs while the process is alive, so it cannot wake an
instance that has already been spun down (after a deploy or crash). Pair it with
an external cron (see ``.github/workflows/keepalive.yml``) for full coverage.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("fitcontrol.keepalive")


async def _ping_loop() -> None:
    url = settings.keepalive_url
    interval = max(60, settings.keepalive_interval_seconds)
    logger.info("Keep-alive started: pinging %s every %ss", url, interval)
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            # Sleep first: no need to ping the instant we start up.
            await asyncio.sleep(interval)
            try:
                resp = await client.get(url)
                logger.debug("Keep-alive ping -> %s", resp.status_code)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - best-effort, never crash
                logger.warning("Keep-alive ping failed: %s", exc)


def should_run() -> bool:
    return bool(settings.keepalive_enabled and settings.keepalive_url)


def start(loop_task_holder: list[asyncio.Task]) -> None:
    """Start the ping loop, appending the created task to ``loop_task_holder``."""
    if not should_run():
        if settings.keepalive_enabled and not settings.keepalive_url:
            logger.info("Keep-alive enabled but PUBLIC_API_URL is unset; skipping.")
        return
    loop_task_holder.append(asyncio.create_task(_ping_loop()))
