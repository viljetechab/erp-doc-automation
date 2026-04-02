"""Customer ORM model — stores ERP customer import data."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Customer(UUIDMixin, TimestampMixin, Base):
    """Customer record imported from ERP System Kundlista export."""

    __tablename__ = "customers"

    # ── Core Identifiers ─────────────────────────────────────────────────
    erp_customer_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)

    # ── Contact Info (denormalized for quick access) ─────────────────────
    email: Mapped[str | None] = mapped_column(String(300), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Address ──────────────────────────────────────────────────────────
    street: Mapped[str | None] = mapped_column(String(300), nullable=True)
    zip_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Meta ─────────────────────────────────────────────────────────────
    default_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
