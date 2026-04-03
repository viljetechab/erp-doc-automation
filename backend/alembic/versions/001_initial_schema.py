"""Initial schema — all tables from ORM models.

Revision ID: 001
Revises: None
Create Date: 2026-04-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(128), nullable=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("auth_provider", sa.String(20), nullable=False, server_default="local"),
        sa.Column("provider_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── refresh_tokens ────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    # ── customers ─────────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("erp_customer_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("email", sa.String(300), nullable=True),
        sa.Column("phone", sa.String(100), nullable=True),
        sa.Column("street", sa.String(300), nullable=True),
        sa.Column("zip_city", sa.String(200), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("default_reference", sa.String(300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_customers_erp_customer_id", "customers", ["erp_customer_id"], unique=True)
    op.create_index("ix_customers_name", "customers", ["name"])

    # ── orders ────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="extracted", index=True),
        sa.Column("source_filename", sa.String(500), nullable=False),
        sa.Column("source_filepath", sa.String(1000), nullable=False),
        sa.Column("order_number", sa.String(100), nullable=True),
        sa.Column("order_date", sa.String(20), nullable=True),
        sa.Column("buyer_name", sa.String(300), nullable=True),
        sa.Column("buyer_street", sa.String(300), nullable=True),
        sa.Column("buyer_zip_city", sa.String(200), nullable=True),
        sa.Column("buyer_country", sa.String(100), nullable=True),
        sa.Column("buyer_reference", sa.String(300), nullable=True),
        sa.Column("buyer_customer_number", sa.String(100), nullable=True),
        sa.Column("supplier_edi_code", sa.String(100), nullable=True),
        sa.Column("supplier_name", sa.String(300), nullable=True),
        sa.Column("supplier_street", sa.String(300), nullable=True),
        sa.Column("supplier_zip_city", sa.String(200), nullable=True),
        sa.Column("supplier_country", sa.String(100), nullable=True),
        sa.Column("goods_marking", sa.String(500), nullable=True),
        sa.Column("delivery_name", sa.String(300), nullable=True),
        sa.Column("delivery_street1", sa.String(300), nullable=True),
        sa.Column("delivery_street2", sa.String(300), nullable=True),
        sa.Column("delivery_zip_city", sa.String(200), nullable=True),
        sa.Column("delivery_country", sa.String(100), nullable=True),
        sa.Column("delivery_is_buyer_address", sa.Boolean(), nullable=True),
        sa.Column("delivery_method", sa.String(100), nullable=True),
        sa.Column("transport_payer", sa.String(10), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True, server_default="SEK"),
        sa.Column("extraction_raw_json", sa.Text(), nullable=True),
        sa.Column("extraction_confidence_json", sa.Text(), nullable=True),
        sa.Column("extraction_notes", sa.Text(), nullable=True),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("generated_xml", sa.Text(), nullable=True),
        sa.Column(
            "matched_customer_id",
            sa.String(36),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("customer_match_status", sa.String(30), nullable=True),
        sa.Column("customer_match_score", sa.Float(), nullable=True),
        sa.Column("customer_match_note", sa.Text(), nullable=True),
        sa.Column("erp_pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("erp_push_status", sa.String(50), nullable=True),
    )
    op.create_index("ix_orders_matched_customer_id", "orders", ["matched_customer_id"])

    # ── order_line_items ──────────────────────────────────────────────────
    op.create_table(
        "order_line_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("part_number", sa.String(200), nullable=True),
        sa.Column("supplier_part_number", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("additional_text", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("delivery_date", sa.String(20), nullable=True),
        sa.Column("unit_price", sa.Float(), nullable=True),
        sa.Column("discount", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("reference_number", sa.String(200), nullable=True),
    )
    op.create_index("ix_order_line_items_order_id", "order_line_items", ["order_id"])

    # ── articles ──────────────────────────────────────────────────────────
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("artikelnummer", sa.String(50), nullable=False),
        sa.Column("artikelbenamning", sa.String(500), nullable=False),
        sa.Column("artikel_typ_id", sa.Integer(), nullable=True),
        sa.Column("standardpris", sa.Numeric(12, 2), nullable=True),
        sa.Column("saldo_varde", sa.Numeric(14, 4), nullable=True),
        sa.Column("saldo_enhet", sa.String(50), nullable=True),
        sa.Column("saldohanteras", sa.Boolean(), nullable=True),
        sa.Column("artikel_kategori_id", sa.Integer(), nullable=True),
        sa.Column("artikel_kod_id", sa.Integer(), nullable=True),
        sa.Column("varugrupp_id", sa.Integer(), nullable=True),
        sa.Column("ursprungsland", sa.String(100), nullable=True),
        sa.Column("artikel_status_id", sa.Integer(), nullable=True),
        sa.Column("nettovikt_varde", sa.Numeric(12, 4), nullable=True),
        sa.Column("nettovikt_enhet", sa.String(50), nullable=True),
        sa.Column("fast_vikt", sa.Boolean(), nullable=True),
        sa.Column("enhet_id", sa.Integer(), nullable=True),
        sa.Column("artikelrevision", sa.String(50), nullable=True),
        sa.Column("ritningsnummer", sa.String(100), nullable=True),
        sa.Column("ritningsrevision", sa.String(50), nullable=True),
        sa.Column("extra_benamning", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_articles_artikelnummer", "articles", ["artikelnummer"], unique=True)


def downgrade() -> None:
    op.drop_table("order_line_items")
    op.drop_table("orders")
    op.drop_table("articles")
    op.drop_table("refresh_tokens")
    op.drop_table("customers")
    op.drop_table("users")
