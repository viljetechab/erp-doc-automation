"""Tests for PDF extraction schema validation."""

from __future__ import annotations

import pytest

from app.schemas.extraction import ExtractedOrderData, ExtractedLineItem


class TestExtractedOrderData:
    """Tests for the extraction Pydantic schema (validates GPT-4o output)."""

    def test_valid_full_extraction(self, sample_extraction_data: dict) -> None:
        """Should parse a complete extraction result without errors."""
        result = ExtractedOrderData.model_validate(sample_extraction_data)
        assert result.order_number == "G73216"
        assert result.buyer_name == "Careco Inredningar AB"
        assert len(result.line_items) == 2

    def test_minimal_extraction(self) -> None:
        """Should accept minimal data with only required fields."""
        data = {
            "line_items": [
                {
                    "row_number": 10,
                    "description": "Test item",
                    "quantity": 1.0,
                }
            ]
        }
        result = ExtractedOrderData.model_validate(data)
        assert result.order_number is None
        assert len(result.line_items) == 1

    def test_empty_line_items_allowed(self) -> None:
        """Should allow an extraction with no line items."""
        data = {"order_number": "TEST-001"}
        result = ExtractedOrderData.model_validate(data)
        assert result.line_items == []

    def test_negative_quantity_rejected(self) -> None:
        """Should reject negative quantities."""
        data = {
            "line_items": [
                {
                    "row_number": 10,
                    "description": "Bad item",
                    "quantity": -5.0,
                }
            ]
        }
        with pytest.raises(Exception):
            ExtractedOrderData.model_validate(data)

    def test_default_currency(self) -> None:
        """Currency should default to SEK."""
        result = ExtractedOrderData.model_validate({})
        assert result.currency == "SEK"

    def test_line_item_default_unit(self) -> None:
        """Unit should default to ST."""
        item = ExtractedLineItem(row_number=10, description="test", quantity=1.0)
        assert item.unit == "ST"

    def test_swedish_price_handling(self, sample_extraction_data: dict) -> None:
        """Prices should be stored as floats (comma→dot conversion done by GPT)."""
        result = ExtractedOrderData.model_validate(sample_extraction_data)
        assert result.line_items[0].unit_price == 372.97
        assert result.line_items[0].discount_percent == -11.34
