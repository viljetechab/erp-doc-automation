# PDF Order Pipeline — Project Overview, Scope & Time Estimation

## Project Summary

A **PDF order intake and approval pipeline** that:
- Parses PDF orders (AI/extraction)
- Lets users review, edit, and approve
- Uses a customer database to prefill/resolve customer IDs and references
- Sends approved orders into **Monitor** (ERP) via API
- Supports both one-off uploads and a continuous “incoming orders” flow with list + detail views

---

## Scope by Step

| Step | Scope | Main Deliverables |
|------|--------|-------------------|
| **Step 1** | Single PDF → parse → review/edit → export XML for Monitor | PDF upload UI, parsing (AI/OCR), editable result view, XML generation, “OK” / edit flow |
| **Step 2** | Customer master from ERP export | Import ERP export, customer DB (schema + storage), matching/resolution logic, prefill of customer ID & references in orders |
| **Step 3** | Incoming-orders workflow | Order list view, order detail view (same flow as Step 1), “approve → next” navigation, persistence of orders and status |
| **Step 4** | Monitor integration | API client for Monitor, push approved orders (not only XML export), error handling, (optional) sync status back |

---

## Detailed Scope Breakdown

### 1. PDF Order Data Extraction

**Objective:** Parse and extract structured order data from incoming PDF files.

| Area | Details |
|------|--------|
| **Input** | Incoming PDF order documents (uploaded or received via defined channel). |
| **Approach** | Choose and implement extraction method: LLM/vision API for flexible layouts, dedicated PDF/table library for fixed templates, or OCR (e.g. Tesseract) for scanned documents. |
| **Sub-tasks** | • PDF ingestion (upload endpoint, file validation, storage) <br>• Text/layout extraction (per page or full document) <br>• Entity extraction: order header (date, ref, customer info), line items (article ID, qty, price, etc.), totals, delivery/shipping <br>• Output: internal structured model (e.g. JSON) for downstream use <br>• Handling multiple PDF formats if more than one layout exists |
| **Deliverables** | Extraction service/API; structured data model; config or prompts per PDF type (if multiple). |
| **Risks / Notes** | Accuracy depends on PDF quality and layout consistency; consider confidence scores and “needs review” flags for low-confidence extractions. |

---

### 2. Structured Data Transformation

**Objective:** Convert the extracted data into a format aligned with Monitor’s import or API specification.

| Area | Details |
|------|--------|
| **Input** | Extracted order data (internal JSON/model). |
| **Output** | Monitor-ready payload: XML (if import file required) and/or request body for Monitor API. |
| **Sub-tasks** | • Obtain and document Monitor’s schema (XSD, API spec, or sample files) <br>• Field mapping: map internal fields → Monitor fields (order ref, customer ID, lines, quantities, prices, etc.) <br>• Data type and format conversion (dates, decimals, codes) <br>• Build transformer(s): extracted data → Monitor XML and/or API DTOs <br>• Optional: support multiple Monitor endpoints or import types if needed |
| **Deliverables** | Mapping specification; transformation service; generated XML and/or API payloads that pass Monitor validation. |
| **Risks / Notes** | Schema changes in Monitor may require mapping updates; version mapping doc and tests. |

---

### 3. Customer Data Import & Matching

**Objective:** Import a full customer export from the ERP and build a customer database to automatically resolve customer IDs, references, and related data.

| Area | Details |
|------|--------|
| **Input** | Full customer export from ERP (e.g. CSV, Excel, XML) — format and frequency TBD. |
| **Sub-tasks** | • Define customer DB schema (ID, name, refs, addresses, payment/shipping defaults, etc.) <br>• Import pipeline: parse export file → validate → upsert into customer DB <br>• Matching logic: match parsed order (e.g. name, order ref, delivery address) to customer record; return customer ID and prefill fields <br>• Prefill: use matched customer to populate order header (customer ID, references, defaults) in review UI and in Monitor payload <br>• Handle ambiguous/multiple matches (e.g. suggest list or manual pick) and “no match” (manual entry or flag for review) |
| **Deliverables** | Customer database; import job/UI; matching service; prefill integration in order flow. |
| **Risks / Notes** | Export format and update frequency affect design (one-time vs scheduled vs on-demand). |

