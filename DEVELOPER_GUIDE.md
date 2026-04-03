# OrderFlow Pro Order Pipeline — Developer Guide

## Architecture Overview

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐    ┌──────────────┐
│  PDF Upload  │───▶│ GPT-4o Vision│───▶│  Order Model  │───▶│ ORDERS420 XML│
│  (Frontend)  │    │ (Extraction) │    │ (PostgreSQL)  │    │  (Generator) │
└─────────────┘    └──────────────┘    └───────────────┘    └──────────────┘
     React +           OpenAI API         SQLAlchemy ORM      lxml etree
     Vite              PyMuPDF            Pydantic schemas     ERP System format
```

### Tech Stack

| Layer       | Technology                                 |
| ----------- | ------------------------------------------ |
| Frontend    | React 18 + TypeScript, Vite, Axios, Lucide |
| Backend     | FastAPI, Uvicorn, Pydantic, Structlog      |
| Database    | PostgreSQL + SQLAlchemy (async via asyncpg) |
| AI          | OpenAI GPT-4o Vision API                   |
| XML         | lxml (generates Monitor ORDERS420 format)  |
| PDF parsing | PyMuPDF (converts PDF pages to images)     |

---

## Data Flow: PDF → XML (Step by Step)

### 1. Upload (`POST /api/v1/orders/upload`)

- Frontend sends PDF via `multipart/form-data`
- Backend validates file type, size, saves to `data/uploads/`
- File path: `{UPLOAD_DIR}/{uuid}_{original_name}.pdf`

### 2. Extraction (`PDFExtractionService.extract()`)

- **PyMuPDF** converts each PDF page to a high-resolution PNG image
- Images are sent to **OpenAI GPT-4o Vision** with a system prompt (`order_extraction.py`)
- The AI returns a structured JSON matching the `ExtractedOrderData` Pydantic schema
- Confidence scores (0.0–1.0) are included for each field

### 3. Persistence (`OrderService.create_from_extraction()`)

- Extracted data is mapped to `Order` + `OrderLineItem` ORM models
- If line items have no `delivery_date`, the header-level date is used as fallback
- Raw JSON and confidence scores are stored for audit

### 4. Review (Frontend `OrderDetailPage`)

- User sees all extracted fields with confidence indicators (yellow = uncertain)
- Editable fields when order is in `EXTRACTED`, `IN_REVIEW`, or `REJECTED` status
- **Preview button** opens fullscreen PDF + XML side-by-side comparison

### 5. Approval (`POST /api/v1/orders/{id}/approve`)

- `XMLGeneratorService.generate(order)` builds the ORDERS420 XML
- XML is persisted to the `generated_xml` column
- Status transitions to `APPROVED`

### 6. Download (`GET /api/v1/orders/{id}/xml`)

- Returns the stored XML with `Content-Disposition: attachment`

---

## XML Role Mapping (Critical)

This is the **most important** concept and the most common source of confusion.

```
ERP Reference (G73216.xml):

<Supplier SupplierCodeEdi="0000000">     ← OrderFlow Pro AB (US, from .env config)
    <Name>OrderFlow Pro AB</Name>
    <StreetBox1>1 Business Street</StreetBox1>
    <ZipCity1>00000 DEMO CITY</ZipCity1>
    <Country>Sverige</Country>
</Supplier>

<Buyer>                                   ← Customer (THEM, from PDF extraction)
    <Name>Careco Inredningar AB</Name>
    <StreetBox1>Box 95</StreetBox1>
    <ZipCity1>283 22 OSBY</ZipCity1>
    <Country>Sverige</Country>
