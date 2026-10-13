"""Vercel (serverless) support: settings defaults, DB URL handling, ops endpoints."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.bot.notifications import LoggingSender, run_daily_summary
from app.core.config import Settings, settings
from app.core.enums import Role
from app.db.session import _split_asyncpg_url, get_sessionmaker
from app.models import Club
from tests.conftest import seed_club, seed_membership, seed_user


def test_vercel_defaults_from_project_url():
    s = Settings(
        vercel="1",
        vercel_project_production_url="fitcontrol-x.vercel.app",
        telegram_update_mode="polling",
        keepalive_enabled=True,
        environment="development",
        cors_origins="*",
    )
    assert s.on_vercel
    assert s.telegram_update_mode == "webhook"
    assert s.keepalive_enabled is False
    assert s.is_production
    assert s.public_api_url == "https://fitcontrol-x.vercel.app"
    assert s.webapp_url == "https://fitcontrol-x.vercel.app"
    assert s.cors_origins_list == ["https://fitcontrol-x.vercel.app"]


def test_explicit_urls_win_on_vercel():
    s = Settings(
        vercel="1",
        vercel_project_production_url="a.vercel.app",
        public_api_url="https://api.example.com",
        webapp_url="https://app.example.com",
    )
    assert s.public_api_url == "https://api.example.com"
    assert s.webapp_url == "https://app.example.com"


def test_not_on_vercel_keeps_settings():
    s = Settings(vercel="", telegram_update_mode="polling", environment="development")
    assert not s.on_vercel
    assert s.telegram_update_mode == "polling"
    assert not s.is_production


def test_webhook_secret_derived_from_token():
    a = Settings(telegram_bot_token="123:abc", telegram_webhook_secret="")
    b = Settings(telegram_bot_token="123:abc", telegram_webhook_secret="")
    c = Settings(telegram_bot_token="456:def", telegram_webhook_secret="")
    assert a.effective_webhook_secret == b.effective_webhook_secret
    assert a.effective_webhook_secret != c.effective_webhook_secret
    assert len(a.effective_webhook_secret) == 64
    assert Settings(telegram_bot_token="", telegram_webhook_secret="").effective_webhook_secret == ""
    explicit = Settings(telegram_bot_token="123:abc", telegram_webhook_secret="mine")
    assert explicit.effective_webhook_secret == "mine"


def test_neon_url_params_translated_for_asyncpg():
    url, args = _split_asyncpg_url(
        "postgresql+asyncpg://u:p@ep-x-pooler.neon.tech/db?sslmode=require&channel_binding=require"
    )
    assert "sslmode" not in url and "channel_binding" not in url
    assert url.startswith("postgresql+asyncpg://u:p@ep-x-pooler.neon.tech/db")
    assert args == {"ssl": "require"}

    url, args = _split_asyncpg_url("postgresql+asyncpg://u:p@localhost/db")
    assert args == {}


@pytest.mark.asyncio
async def test_ops_disabled_without_cron_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", "")
    r = await client.get("/api/v1/ops/cron/notifications")
    assert r.status_code == 503
    r = await client.get("/api/v1/ops/setup", params={"key": "anything"})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_ops_rejects_bad_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", "s3cret-value-1234567890")
    r = await client.get("/api/v1/ops/cron/notifications")
    assert r.status_code == 401
    r = await client.get(
        "/api/v1/ops/cron/notifications", headers={"Authorization": "Bearer wrong"}
    )
    assert r.status_code == 401
    r = await client.get("/api/v1/ops/setup", params={"key": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_cron_runs_with_bearer_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "cron_secret", "s3cret-value-1234567890")
    monkeypatch.setattr(settings, "telegram_bot_token", "")  # LoggingSender, no network
    r = await client.get(
        "/api/v1/ops/cron/notifications",
        headers={"Authorization": "Bearer s3cret-value-1234567890"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert set(body["sent"]) == {"expiry", "overdue", "daily_summary"}


@pytest.mark.asyncio
async def test_daily_summary_any_hour():
    club = await seed_club("Hourless Gym")
    owner = await seed_user(8101)
    await seed_membership(owner.id, club.id, Role.club_owner)
    sender = LoggingSender()
    sm = get_sessionmaker()
    # 03:00 UTC = 08:00 in Tashkent: not the configured summary hour (9).
    now = datetime(2026, 1, 15, 3, 0, tzinfo=ZoneInfo("UTC"))
    async with sm() as db:
        c = await db.get(Club, club.id)
        assert await run_daily_summary(db, sender, c, now) == 0
        assert await run_daily_summary(db, sender, c, now, any_hour=True) == 1
        # De-duplicated for the rest of the day.
        assert await run_daily_summary(db, sender, c, now, any_hour=True) == 0
