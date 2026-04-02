"""Unit tests for Orders API endpoints.

Covers upload validation, listing, approval lifecycle, and XML downloads.
Ensures correct interaction between routes and services.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

from app.schemas.order import OrderResponse, ERPPushResponse
from app.api.deps import get_order_service, get_pdf_extraction_service, get_xml_generator_service, get_erp_push_service, get_current_user
from app.core.exceptions import AppError, FileValidationError


@pytest.fixture
def mock_order_service(sample_order):
    with patch("app.api.deps.OrderService") as MockService:
        instance = MockService.return_value
        instance.list_orders = AsyncMock(return_value=[(sample_order, 1)])
        instance.get_by_id = AsyncMock(return_value=sample_order)
        instance.update_order = AsyncMock(return_value=sample_order)
        instance.approve_order = AsyncMock(return_value=sample_order)
        instance.reject_order = AsyncMock(return_value=sample_order)
        instance.get_field_confidence = MagicMock(return_value={})
        instance.has_low_confidence = MagicMock(return_value=False)
        instance.record_erp_push = AsyncMock()
        instance.create_from_extraction = AsyncMock(return_value=sample_order)
        yield instance


@pytest.fixture
def mock_extraction_service(sample_extraction_data):
    with patch("app.api.deps.PDFExtractionService") as MockService:
        instance = MockService.return_value
        
        # We need a Pydantic model for extract return
        from app.schemas.extraction import ExtractedOrderData
        extracted = ExtractedOrderData(**sample_extraction_data)
        
        instance.extract = AsyncMock(return_value=extracted)
        yield instance


@pytest.fixture
def override_deps_orders(client, mock_order_service, mock_extraction_service, mock_user):
    app = client.app
    app.dependency_overrides[get_order_service] = lambda: mock_order_service
    app.dependency_overrides[get_pdf_extraction_service] = lambda: mock_extraction_service
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.clear()


def test_upload_pdf_success(client, override_deps_orders):
    # Execute with a dummy file
    dummy_pdf = BytesIO(b"%PDF-1.4...")
    dummy_pdf.name = "test.pdf"
    
    res = client.post(
        "/api/v1/orders/upload",
        files={"file": ("test.pdf", dummy_pdf, "application/pdf")}
    )
    
    assert res.status_code == 201
    assert res.json()["order_number"] == "G73216"


def test_upload_pdf_wrong_type(client, override_deps_orders):
    """Test standard validation preventing non-pdf files from being processed."""
    dummy_txt = BytesIO(b"Hello world")
    
    res = client.post(
        "/api/v1/orders/upload",
        files={"file": ("test.txt", dummy_txt, "text/plain")}
    )
    
    assert res.status_code == 400


def test_list_orders(client, override_deps_orders):
    res = client.get("/api/v1/orders")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["order_number"] == "G73216"


def test_get_order(client, override_deps_orders):
    res = client.get("/api/v1/orders/test-order-id")
    assert res.status_code == 200
    data = res.json()
    assert data["order_number"] == "G73216"
    assert len(data["line_items"]) == 1


def test_update_order(client, override_deps_orders, mock_order_service):
    res = client.patch(
        "/api/v1/orders/test-order-id",
        json={"notes": "Updated note"}
    )
    assert res.status_code == 200
    mock_order_service.update_order.assert_called_once()


def test_approve_order(client, override_deps_orders, mock_order_service):
    with patch("app.api.deps.XMLGeneratorService") as MockXML:
        xml_instance = MockXML.return_value
        xml_instance.generate.return_value = "<xml></xml>"
        client.app.dependency_overrides[get_xml_generator_service] = lambda: xml_instance
        
        res = client.post("/api/v1/orders/test-order-id/approve")
        
        assert res.status_code == 200
        assert res.json()["message"] == "Order approved and XML generated successfully"
        mock_order_service.approve_order.assert_called_once()


def test_download_xml_not_generated(client, override_deps_orders, sample_order):
    sample_order.generated_xml = None
    res = client.get("/api/v1/orders/test-order-id/xml")
    assert res.status_code == 400

def test_download_xml_success(client, override_deps_orders, sample_order):
    sample_order.generated_xml = "<xml>Generated</xml>"
    res = client.get("/api/v1/orders/test-order-id/xml")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/xml"
    assert res.text == "<xml>Generated</xml>"
