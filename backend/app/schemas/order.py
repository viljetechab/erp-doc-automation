"""Pydantic schemas for Order API request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.order import OrderStatus


class LineItemSchema(BaseModel):
    """Schema for a single order line item (read/write)."""

    id: str | None = None
    row_number: int
    part_number: str | None = None
    supplier_part_number: str | None = None
    description: str | None = None
    additional_text: str | None = None
    quantity: float | None = None
    unit: str | None = None
    delivery_date: str | None = None
    unit_price: float | None = None
    discount: float | None = None
    reference_number: str | None = None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    """Full order response including header and line items."""

    id: str
    status: OrderStatus
    source_filename: str
    order_number: str | None = None
    order_date: str | None = None

    # Buyer
    buyer_name: str | None = None
    buyer_street: str | None = None
    buyer_zip_city: str | None = None
    buyer_country: str | None = None
    buyer_reference: str | None = None
    buyer_customer_number: str | None = None
    supplier_edi_code: str | None = None
    supplier_name: str | None = None
    supplier_street: str | None = None
    supplier_zip_city: str | None = None
    supplier_country: str | None = None
    goods_marking: str | None = None

    # Delivery
    delivery_name: str | None = None
    delivery_street1: str | None = None
    delivery_street2: str | None = None
    delivery_zip_city: str | None = None
    delivery_country: str | None = None
    delivery_is_buyer_address: bool | None = None

    # Terms
    delivery_method: str | None = None
    transport_payer: str | None = None
    payment_terms_days: int | None = None
    currency: str | None = None

    # Line items
    line_items: list[LineItemSchema] = Field(default_factory=list)

    # Customer match
    matched_customer_id: str | None = None
    customer_match_status: str | None = None
    customer_match_score: float | None = None
    customer_match_note: str | None = None

    # Confidence & metadata
    field_confidence: dict[str, float] = Field(default_factory=dict)
    extraction_notes: str | None = None
    extraction_error: str | None = None
    created_at: datetime
    updated_at: datetime

    # ERP push tracking
    erp_pushed_at: datetime | None = None
    erp_push_status: str | None = None

    model_config = {"from_attributes": True}


class OrderListItem(BaseModel):
    """Lightweight order summary for list views."""

    id: str
    status: OrderStatus
    source_filename: str
    order_number: str | None = None
    order_date: str | None = None
    buyer_name: str | None = None
    buyer_reference: str | None = None
    line_item_count: int = 0
    has_low_confidence: bool = False
    customer_match_status: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderUpdateRequest(BaseModel):
    """Fields that can be edited during review."""

    order_number: str | None = None
    order_date: str | None = None
    buyer_name: str | None = None
    buyer_street: str | None = None
    buyer_zip_city: str | None = None
    buyer_country: str | None = None
    buyer_reference: str | None = None
    buyer_customer_number: str | None = None
    supplier_edi_code: str | None = None
    supplier_name: str | None = None
    supplier_street: str | None = None
    supplier_zip_city: str | None = None
    supplier_country: str | None = None
    goods_marking: str | None = None
    delivery_name: str | None = None
    delivery_street1: str | None = None
    delivery_street2: str | None = None
    delivery_zip_city: str | None = None
    delivery_country: str | None = None
    delivery_is_buyer_address: bool | None = None
    delivery_method: str | None = None
    transport_payer: str | None = None
    payment_terms_days: int | None = None
    currency: str | None = None
    line_items: list[LineItemSchema] | None = None


class OrderApproveResponse(BaseModel):
    """Response after approving an order and generating XML."""

    id: str
    status: OrderStatus
    message: str
    xml_download_url: str


class ERPPushResponse(BaseModel):
    """Response after attempting to push an order to ERP System."""

    success: bool
    message: str
    erp_push_status: str  # "success" | "failed"