---

### 4. PDF Upload, Order Review & Approval Portal

**Objective:** Web-based interface for upload, list view, detail view, and approval workflow before sending orders to Monitor.

| Area | Details |
|------|--------|
| **PDF upload** | • Upload page: drag-and-drop or file picker, single or multiple PDFs <br>• Client-side validation (type, size) and upload to backend <br>• Trigger extraction and create “order” record with status (e.g. Pending review) |
| **List view** | • List of incoming orders: key columns (order ref, customer, date, status, source) <br>• Filtering and sorting by status, date, etc. <br>• Click row → open order detail |
| **Order detail view** | • Show parsed data in editable form (header + line items) <br>• Prefilled customer ID and references from matching <br>• Edit fields, add/remove lines if required <br>• Validation feedback (required fields, formats) before approval <br>• Actions: Save draft, Approve (submit to Monitor), Reject/Return (if in scope) |
| **Approval workflow** | • Status flow: e.g. New → In review → Approved → Sent to Monitor (or Failed) <br>• “Approve and go to next” so user can process queue without leaving detail view <br>• Optional: simple audit (who approved when) |
| **Deliverables** | Upload page; orders list page; order detail page with edit + approve; workflow state and navigation. |
| **Risks / Notes** | Auth and roles (viewer vs approver) if multiple users; responsive layout if needed. |

---

### 5. Direct Monitor API Integration

**Objective:** Integrate with the Monitor API to create and synchronize approved orders in the ERP.

| Area | Details |
|------|--------|
| **Sub-tasks** | • Obtain API documentation (REST/SOAP), auth (e.g. API key, OAuth), rate limits <br>• Implement API client: authentication, request building, error handling <br>• Map approved order (internal model) to Monitor create-order endpoint(s) <br>• Call Monitor on “Approve”: create order (and optionally order lines, references) <br>• Handle response: store Monitor order ID and/or status in our DB for traceability <br>• Optional: sync status back (e.g. confirmed, rejected by ERP) and show in portal |
| **Deliverables** | Monitor API client; integration in approval step; persistence of Monitor IDs/status; (optional) status sync. |
| **Risks / Notes** | Retries and idempotency if API is flaky; clear errors when Monitor rejects (validation, duplicates). |

---

### 6. Error Handling & Validation

**Objective:** Robust validation and clear user feedback for missing data, wrong formats, unmatched customers, invalid articles, and API errors.

| Area | Details |
|------|--------|
| **Validation layers** | • **Extraction:** missing or low-confidence fields → flag in UI, block approve until resolved or explicitly accepted <br>• **Transformation:** required Monitor fields missing or invalid format → validation errors before API call <br>• **Customer matching:** no match or multiple matches → show in UI, require selection or manual input <br>• **Article/master data:** invalid article numbers or unknown SKUs → validate against list or API if available; show error and block or warn on approve <br>• **Monitor API:** HTTP errors, business rule errors (e.g. duplicate order) → map to user message and optionally retry/queue |
| **User feedback** | • Inline validation messages on fields and line items <br>• Summary/blocking errors before Approve <br>• Toast or banner for success/failure after submit to Monitor <br>• Order status and “Failed” reason visible in list/detail |
| **Logging** | • Log validation failures, API requests/responses (sanitized), and errors with order ID for support and debugging |
| **Deliverables** | Validation rules per layer; UI error display; logging and (optional) error reporting. |

---

### 7. Testing & Validation

**Objective:** Comprehensive testing to ensure correctness, integration, and end-to-end workflow.

