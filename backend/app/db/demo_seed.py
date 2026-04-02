"""
Demo seed data for client demonstrations.

ALL data here is entirely fictional. No real companies, addresses, or
customer numbers are used. Safe to run in any demo environment.

Usage:
    cd backend
    python -m app.db.demo_seed

Creates:
  - 1 demo admin user (email/password login — no OAuth needed)
  - 6 fictional demo customers
  - 3 fictional demo orders in different states
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.init_db import init_db
from app.models.customer import Customer
from app.models.order import Order, LineItem, OrderStatus
from app.models.user import User

logger = structlog.get_logger(__name__)

# ── Demo Login Credentials ────────────────────────────────────────────────────

DEMO_EMAIL = "demo@orderflowpro.example"
DEMO_PASSWORD = "Demo1234!"
DEMO_DISPLAY_NAME = "Demo Admin"

# ── Fictional Demo Customers ──────────────────────────────────────────────────

DEMO_CUSTOMERS = [
    {
        "erp_customer_id": "DEMO-001",
        "name": "Nordicwood Interiors AB",
        "street": "Maple Lane 12",
        "zip_city": "10001 DEMO CITY",
        "country": "Demo Country",
        "email": "orders@nordicwood.example",
        "phone": "+00 700 000 001",
    },
    {
        "erp_customer_id": "DEMO-002",
        "name": "Bergström Building Solutions",
        "street": "Oak Street 45",
        "zip_city": "10002 DEMO CITY",
        "country": "Demo Country",
        "email": "procurement@bergstrom.example",
        "phone": "+00 700 000 002",
    },
    {
        "erp_customer_id": "DEMO-003",
        "name": "Lindqvist Interior Design",
        "street": "Elm Avenue 8",
        "zip_city": "10003 DEMO CITY",
        "country": "Demo Country",
        "email": "hello@lindqvist-design.example",
        "phone": "+00 700 000 003",
    },
    {
        "erp_customer_id": "DEMO-004",
        "name": "Stellarcraft Furniture Co.",
        "street": "Pine Boulevard 99",
        "zip_city": "10004 DEMO CITY",
        "country": "Demo Country",
        "email": "buying@stellarcraft.example",
        "phone": "+00 700 000 004",
    },
    {
        "erp_customer_id": "DEMO-005",
        "name": "Greenleaf Construction Group",
        "street": "Cedar Road 3",
        "zip_city": "10005 DEMO CITY",
        "country": "Demo Country",
        "email": "orders@greenleaf-group.example",
        "phone": "+00 700 000 005",
    },
    {
        "erp_customer_id": "DEMO-006",
        "name": "Apex Renovation Services",
        "street": "Birch Close 22",
        "zip_city": "10006 DEMO CITY",
        "country": "Demo Country",
        "email": "purchasing@apex-reno.example",
        "phone": "+00 700 000 006",
    },
]

# ── Fictional Demo Orders ─────────────────────────────────────────────────────

DEMO_ORDERS = [
    {
        "order_number": "DEMO-PO-2024-001",
        "order_date": date(2024, 3, 1),
        "status": OrderStatus.APPROVED,
        "source_filename": "demo-order-DEMO-PO-2024-001.pdf",
        "source_filepath": "/uploads/demo/order-DEMO-PO-2024-001.pdf",
        "buyer_name": "Nordicwood Interiors AB",
        "buyer_street": "Maple Lane 12",
        "buyer_zip_city": "10001 DEMO CITY",
        "buyer_country": "Demo Country",
        "buyer_reference": "Jane Demo",
        "buyer_customer_number": "DEMO-001",
        "supplier_name": "Demo Supplier Ltd",
        "supplier_edi_code": "0000000",
        "supplier_street": "1 Business Street",
        "supplier_zip_city": "00000 DEMO CITY",
        "supplier_country": "Demo Country",
        "delivery_name": "Nordicwood Interiors AB",
        "delivery_street1": "Maple Lane 12",
        "delivery_zip_city": "10001 DEMO CITY",
        "delivery_country": "Demo Country",
        "delivery_is_buyer_address": True,
        "delivery_method": "Standard Freight",
        "payment_terms_days": 30,
        "currency": "USD",
        "delivery_date": date(2024, 3, 20),
        "line_items": [
            {
                "row_number": 10,
                "part_number": "NW-1001",
                "supplier_part_number": "SP-A100",
                "description": "Premium Oak Panel 19mm",
                "additional_text": "Finish: Natural\n2800x2070",
                "quantity": 50.0,
                "unit": "PCS",
                "delivery_date": date(2024, 3, 20),
            },
            {
                "row_number": 20,
                "part_number": "NW-1002",
                "supplier_part_number": "SP-B200",
                "description": "Birch Veneer Sheet 12mm",
                "additional_text": "Finish: Lacquered White\n2440x1220",
                "quantity": 120.0,
                "unit": "PCS",
                "delivery_date": date(2024, 3, 20),
            },
        ],
    },
    {
        "order_number": "DEMO-PO-2024-002",
        "order_date": date(2024, 3, 5),
        "status": OrderStatus.IN_REVIEW,
        "source_filename": "demo-order-DEMO-PO-2024-002.pdf",
        "source_filepath": "/uploads/demo/order-DEMO-PO-2024-002.pdf",
        "buyer_name": "Bergström Building Solutions",
        "buyer_street": "Oak Street 45",
        "buyer_zip_city": "10002 DEMO CITY",
        "buyer_country": "Demo Country",
        "buyer_reference": "Karl Demo",
        "buyer_customer_number": "DEMO-002",
        "supplier_name": "Demo Supplier Ltd",
        "supplier_edi_code": "0000000",
        "supplier_street": "1 Business Street",
        "supplier_zip_city": "00000 DEMO CITY",
        "supplier_country": "Demo Country",
        "delivery_name": "Bergström Site Office",
        "delivery_street1": "Construction Ave 77",
        "delivery_zip_city": "10099 BUILD CITY",
        "delivery_country": "Demo Country",
        "delivery_is_buyer_address": False,
        "delivery_method": "Express Courier",
        "payment_terms_days": 14,
        "currency": "USD",
        "delivery_date": date(2024, 3, 15),
        "line_items": [
            {
                "row_number": 10,
                "part_number": "BB-5010",
                "supplier_part_number": "SP-C300",
                "description": "MDF Board 18mm",
                "additional_text": "Grade: E1\n2440x1220",
                "quantity": 200.0,
                "unit": "PCS",
                "delivery_date": date(2024, 3, 15),
            },
        ],
    },
    {
        "order_number": "DEMO-PO-2024-003",
        "order_date": date(2024, 3, 8),
        "status": OrderStatus.REJECTED,
        "source_filename": "demo-order-DEMO-PO-2024-003.pdf",
        "source_filepath": "/uploads/demo/order-DEMO-PO-2024-003.pdf",
        "buyer_name": "Lindqvist Interior Design",
        "buyer_street": "Elm Avenue 8",
        "buyer_zip_city": "10003 DEMO CITY",
        "buyer_country": "Demo Country",
        "buyer_reference": "Sara Demo",
        "buyer_customer_number": "DEMO-003",
        "supplier_name": "Demo Supplier Ltd",
        "supplier_edi_code": "0000000",
        "supplier_street": "1 Business Street",
        "supplier_zip_city": "00000 DEMO CITY",
        "supplier_country": "Demo Country",
        "delivery_name": "Lindqvist Interior Design",
        "delivery_street1": "Elm Avenue 8",
        "delivery_zip_city": "10003 DEMO CITY",
        "delivery_country": "Demo Country",
        "delivery_is_buyer_address": True,
        "delivery_method": "Pickup",
        "payment_terms_days": 30,
        "currency": "USD",
        "delivery_date": date(2024, 3, 25),
        "line_items": [
            {
                "row_number": 10,
                "part_number": "LD-2001",
                "supplier_part_number": "SP-D400",
                "description": "Walnut Veneer Panel 6mm",
                "additional_text": "Surface: Brushed\n1200x600",
                "quantity": 30.0,
                "unit": "PCS",
                "delivery_date": date(2024, 3, 25),
            },
            {
                "row_number": 20,
                "part_number": "LD-2002",
                "supplier_part_number": None,
                "description": "Edge Banding 22mm Walnut",
                "additional_text": None,
                "quantity": 500.0,
                "unit": "M",
                "delivery_date": date(2024, 3, 25),
            },
        ],
    },
]


# ── Seed functions ────────────────────────────────────────────────────────────

async def seed_demo_user(db: AsyncSession) -> None:
    """Create a demo admin login so you can sign in without OAuth credentials."""
    from app.core.security import hash_password

    existing = await db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if existing:
        logger.info("demo_user_exists", email=DEMO_EMAIL)
        return

    user = User(
        id=str(uuid.uuid4()),
        email=DEMO_EMAIL,
        hashed_password=hash_password(DEMO_PASSWORD),
        display_name=DEMO_DISPLAY_NAME,
        avatar_url=None,
        auth_provider="local",
        provider_id=None,
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    logger.info("demo_user_created", email=DEMO_EMAIL)


async def seed_demo_data(db: AsyncSession) -> None:
    """Insert demo customers and orders. Skips any that already exist."""
    now = datetime.now(timezone.utc)

    # ── Customers ─────────────────────────────────────────────────────────
    seeded_customers: dict[str, Customer] = {}
    for c in DEMO_CUSTOMERS:
        existing = await db.scalar(
            select(Customer).where(Customer.erp_customer_id == c["erp_customer_id"])
        )
        if existing:
            seeded_customers[c["erp_customer_id"]] = existing
            continue

        customer = Customer(
            id=str(uuid.uuid4()),
            erp_customer_id=c["erp_customer_id"],
            name=c["name"],
            street=c["street"],
            zip_city=c["zip_city"],
            country=c["country"],
            email=c["email"],
            phone=c["phone"],
            created_at=now,
            updated_at=now,
        )
        db.add(customer)
        seeded_customers[c["erp_customer_id"]] = customer
        logger.info("demo_customer_created", name=c["name"])

    await db.flush()

    # ── Orders ────────────────────────────────────────────────────────────
    for o in DEMO_ORDERS:
        existing = await db.scalar(
            select(Order).where(Order.order_number == o["order_number"])
        )
        if existing:
            continue

        customer = seeded_customers.get(o["buyer_customer_number"])

        order = Order(
            id=str(uuid.uuid4()),
            order_number=o["order_number"],
            order_date=o["order_date"],
            status=o["status"],
            source_filename=o["source_filename"],
            source_filepath=o["source_filepath"],
            buyer_name=o["buyer_name"],
            buyer_street=o["buyer_street"],
            buyer_zip_city=o["buyer_zip_city"],
            buyer_country=o["buyer_country"],
            buyer_reference=o["buyer_reference"],
            buyer_customer_number=o["buyer_customer_number"],
            supplier_name=o["supplier_name"],
            supplier_edi_code=o["supplier_edi_code"],
            supplier_street=o["supplier_street"],
            supplier_zip_city=o["supplier_zip_city"],
            supplier_country=o["supplier_country"],
            delivery_name=o["delivery_name"],
            delivery_street1=o["delivery_street1"],
            delivery_zip_city=o["delivery_zip_city"],
            delivery_country=o["delivery_country"],
            delivery_is_buyer_address=o["delivery_is_buyer_address"],
            delivery_method=o["delivery_method"],
            payment_terms_days=o["payment_terms_days"],
            currency=o["currency"],
            delivery_date=o["delivery_date"],
            matched_customer_id=customer.id if customer else None,
            customer_match_status="matched_exact" if customer else "unmatched",
            customer_match_score=1.0 if customer else None,
            created_at=now,
            updated_at=now,
        )
        db.add(order)
        await db.flush()

        for li in o["line_items"]:
            line_item = LineItem(
                id=str(uuid.uuid4()),
                order_id=order.id,
                row_number=li["row_number"],
                part_number=li.get("part_number"),
                supplier_part_number=li.get("supplier_part_number"),
                description=li["description"],
                additional_text=li.get("additional_text"),
                quantity=li["quantity"],
                unit=li["unit"],
                delivery_date=li.get("delivery_date"),
            )
            db.add(line_item)

        logger.info("demo_order_created", order_number=o["order_number"])

    await db.commit()


async def main() -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        await seed_demo_user(db)
        await seed_demo_data(db)

    print("\n✓ Demo seed complete")
    print("━" * 40)
    print("  Login credentials:")
    print(f"    Email:    {DEMO_EMAIL}")
    print(f"    Password: {DEMO_PASSWORD}")
    print("━" * 40)
    print(f"  Customers: {len(DEMO_CUSTOMERS)}")
    print(f"  Orders:    {len(DEMO_ORDERS)}")
    print("\n  ⚠  All data is fictional — safe for client demos.")
    print("  ⚠  Change the password before any real deployment.\n")


if __name__ == "__main__":
    asyncio.run(main())
