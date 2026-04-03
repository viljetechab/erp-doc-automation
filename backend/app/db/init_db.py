"""Database initialisation — verifies connectivity and schema on startup.

Schema creation and evolution are handled exclusively by Alembic migrations.
This module only performs read-only health checks at application startup:
- Verifies database connectivity
- Logs schema compatibility warnings when tables exist but are missing columns

For local SQLite development, ``create_all`` is still available as a
convenience fallback so ``uvicorn`` works out of the box without running
``alembic upgrade head`` first.
"""

from __future__ import annotations

import structlog
from sqlalchemy import inspect

import app.models  # noqa: F401 — registers all ORM models with Base.metadata
from app.db.session import engine
from app.models.base import Base

logger = structlog.get_logger(__name__)


async def _verify_schema(conn) -> None:
    """Read-only schema health check — logs warnings, never mutates."""

    def _sync_inspect(sync_conn):
        insp = inspect(sync_conn)

        expected_tables = set(Base.metadata.tables.keys())
        for table_name in expected_tables:
            if not insp.has_table(table_name):
                logger.warning(
                    "table_missing",
                    table=table_name,
                    action="Run 'alembic upgrade head' to create the schema.",
                )

    await conn.run_sync(_sync_inspect)


async def init_db() -> None:
    """Initialise the database.

    - PostgreSQL (production/staging): verifies connectivity and logs schema
      warnings.  Schema must be managed via ``alembic upgrade head``.
    - SQLite (local development only): creates tables via ``create_all`` as a
      convenience so developers can start without running Alembic.
    """
    from app.config import get_settings
    settings = get_settings()

    async with engine.begin() as conn:
        if settings.is_sqlite:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("database_initialised_sqlite_dev", env=settings.app_env)
        else:
            await _verify_schema(conn)
            logger.info(
                "database_connected",
                env=settings.app_env,
                message="Schema managed by Alembic. Run 'alembic upgrade head' if tables are missing.",
            )