</Buyer>
```

**Rule:** `<Supplier>` = OrderFlow Pro (our company, from `SUPPLIER_*` env vars).
`<Buyer>` = the customer who sent the purchase order (from PDF extraction).

---

## Field Mapping Table

### Header → XML

| PDF / Extraction Field | DB Column            | XML Element                         |
| ---------------------- | -------------------- | ----------------------------------- |
| _(from config)_        | —                    | `Supplier/Name`                     |
| _(from config)_        | —                    | `Supplier@SupplierCodeEdi`          |
| `buyer_name`           | `buyer_name`         | `Buyer/Name`                        |
| `buyer_street`         | `buyer_street`       | `Buyer/StreetBox1`                  |
| `buyer_zip_city`       | `buyer_zip_city`     | `Buyer/ZipCity1`                    |
| `buyer_country`        | `buyer_country`      | `Buyer/Country`                     |
| `buyer_reference`      | `buyer_reference`    | `References/BuyerReference`         |
| `delivery_name`        | `delivery_name`      | `DeliveryAddress/Name`              |
| `delivery_street1`     | `delivery_street1`   | `DeliveryAddress/StreetBox1`        |
| `delivery_street2`     | `delivery_street2`   | `DeliveryAddress/StreetBox2`        |
| `delivery_zip_city`    | `delivery_zip_city`  | `DeliveryAddress/ZipCity1`          |
| `delivery_country`     | `delivery_country`   | `DeliveryAddress/Country`           |
| _(hardcoded "1")_      | —                    | `DeliveryAddress/CompanyAdressFlag` |
| `delivery_method`      | `delivery_method`    | `DeliveryTerms/DeliveryMethod`      |
| `transport_payer`      | `transport_payer`    | `DeliveryTerms/TransportPayer`      |
| `order_date`           | `order_date`         | `Terms/OrderDate`                   |
| `payment_terms_days`   | `payment_terms_days` | `PaymentTerms/TermsOfPaymentDays`   |
| `currency`             | `currency`           | `Export/Currency`                   |

### Line Items → XML Rows

| Extraction Field       | DB Column              | XML (RowType=1)           | XML (RowType=4)           |
| ---------------------- | ---------------------- | ------------------------- | ------------------------- |
| `part_number`          | `part_number`          | `Part@PartNumber`         | `Part@PartNumber`         |
| `supplier_part_number` | `supplier_part_number` | `Part@SupplierPartNumber` | `Part@SupplierPartNumber` |
| `description`          | `description`          | `Text`                    | —                         |
| `additional_text`      | `additional_text`      | —                         | `Text` (multiline)        |
| `quantity`             | `quantity`             | `Quantity` (2dp)          | `1.00` (fixed)            |
| `unit`                 | `unit`                 | `Unit`                    | _(empty)_                 |
| `delivery_date`        | `delivery_date`        | `DeliveryPeriod`          | `DeliveryPeriod`          |
| `unit_price`           | `unit_price`           | `Each` (2dp)              | _(empty)_                 |
| `discount_percent`     | `discount`             | `Discount` (2dp)          | `0.00`                    |

---

## Delivery Address Extraction Rules

The PDF delivery address block typically has 3–4 lines:

```
Line 1: Careco Inredningar AB     → delivery_name
Line 2: LAS Interör AB            → delivery_street1 (sub-company/c/o)
Line 3: Ågatan 5                  → delivery_street2 (actual street)
Line 4: 646 30 Gnesta             → delivery_zip_city
```

**Important:** `delivery_street1` is NOT a street — it's often a sub-company or intermediary name. The actual street goes in `delivery_street2`.

---

## Transport Payer Logic

| PDF Text                         | Value | Meaning       |
| -------------------------------- | ----- | ------------- |
| _(default / no mention)_         | `C`   | Customer pays |
| "Mottagaren betalar frakt"       | `C`   | Customer pays |
| "Fraktfritt" / "Fritt levererat" | `S`   | Supplier pays |

---

## Environment Configuration

All config is in `backend/.env`. Key variables:

```env
OPENAI_API_KEY=sk-...           # Required for PDF extraction
OPENAI_MODEL=gpt-4o             # Vision model
SUPPLIER_NAME=OrderFlow Pro AB  # Goes into <Supplier> XML element
SUPPLIER_EDI_CODE=0000000       # SupplierCodeEdi attribute
SUPPLIER_STREET=1 Business Street
SUPPLIER_ZIP_CITY=00000 DEMO CITY
SUPPLIER_COUNTRY=Sverige
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/orderflow_pro
```

---

## Order Status Lifecycle

```
PENDING_EXTRACTION → EXTRACTED → IN_REVIEW → APPROVED
                       ↓              ↓          ↓
              EXTRACTION_FAILED    REJECTED ←────┘
                                     ↓
                                  (re-edit → IN_REVIEW → APPROVED)
