"""Shared test fixtures for the Pro test suite."""

from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import Settings
from app.models.user import User
from app.models.order import Order, OrderLineItem
from app.api.deps import get_settings, get_db, get_current_user

# --- App configuration ---

@pytest.fixture
def mock_settings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret_key="test-secret-key-that-is-long-enough-for-validation",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=7,
        microsoft_client_id="m_id",
        microsoft_client_secret="m_secret",
        microsoft_tenant_id="m_tenant",
        openai_api_key="test-key",
        openai_model="gpt-4o",
        openai_max_tokens=4000,
        monitor_erp_base_url="http://erp",
        monitor_erp_api_key="erp-key",
        upload_dir=str(tmp_path / "uploads"),
        max_upload_size_mb=1,
        supplier_name="Test Supplier",
        supplier_edi_code="1234",
        supplier_street="123 Test St",
        supplier_zip_city="12345 Test City",
        supplier_country="Demo Country",
        cors_origins=["http://localhost:5173"],
    )

@pytest.fixture
def override_deps(mock_settings):
    app.dependency_overrides[get_settings] = lambda: mock_settings
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client(override_deps) -> TestClient:
    return TestClient(app)

@pytest.fixture
def mock_user() -> User:
    user = User(
        email="test@example.com",
        display_name="Test User",
        auth_provider="local",
        is_active=True
    )
    user.id = "test-user-id"
    user.created_at = datetime.utcnow()
    return user

@pytest.fixture
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture
def auth_client(client, override_auth) -> TestClient:
    return client

# --- Sample Data ---

@pytest.fixture
def sample_extraction_data() -> dict:
    """Returns a sample extraction result matching the G73216 test PDF."""
    return {
        "order_number": "G73216",
        "order_date": "2026-02-05",
        "buyer_name": "Careco Inredningar AB",
        "buyer_street": "Box 95",
        "buyer_zip_city": "283 22 OSBY",
        "buyer_country": "Demo Country",
        "buyer_reference": "Marina Thorsén",
        "buyer_customer_number": "1792",
        "supplier_name": "Demo Supplier Ltd",
        "supplier_edi_code": "DL123",
        "supplier_street": "DL Street",
        "supplier_zip_city": "DL City",
        "supplier_country": "Demo Country",
        "goods_marking": "Pallet 1",
        "delivery_name": "Careco Inredningar AB",
        "delivery_street1": "LAS Interör AB",
        "delivery_street2": "Ågatan 5",
        "delivery_zip_city": "646 30 Gnesta",
        "delivery_country": "Demo Country",
        "delivery_method": "Bil",
        "transport_payer": "C",
        "payment_terms_days": 30,
        "currency": "SEK",
        "line_items": [
            {
                "row_number": 10,
                "part_number": "101928002070DL",
                "supplier_part_number": "HA0413",
                "description": "Sample Panel Oak 19mm",
                "additional_text": "Dekor W980 ST2 Platinum White\n2800;2070\nNCS 0502-g50y",
                "quantity": 96.00,
                "unit": "ST",
                "delivery_date": "2026-02-17",
                "unit_price": 372.97,
                "discount_percent": -11.34,
                "reference_number": None,
            }
        ],
        "extraction_notes": None,
    }

@pytest.fixture
def sample_order(sample_extraction_data) -> Order:
    order = Order(
        id="test-order-id",
        source_filename="test.pdf",
        source_filepath="/tmp/test.pdf",
        order_number=sample_extraction_data["order_number"],
        order_date=sample_extraction_data["order_date"],
        buyer_name=sample_extraction_data["buyer_name"],
        buyer_street=sample_extraction_data["buyer_street"],
        buyer_zip_city=sample_extraction_data["buyer_zip_city"],
        buyer_country=sample_extraction_data["buyer_country"],
        buyer_reference=sample_extraction_data["buyer_reference"],
        buyer_customer_number=sample_extraction_data["buyer_customer_number"],
        supplier_name=sample_extraction_data["supplier_name"],
        supplier_edi_code=sample_extraction_data["supplier_edi_code"],
        supplier_street=sample_extraction_data["supplier_street"],
        supplier_zip_city=sample_extraction_data["supplier_zip_city"],
        supplier_country=sample_extraction_data["supplier_country"],
        goods_marking=sample_extraction_data["goods_marking"],
        delivery_name=sample_extraction_data["delivery_name"],
        delivery_street1=sample_extraction_data["delivery_street1"],
        delivery_street2=sample_extraction_data["delivery_street2"],
        delivery_zip_city=sample_extraction_data["delivery_zip_city"],
        delivery_country=sample_extraction_data["delivery_country"],
        delivery_method=sample_extraction_data["delivery_method"],
        transport_payer=sample_extraction_data["transport_payer"],
        payment_terms_days=sample_extraction_data["payment_terms_days"],
        currency=sample_extraction_data["currency"],
        delivery_is_buyer_address=False,
    )
    
    order.line_items = [
        OrderLineItem(
            order_id="test-order-id",
            row_number=li["row_number"],
            part_number=li["part_number"],
            supplier_part_number=li["supplier_part_number"],
            description=li["description"],
            additional_text=li["additional_text"],
            quantity=li["quantity"],
            unit=li["unit"],
            delivery_date=li["delivery_date"],
            unit_price=li["unit_price"],
            discount=li.get("discount_percent") or li.get("discount", 0.0),
            reference_number=li["reference_number"]
        ) for li in sample_extraction_data["line_items"]
    ]
    return order
