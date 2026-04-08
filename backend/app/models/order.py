"""Order and OrderLineItem ORM models."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class OrderStatus(str, enum.Enum):
    """Order lifecycle states."""

    EXTRACTED = "extracted"
    EXTRACTION_FAILED = "extraction_failed"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Order(UUIDMixin, TimestampMixin, Base):
    """Represents a parsed purchase order."""

    __tablename__ = "orders"

    # ── Status & Source ──────────────────────────────────────────────────
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False),
        default=OrderStatus.EXTRACTED,
        nullable=False,
        index=True,
    )
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_filepath: Mapped[str] = mapped_column(String(1000), nullable=False)

    # ── Order Header ─────────────────────────────────────────────────────
    order_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order_date: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Buyer ────────────────────────────────────────────────────────────
    buyer_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    buyer_street: Mapped[str | None] = mapped_column(String(300), nullable=True)
    buyer_zip_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    buyer_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    buyer_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    buyer_customer_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # "Vårt kundnr" → BuyerCodeEdi + CustomerInvoiceCode
    supplier_edi_code: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # "Leverantörsnummer" from PDF header
    supplier_name: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )  # Supplier company name from PDF "Postadress" block
    supplier_street: Mapped[str | None] = mapped_column(String(300), nullable=True)
    supplier_zip_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supplier_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    goods_marking: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # "Godsmärke" field

    # ── Delivery Address ─────────────────────────────────────────────────
    delivery_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    delivery_street1: Mapped[str | None] = mapped_column(String(300), nullable=True)
    delivery_street2: Mapped[str | None] = mapped_column(String(300), nullable=True)
    delivery_zip_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    delivery_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_is_buyer_address: Mapped[bool | None] = mapped_column(
        nullable=True, default=None
    )  # True → CompanyAdressFlag=1, False → 0

    # ── Terms ────────────────────────────────────────────────────────────
    delivery_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transport_payer: Mapped[str | None] = mapped_column(String(10), nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(
        String(10), default="SEK", nullable=True
    )

    # ── Extraction Metadata ──────────────────────────────────────────────
    extraction_raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_confidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── XML Output ───────────────────────────────────────────────────────
    generated_xml: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Customer Match ────────────────────────────────────────────────────
    matched_customer_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    customer_match_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
    )  # "matched_exact" | "matched_fuzzy" | "unmatched" | "skipped"
    customer_match_score: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    customer_match_note: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    # ── ERP Push ─────────────────────────────────────────────────────────
    erp_pushed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    erp_push_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # "success" | "failed"

    # ── Ownership ────────────────────────────────────────────────────────
    # Nullable so that pre-existing rows (before this column was added) are
    # not broken.  SET NULL on user deletion preserves the order record.
    uploaded_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    line_items: Mapped[list[OrderLineItem]] = relationship(
        "OrderLineItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderLineItem.row_number",
    )


class OrderLineItem(UUIDMixin, TimestampMixin, Base):
    """A single line item within an order."""

    __tablename__ = "order_line_items"

    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Item Data ────────────────────────────────────────────────────────
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    part_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supplier_part_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delivery_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    reference_number: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── Relationship ─────────────────────────────────────────────────────
    order: Mapped[Order] = relationship("Order", back_populates="line_items")