| Area | Details |
|------|--------|
| **Unit tests** | • Extractors: mock PDF input → assert structured output <br>• Transformers: internal model → Monitor XML/API payload <br>• Customer matching: sample data → correct ID and prefill <br>• Validation rules: invalid inputs → expected errors |
| **Integration tests** | • PDF upload → extraction → DB; customer import → DB; approval → Monitor API (stub or test env) <br>• API client against Monitor sandbox/test if available |
| **Parsing accuracy** | • Test set of sample PDFs; measure field-level accuracy and regressions when layout or prompts change |
| **API testing** | • Monitor API: create order (test data), assert response and side effects in test system <br>• Error cases: invalid payload, duplicate, auth failure |
| **End-to-end (E2E)** | • Upload PDF → review → edit → approve → verify order in Monitor (or stub) <br>• Customer prefill and validation messages in the flow <br>• List → detail → approve next flow |
| **Deliverables** | Unit test suite; integration tests; parsing accuracy checks; API tests; E2E scenarios (automated or scripted). |

---

## Time Estimation (Single Full-Stack Developer)

*Assumptions: Web app (e.g. React/Next + Node/Python), one developer, no existing codebase.*

| Phase | Work | Low | High |
|-------|------|-----|------|
| **Step 1** | PDF upload, parsing (e.g. LLM/OCR), UI for result + edits, XML generation, basic auth | 2–3 weeks | 4–5 weeks |
| **Step 2** | ERP export parser, DB design, customer matching/prefill, wiring into Step 1 | 1–2 weeks | 2–3 weeks |
| **Step 3** | Order list + detail views, state (e.g. pending/approved), “next order” flow, persistence | 1–2 weeks | 2–3 weeks |
| **Step 4** | Monitor API integration, mapping to their schema, retries/errors, testing | 1–2 weeks | 3–4 weeks |
| **Common** | Auth, env/config, deployment, basic testing, docs | 1–2 weeks | 2–3 weeks |

### Total (Ballpark)

**6–10 weeks** (~1.5–2.5 months) for an MVP that covers all four steps end-to-end.

*If PDF layouts are highly variable or Monitor API is poorly documented, lean toward the upper end.*

---

## Clarifying Questions

1. **How many PDF formats are there?** Or is it a single structured format (one template/layout only)?
2. **Is an XML file needed for Monitor?** Given we have an approval system to import data into Monitor, should we still produce XML, or will import be done only via API?
3. **They provide full customer export data. How often will it be updated?** (e.g. one-time, daily, weekly, or manual/on demand?)

### Additional (Step 3 — Orders Flow)

- Where do “incoming orders” come from: email, folder watch, API, or only manual PDF upload for now?
- Required order states (e.g. New → In review → Approved → Sent to Monitor → Failed)? Any need for rejection/return to sender?

### Additional (General)

- Tech stack: any must-use (e.g. React, .NET, Python)?
- Hosting: cloud (which?), on-prem, or undecided?
- Any compliance (GDPR, audit logs, data retention)?

---

## Summary

- **Overview:** PDF order parsing → review/edit → customer prefill → approve → send to Monitor (XML and/or API), with an optional “incoming orders” list/detail flow.
- **Scope:** Steps 1–4 as in the table above.
- **Estimate:** **~6–10 weeks** for one developer to reach an end-to-end MVP; can refine once the questions above are answered.
Conversations 1

Thread in Rajashekar
1:29 PM


Rajashekar
OrderFlow Pro:
I’m thinking about the solution roughly like this, step by step:
Step 1
Drag & drop a PDF order → get a parsed result on the other side → either press “OK” or make edits → generate an XML file ready for import into Monitor.
Step 2
They provide a full customer export from the ERP → we build a customer database so we can automatically resolve and prefill correct customer IDs, references, etc.
Step 3
All orders flow directly into the system.
There’s:
a list view with incoming orders, and
an order detail view where you do the same workflow as in Step 1.
Once an order is approved, you can immediately jump to the next one.
Step 4
Direct API integration with Monitor
(This might move earlier if we are 100% confident we can solve it cleanly.)e an order is approved, you can immediately jump to the next one.
Step 4
Direct API integration with Monitor
(This might move earlier if we are 100% confident we can solve it cleanly.)e an order is approved, you can immediately jump to the next one.
Step 4
Direct API integration with Monitor
(This might move earlier if we are 100% confident we can solve it cleanly.)