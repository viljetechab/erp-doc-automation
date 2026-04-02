# OrderFlow Pro — Order Pipeline

> **White-label prototype.** All company-specific branding has been removed.
> Configure your own identity via environment variables before any client demo.

## What It Does

OrderFlow Pro is an AI-powered order intake pipeline:

1. **Upload** a purchase order PDF
2. **Extract** all order fields automatically using GPT-4o vision
3. **Review & edit** the extracted data in a structured UI
4. **Match** orders to your customer database (fuzzy + exact)
5. **Export** the order as ERP-compatible XML, or push directly via REST API

---

## Quick Start

### Backend

```bash
cd backend
cp .env.example .env
# Fill in OPENAI_API_KEY and MICROSOFT_* OAuth credentials
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

### Seed Demo Data (optional)

Populates the database with **entirely fictional** demo customers and orders:

```bash
cd backend
python -m app.db.demo_seed
```

---

## White-Label Configuration

All branding is driven by environment variables — no code changes needed.

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|---|---|---|
| `VITE_APP_NAME` | `OrderFlow Pro` | Short name in sidebar & titles |
| `VITE_COMPANY_NAME` | `OrderFlow Pro` | Company display name |
| `VITE_ERP_SYSTEM_NAME` | `ERP System` | ERP name in UI (e.g. `Monitor ERP`, `SAP`) |
| `VITE_CUSTOMER_LIST_LABEL` | `Customer List CSV` | Label for customer import file |
| `VITE_ARTICLE_LIST_LABEL` | `Article Catalogue` | Label for article import file |

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `SUPPLIER_NAME` | Default supplier name (fallback when not found in PDF) |
| `SUPPLIER_EDI_CODE` | Default EDI/vendor code |
| `SUPPLIER_STREET` | Supplier street address |
| `SUPPLIER_ZIP_CITY` | Supplier postal code and city |
| `SUPPLIER_COUNTRY` | Supplier country |
| `ERP_BASE_URL` | ERP push integration endpoint |
| `ERP_API_KEY` | ERP push API key |

### Logo

Replace `frontend/public/logo.svg` with the client logo (200x48px recommended).

### Colors

Edit `frontend/src/index.css`:

```css
:root {
  --color-accent: #1e40af;        /* Primary brand color */
  --color-accent-hover: #1e3a8a;
}
```

---

## Architecture

```
orderflow-pro-demo/
├── backend/                  FastAPI (Python)
│   └── app/
│       ├── config.py         All settings, env-driven
│       ├── db/demo_seed.py   Fictional demo data
│       └── services/         Business logic
└── frontend/                 React 18 + TypeScript + Vite
    └── src/config/branding.ts  ← Single source of truth for UI text
```

## GDPR Notice

- No real customer data is stored in this repository
- Demo seed uses entirely fictional company names and addresses
- All secrets are environment-variable only — nothing hardcoded