```

---

## API Endpoints

| Method | Path                              | Description                       |
| ------ | --------------------------------- | --------------------------------- |
| POST   | `/api/v1/orders/upload`           | Upload PDF → extract → create     |
| GET    | `/api/v1/orders`                  | List orders (filter by status)    |
| GET    | `/api/v1/orders/{id}`             | Get full order details            |
| PATCH  | `/api/v1/orders/{id}`             | Update fields during review       |
| POST   | `/api/v1/orders/{id}/approve`     | Approve → generate XML            |
| POST   | `/api/v1/orders/{id}/reject`      | Reject → back to editing          |
| GET    | `/api/v1/orders/{id}/xml`         | Download generated XML            |
| GET    | `/api/v1/orders/{id}/pdf`         | Serve uploaded PDF (inline)       |
| GET    | `/api/v1/orders/{id}/preview-xml` | Generate XML preview (no persist) |

---

## How to Add a New Field

1. **Schema:** Add to `ExtractedOrderData` in `schemas/extraction.py`
2. **Prompt:** Add extraction instructions in `prompts/order_extraction.py`
3. **DB Model:** Add column to `Order` in `models/order.py`
4. **Migration:** Create Alembic migration: `alembic revision --autogenerate -m "add field"`
5. **Service:** Map in `OrderService.create_from_extraction()`
6. **XML:** Add element in `XMLGeneratorService._add_*()` method
7. **API Schema:** Add to `OrderResponse` and `OrderUpdateRequest` in `schemas/order.py`
8. **Frontend:** Add to `Order` type and `OrderDetailPage` form
9. **Tests:** Add test in `test_xml_generator.py`

---

## Common Senior Dev Questions

### Q: How do you handle malformed AI responses?

**A:** Pydantic validates the extracted JSON against `ExtractedOrderData`. Invalid responses raise `ValidationError`, which is caught and persisted as `EXTRACTION_FAILED` status with the error message.

### Q: What happens if the PDF extraction times out?

**A:** Frontend uses a 5-minute timeout (`UPLOAD_TIMEOUT_MS = 300000`). Backend has no timeout — if OpenAI is slow, the request stays open. The frontend shows a user-friendly timeout message with guidance to check the Orders page.

### Q: How is data integrity ensured?

**A:** SQLAlchemy async sessions with `flush()` for immediate ID generation. Cascade deletes ensure line items are removed with orders. Status transitions are validated server-side (can't approve a failed order).

### Q: How do you prevent XSS/injection?

**A:** lxml generates XML via DOM API (not string concatenation), preventing XML injection. FastAPI auto-validates all input via Pydantic. Frontend uses React's built-in XSS protection.

### Q: What's the testing strategy?

**A:** 22 unit tests in `test_xml_generator.py` validate every XML element and attribute against the ERP reference file (G73216.xml). Tests use `get_settings()` to inject real configuration values.

### Q: How do you handle concurrent edits?

**A:** Currently single-user. PostgreSQL handles concurrent writes natively. For multi-user, would need optimistic locking (version column + `If-Match` header).

### Q: What about performance with large PDFs?

**A:** PyMuPDF processes one page at a time. Images are sent individually to OpenAI. For very large PDFs (>10 pages), extraction time increases linearly. The 5-minute frontend timeout accommodates this.

### Q: Why PostgreSQL?

**A:** PostgreSQL is the production database. It provides proper concurrency, ACID transactions, and is required for deployment. SQLite is only supported as a convenience for local development with `APP_ENV=development`. Schema management uses Alembic migrations (`alembic upgrade head`).

### Q: How is the XML validated?

**A:** The XML structure is validated via the ERP reference file (G73216.xml). The generator uses lxml's DOM API which guarantees well-formed XML. No XSD validation yet — ERP System validates on import.

### Q: What's the error handling strategy?

**A:** Three-layer approach:

1. **Domain errors** (`AppError` subclasses) — structured, user-facing
2. **Framework errors** (FastAPI validation) — automatic 422 responses
3. **Unexpected errors** — caught, logged with structlog, wrapped in `AppError`
