"""SQLAlchemy model for the ``articles`` table.

Changes from initial version:
- Migrated from legacy Column() / Mapped[] hybrid to consistent
  SQLAlchemy 2.0 mapped_column() with Mapped[] type annotations (#22).
  This eliminates type-checker warnings and ensures correct behaviour
  with asyncio session expire_on_commit semantics.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Article(TimestampMixin, Base):
    """Represents a product article (artiklar) from the ERP catalogue."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artikelnummer: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True,
        doc="Article / part number",
    )
    artikelbenamning: Mapped[str] = mapped_column(
        String(500), nullable=False, doc="Article description",
    )
    artikel_typ_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="FK to artikel_typer",
    )
    standardpris: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, doc="Standard unit price",
    )
    saldo_varde: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True, doc="Stock balance value",
    )
    saldo_enhet: Mapped[str | None] = mapped_column(
        String(50), nullable=True, doc="Stock balance unit",
    )
    saldohanteras: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, doc="Whether stock is managed",
    )
    artikel_kategori_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="FK to artikel_kategorier",
    )
    artikel_kod_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="FK to artikel_koder",
    )
    varugrupp_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="FK to varugrupper",
    )
    ursprungsland: Mapped[str | None] = mapped_column(
        String(100), nullable=True, doc="Country of origin",
    )
    artikel_status_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="FK to artikel_status",
    )
    nettovikt_varde: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True, doc="Net weight value",
    )
    nettovikt_enhet: Mapped[str | None] = mapped_column(
        String(50), nullable=True, doc="Net weight unit",
    )
    fast_vikt: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, doc="Fixed weight flag",
    )
    enhet_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="FK to enheter (units)",
    )
    artikelrevision: Mapped[str | None] = mapped_column(
        String(50), nullable=True, doc="Article revision",
    )
    ritningsnummer: Mapped[str | None] = mapped_column(
        String(100), nullable=True, doc="Drawing number",
    )
    ritningsrevision: Mapped[str | None] = mapped_column(
        String(50), nullable=True, doc="Drawing revision",
    )
    extra_benamning: Mapped[str | None] = mapped_column(
        String(500), nullable=True, doc="Extra description / secondary name",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, doc="Soft-delete flag",
    )

    def __repr__(self) -> str:
        return f"<Article {self.artikelnummer} – {self.artikelbenamning[:40]}>"
