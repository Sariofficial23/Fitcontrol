"""Async engine / session factory.

The engine URL comes from settings. Tests override ``DATABASE_URL`` to point at
an isolated SQLite (aiosqlite) database so they never touch production data.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _normalize_async_url(url: str) -> str:
    """Accept the bare ``postgresql://`` URL that hosts like Render hand out and
    upgrade it to the async driver the app requires."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):  # some providers use this scheme
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


# libpq-style query params that asyncpg does not accept as connect() kwargs.
_LIBPQ_ONLY_PARAMS = ("sslmode", "channel_binding")


def _split_asyncpg_url(url: str) -> tuple[str, dict]:
    """Strip libpq-only params (Neon/Vercel URLs carry ``sslmode=require`` and
    ``channel_binding=require``) and translate sslmode into asyncpg's ``ssl``."""
    parsed = make_url(url)
    query = dict(parsed.query)
    connect_args: dict = {}
    sslmode = query.get("sslmode")
    for key in _LIBPQ_ONLY_PARAMS:
        query.pop(key, None)
    if sslmode:
        connect_args["ssl"] = sslmode  # asyncpg accepts libpq sslmode names
    return parsed.set(query=query).render_as_string(hide_password=False), connect_args


def _make_engine(url: str, *, serverless: bool = False) -> AsyncEngine:
    url = _normalize_async_url(url)
    connect_args: dict = {}
    kwargs: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif url.startswith("postgresql+asyncpg"):
        url, connect_args = _split_asyncpg_url(url)
    if serverless and not url.startswith("sqlite"):
        # Each serverless invocation may run on a new event loop and instances
        # are frozen between requests: don't keep pooled connections around.
        # Statement cache off so PgBouncer-style poolers (Neon "-pooler") work.
        kwargs["poolclass"] = NullPool
        connect_args["statement_cache_size"] = 0
    return create_async_engine(
        url, future=True, pool_pre_ping=True, connect_args=connect_args, **kwargs
    )


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _make_engine(settings.database_url, serverless=settings.on_vercel)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
    return _sessionmaker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a session with commit/rollback handling."""
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
