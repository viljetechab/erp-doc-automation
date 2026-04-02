"""Pydantic schema for the GPT-4o extraction response.

This schema defines the structure we instruct GPT-4o to return.
Pydantic validation ensures we catch malformed AI responses early.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedLineItem(BaseModel):
    """A single line item extracted from the PDF order."""

    row_number: int = Field(..., description="Sequential row number (10, 20, 30, ...)")
    part_number: str | None = Field(None, description="Buyer's article/part number")
    supplier_part_number: str | None = Field(
        None, description="Supplier's own part number"
    )
    description: str = Field(..., description="Main item description text")
    additional_text: str | None = Field(
        None, description="Extra specs: dekor, dimensions, color codes"
    )
    quantity: float = Field(..., ge=0, description="Order quantity")
    unit: str = Field(default="ST", description="Unit of measure (ST, M2, etc.)")
    delivery_date: str | None = Field(
        None, description="Requested delivery date (YYYY-MM-DD)"
    )
    unit_price: float | None = Field(None, ge=0, description="Price per unit")
    discount_percent: float | None = Field(
        None, description="Discount percentage (negative = discount)"
    )
    reference_number: str | None = Field(
        None, description="Line-level reference number"
    )


class ExtractedOrderData(BaseModel):
    """Complete structured data extracted from a PDF purchase order.

    This maps to the fields needed for the Monitor ORDERS420 XML schema.
    """

    # ── Order Header ─────────────────────────────────────────────────────
    order_number: str | None = Field(
        None, description="Purchase order number / reference"
    )
    order_date: str | None = Field(None, description="Order date (YYYY-MM-DD)")

    # ── Buyer ────────────────────────────────────────────────────────────
    buyer_name: str | None = Field(None, description="Buying company name")
    buyer_street: str | None = Field(None, description="Buyer street address")
    buyer_zip_city: str | None = Field(None, description="Buyer postal code and city")
    buyer_country: str | None = Field(None, description="Buyer country")
    buyer_reference: str | None = Field(
        None, description="Contact person / buyer reference ('Vår referens')"
    )
    buyer_customer_number: str | None = Field(
        None,
        description="'Vårt kundnr' field — the buyer's customer number at the supplier",
    )
    supplier_edi_code: str | None = Field(
        None,
        description="'Leverantörsnummer' field — the supplier's EDI/vendor code",
    )
    supplier_name: str | None = Field(
        None,
        description=(
            "Supplier/vendor company name from 'Postadress' block on "
            "RIGHT side of PO header (the company RECEIVING the order)"
        ),
    )
    supplier_street: str | None = Field(
        None, description="Supplier street address from 'Postadress' block"
    )
    supplier_zip_city: str | None = Field(
        None, description="Supplier postal code and city from 'Postadress' block"
    )
    supplier_country: str | None = Field(
        None, description="Supplier country, default 'Sverige'"
    )
    goods_marking: str | None = Field(
        None, description="'Godsmärke' field — goods marking/labeling text"
    )

    # ── Delivery Address ─────────────────────────────────────────────────
    delivery_name: str | None = Field(
        None, description="Delivery recipient company name"
    )
    delivery_street1: str | None = Field(None, description="Delivery address line 1")
    delivery_street2: str | None = Field(None, description="Delivery address line 2")
    delivery_zip_city: str | None = Field(
        None, description="Delivery postal code and city"
    )
    delivery_country: str | None = Field(None, description="Delivery country")
    delivery_is_buyer_address: bool | None = Field(
        None,
        description=(
            "True if the delivery company name matches the buyer company name "
            "(internal delivery / CompanyAdressFlag=1). False if it's a third party."
        ),
    )

    # ── Terms ────────────────────────────────────────────────────────────
    delivery_method: str | None = Field(None, description="Delivery method (e.g. Bil)")
    transport_payer: str | None = Field(
        None, description="Transport payer code (e.g. C)"
    )
    payment_terms_days: int | None = Field(None, description="Payment terms in days")
    currency: str = Field(default="SEK", description="Order currency")

    # ── Header-level Delivery Date ──────────────────────────────────────
    delivery_date: str | None = Field(
        None,
        description=(
            "Overall requested delivery date for the entire order (YYYY-MM-DD). "
            "If only line-level dates exist, this can be null."
        ),
    )

    # ── Line Items ───────────────────────────────────────────────────────
    line_items: list[ExtractedLineItem] = Field(
        default_factory=list, description="Order line items"
    )

    # ── Confidence Scoring ───────────────────────────────────────────────
    field_confidence: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Confidence scores (0.0–1.0) for each extracted field. "
            "Fields the AI is uncertain about will have scores < 0.8."
        ),
    )

    # ── Metadata ─────────────────────────────────────────────────────────
    extraction_notes: str | None = Field(
        None, description="Any notes or warnings from extraction"
    )
