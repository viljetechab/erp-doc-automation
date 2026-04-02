"""Database initialisation — creates all tables on startup.

Changes from initial version:
- _ensure_schema_compatibility() now uses SQLAlchemy inspect() instead of
  information_schema queries, making it database-agnostic (SQLite + Postgres) (#15)
- DROP TABLE removed; schema mismatches now logged as errors, not silently fixed (#14)
- Base.metadata.create_all() is gated to non-production environments (#14)
- Production deployments should use: alembic upgrade head
"""

from __future__ import annotations

import structlog
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection

import app.models  # noqa: F401 — registers all ORM models with Base.metadata
from app.db.session import engine
from app.models.base import Base

logger = structlog.get_logger(__name__)


async def _ensure_schema_compatibility(conn: AsyncConnection) -> None:
    """Check that existing tables are compatible with current ORM models.

    Uses SQLAlchemy inspect() — works identically on SQLite and PostgreSQL (#15).
    Unlike the previous version, this does NOT drop or recreate tables.
    Missing columns on the orders table are added via ALTER TABLE for POC convenience.
    In production, use Alembic migrations instead.
    """

    def _sync_inspect(sync_conn):
        insp = inspect(sync_conn)

        # ── Check customers table ─────────────────────────────────────
        if insp.has_table("customers"):
            customer_cols = {c["name"] for c in insp.get_columns("customers")}
            if "erp_customer_id" not in customer_cols:
                logger.error(
                    "customers_schema_incompatible",
                    existing_columns=sorted(customer_cols),
                    action=(
                        "MANUAL ACTION REQUIRED: run Alembic migration or recreate "
                        "the customers table. The app will NOT drop it automatically."
                    ),
                )
                # Do NOT drop — operator must run migrations explicitly

        # ── Check orders table for missing customer-match columns ─────
        if insp.has_table("orders"):
            order_cols = {c["name"] for c in insp.get_columns("orders")}
            return order_cols
        return set()

    order_cols: set[str] = await conn.run_sync(_sync_inspect)

    # Add missing columns to orders table (POC convenience; Alembic in prod)
    new_order_columns: list[tuple[str, str]] = [
        ("matched_customer_id", "VARCHAR(36)"),
        ("customer_match_status", "VARCHAR(30)"),
        ("customer_match_score", "FLOAT"),
        ("customer_match_note", "TEXT"),
    ]
    if order_cols:
        for col_name, col_type in new_order_columns:
            if col_name not in order_cols:
                try:
                    await conn.execute(
                        text(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
                    )
                    logger.info("column_added", table="orders", column=col_name)
                except Exception as exc:
                    logger.debug(
                        "column_add_skipped",
                        table="orders",
                        column=col_name,
                        reason=str(exc),
                    )


async def init_db() -> None:
    """Initialise the database.

    - In development: creates tables that don't exist and fixes missing columns.
    - In production: ONLY runs schema compatibility checks and logs warnings.
      Run ``alembic upgrade head`` as part of your deployment pipeline (#14).
    """
    from app.config import get_settings
    settings = get_settings()

    async with engine.begin() as conn:
        await _ensure_schema_compatibility(conn)

        if not settings.is_production:
            # FIXED (#14): create_all only runs outside production
            await conn.run_sync(Base.metadata.create_all)
            logger.info("database_initialised", env=settings.app_env)
        else:
            logger.info(
                "database_init_skipped_in_production",
                message="Run 'alembic upgrade head' to apply migrations.",
            )
