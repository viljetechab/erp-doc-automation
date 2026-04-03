"""Async database engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import ssl
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()


def _build_engine_url_and_kwargs() -> tuple[str, dict]:
    """Return (engine_url, kwargs) handling SSL and driver-specific options."""
    raw_url = settings.database_url
    connect_args: dict = {}

    # If sslmode=require present, remove it from the URL and build SSLContext
    if "sslmode=require" in raw_url:
        # parse and remove sslmode from query string
        parts = urlparse(raw_url)
        qs = dict(parse_qsl(parts.query, keep_blank_values=True))
        qs.pop("sslmode", None)
        new_query = urlencode(qs)
        parts = parts._replace(query=new_query)
        engine_url = urlunparse(parts)

        ssl_ctx = ssl.create_default_context()
        connect_args["ssl"] = ssl_ctx
    else:
        engine_url = raw_url

    kwargs: dict = {"echo": settings.app_debug}

    if settings.is_sqlite:
        # SQLite needs the check_same_thread flag for the sync driver used under the hood
        kwargs["connect_args"] = {"check_same_thread": False}
        # merge any connect_args we set above (unlikely for sqlite)
        if connect_args:
            kwargs["connect_args"].update(connect_args)
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
        if connect_args:
            kwargs.setdefault("connect_args", {}).update(connect_args)

    return engine_url, kwargs


engine_url, engine_kwargs = _build_engine_url_and_kwargs()
engine = create_async_engine(engine_url, **engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
