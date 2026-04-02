"""Pydantic schemas for customer import and matching."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CustomerImportRow(BaseModel):
    """One row from the Kundlista CSV after parsing."""

    erp_customer_id: str = Field(
        ..., description="Kund column — ERP integer ID as string",
    )
    name: str = Field(..., description="Namn column — company name")
    contact_type: str | None = Field(
        None, description="Typ column: Telefon/Fax/E-post",
    )
    contact_value: str | None = Field(
        None, description="E-post/Tfn.nr column",
    )
    notes: str | None = Field(None, description="Anmärkning column")
    recipient_type: str | None = Field(
        None, description="Mottagare av column",
    )


class CustomerMatchResult(BaseModel):
    """Result of matching an order's buyer fields against the customer DB."""

    status: str = Field(
        ...,
        description="matched_exact | matched_fuzzy | unmatched | skipped",
    )
    customer_id: str | None = Field(
        None,
        description="UUID of matched Customer row (null if unmatched/skipped)",
    )
    erp_customer_id: str | None = Field(
        None, description="ERP customer number (Kund) of matched customer",
    )
    customer_name: str | None = Field(
        None, description="Name of matched customer",
    )
    score: float | None = Field(
        None, description="Similarity score 0.0–1.0 (fuzzy only)",
    )
    note: str | None = Field(
        None, description="Explanation of how match was determined",
    )


class CustomerImportResponse(BaseModel):
    """Response from POST /customers/import."""

    imported: int = Field(
        ..., description="Number of customer records upserted",
    )
    skipped: int = Field(
        ..., description="Number of rows skipped (bad data)",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Any non-fatal errors during import",
    )
