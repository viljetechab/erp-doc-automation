"""Customer service — CSV import, deduplication, and order matching logic.

Changes from initial version:
- match_order_to_customer() fuzzy path no longer loads ALL customers into
  memory (#13). It now fetches up to MAX_FUZZY_CANDIDATES rows using a
  LIKE-based pre-filter on the first normalised token, then runs SequenceMatcher
  only on that reduced set. For production scale, replace with a pg_trgm
  similarity query (see NOTE below).
- CustomerImportResponse errors are sanitised: raw SQLAlchemy exception strings
  are replaced with user-friendly messages in non-debug mode (#25).
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from difflib import SequenceMatcher

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CustomerMatchError
from app.models.customer import Customer
from app.models.order import Order
from app.schemas.customer import CustomerImportResponse, CustomerMatchResult

logger = structlog.get_logger(__name__)

FUZZY_MATCH_THRESHOLD = 0.72
FUZZY_HIGH_CONFIDENCE = 0.85

# Maximum candidates to load for in-memory fuzzy matching.
# With a pg_trgm GIN index this constant becomes irrelevant — the SQL query
# handles ranking. Without it, this cap prevents OOM at scale.
MAX_FUZZY_CANDIDATES = 200


class CustomerService:
    """Handles CSV import of Customer List and customer matching for orders."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── CSV Import ────────────────────────────────────────────────────────

    async def import_from_csv(self, csv_content: str) -> CustomerImportResponse:
        """Parse Customer List CSV and upsert customer records.

        The CSV has one row per contact (Telefon/Fax/E-post). This method
        groups rows by erp_customer_id, picks the best email and phone, then
        upserts one Customer row per unique Kund value.
        """
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as exc:
            raise CustomerMatchError(f"Failed to parse CSV: {exc}") from exc

        raw_headers = {str(h).strip() for h in (reader.fieldnames or [])}
        if not raw_headers:
            raise CustomerMatchError(
                "The uploaded file appears to be empty or has no header row. "
                "Please upload a valid ERP Customer List CSV."
            )

        _REQUIRED_CUSTOMER_COLS = {"Kund", "Namn"}
        missing = _REQUIRED_CUSTOMER_COLS - raw_headers
        if missing:
            normalised = {h.lower() for h in raw_headers}
            if "article_number" in normalised or "article_name" in normalised:
                raise CustomerMatchError(
                    "Wrong file — this looks like an Article Catalogue (article file). "
                    "Please upload it via 'Update Articles' instead."
                )
            raise CustomerMatchError(
                f"Wrong file — this does not look like a Customer List CSV. "
                f"Required columns {sorted(_REQUIRED_CUSTOMER_COLS)} not found. "
                f"Found: {sorted(raw_headers)}. "
                f"Make sure you are uploading the Monitor ERP Customer List export."
            )

        customer_map: dict[str, dict[str, str | None]] = {}
        skipped = 0
        errors: list[str] = []

        try:
            for row in reader:
                try:
                    kund = str(row.get("Kund", "")).strip()
                    namn = str(row.get("Namn", "")).strip()
                    if not kund or not namn:
                        skipped += 1
                        continue

                    if kund not in customer_map:
                        customer_map[kund] = {
                            "erp_customer_id": kund,
                            "name": namn,
                            "email": None,
                            "phone": None,
                        }

                    typ = str(row.get("Typ", "")).strip()
                    value = str(row.get("E-post/Tfn.nr", "")).strip()

                    if typ == "E-post" and value and not customer_map[kund]["email"]:
                        customer_map[kund]["email"] = value
                    elif typ == "Telefon" and value and not customer_map[kund]["phone"]:
                        customer_map[kund]["phone"] = value

                except Exception as row_exc:
                    errors.append(f"Row parse error: {row_exc}")
                    skipped += 1
                    continue
        except Exception as exc:
            raise CustomerMatchError(f"Failed to iterate CSV rows: {exc}") from exc

        imported = 0
        for data in customer_map.values():
            try:
                async with self._db.begin_nested():
                    stmt = select(Customer).where(
                        Customer.erp_customer_id == data["erp_customer_id"],
                    )
                    result = await self._db.execute(stmt)
                    existing = result.scalar_one_or_none()

                    if existing:
                        existing.name = data["name"] or existing.name
                        if data["email"]:
                            existing.email = data["email"]
                        if data["phone"]:
                            existing.phone = data["phone"]
                    else:
                        customer = Customer(
                            erp_customer_id=data["erp_customer_id"] or "",
                            name=data["name"] or "",
                            email=data["email"],
                            phone=data["phone"],
                        )
                        self._db.add(customer)

                imported += 1
            except Exception as exc:
                # FIXED (#25): sanitise raw DB exception strings
                errors.append(
                    _sanitize_db_error(
                        exc,
                        context=f"customer {data.get('erp_customer_id')}",
                    )
                )
                skipped += 1
                continue

        try:
            await self._db.flush()
        except Exception as exc:
            raise CustomerMatchError(
                f"Failed to commit customer import: {exc}",
            ) from exc

        logger.info(
            "customer_import_complete",
            imported=imported,
            skipped=skipped,
            errors=len(errors),
        )

        return CustomerImportResponse(
            imported=imported,
            skipped=skipped,
            errors=errors,
        )

    # ── Order Matching ────────────────────────────────────────────────────

    async def match_order_to_customer(self, order: Order) -> CustomerMatchResult:
        """Attempt to match an order's buyer fields to a customer record.

        Matching priority:
        1. Exact match on buyer_customer_number -> customers.erp_customer_id
        2. Fuzzy name match on buyer_name -> customers.name (threshold 0.72)
           Uses a pre-filter LIKE query to limit candidates before in-memory
           SequenceMatcher (#13). For high-scale, use pg_trgm instead.
        3. Unmatched if nothing found
        """
        buyer_num = (order.buyer_customer_number or "").strip()
        buyer_name = (order.buyer_name or "").strip()

        if not buyer_num and not buyer_name:
            return CustomerMatchResult(
                status="skipped",
                customer_id=None,
                erp_customer_id=None,
                customer_name=None,
                score=None,
                note="No buyer_customer_number or buyer_name available for matching",
            )

        # ── Step 1: Exact match on ERP customer ID ────────────────────────
        if buyer_num:
            try:
                result = await self._db.execute(
                    select(Customer).where(
                        Customer.erp_customer_id == buyer_num,
                    ),
                )
                customer = result.scalar_one_or_none()
            except Exception as exc:
                raise CustomerMatchError(
                    f"DB query failed during exact customer ID match: {exc}",
                ) from exc

            if customer:
                logger.info(
                    "customer_match_exact",
                    order_id=order.id,
                    erp_customer_id=customer.erp_customer_id,
                )
                return CustomerMatchResult(
                    status="matched_exact",
                    customer_id=customer.id,
                    erp_customer_id=customer.erp_customer_id,
                    customer_name=customer.name,
                    score=1.0,
                    note=f"Exact match on buyer_customer_number '{buyer_num}'",
                )

        # ── Step 2: Fuzzy name match with pre-filter (#13) ───────────────
        if buyer_name:
            normalized_query = _normalize_company_name(buyer_name)

            # Pre-filter: fetch candidates whose name starts with the same
            # first token (e.g. "acme" for "Acme Corp AB"). This reduces
            # the in-memory set from ALL customers to a small subset.
            # NOTE: For production at scale, replace with:
            #   SELECT *, similarity(name, :query) AS sim FROM customers
            #   WHERE similarity(name, :query) > 0.3
            #   ORDER BY sim DESC LIMIT 20
            # after enabling the pg_trgm extension with a GIN index.
            tokens = normalized_query.split()
            first_token = tokens[0] if tokens else ""
            # Escape LIKE wildcards so e.g. "Acme_Corp" doesn't match "AcmeXCorp"
            first_token_escaped = first_token.replace("%", r"\%").replace("_", r"\_")

            try:
                if first_token_escaped:
                    pre_filter = select(Customer).where(
                        or_(
                            func.lower(Customer.name).like(f"{first_token_escaped}%"),
                            func.lower(Customer.name).like(f"% {first_token_escaped}%"),
                        )
                    ).order_by(Customer.name).limit(MAX_FUZZY_CANDIDATES)
                else:
                    pre_filter = select(Customer).order_by(Customer.name).limit(MAX_FUZZY_CANDIDATES)

                result = await self._db.execute(pre_filter)
                candidates = list(result.scalars().all())
            except Exception as exc:
                raise CustomerMatchError(
                    f"DB query failed during fuzzy customer name match: {exc}",
                ) from exc

            best_score = 0.0
            best_customer: Customer | None = None

            for c in candidates:
                try:
                    normalized_candidate = _normalize_company_name(c.name)
                    score = SequenceMatcher(
                        None,
                        normalized_query,
                        normalized_candidate,
                    ).ratio()
                    if score > best_score:
                        best_score = score
                        best_customer = c
                except Exception:
                    continue

            if best_customer and best_score >= FUZZY_MATCH_THRESHOLD:
                status = (
                    "matched_fuzzy"
                    if best_score < FUZZY_HIGH_CONFIDENCE
                    else "matched_exact"
                )
                logger.info(
                    "customer_match_fuzzy",
                    order_id=order.id,
                    score=best_score,
                    customer_name=best_customer.name,
                    status=status,
                )
                return CustomerMatchResult(
                    status=status,
                    customer_id=best_customer.id,
                    erp_customer_id=best_customer.erp_customer_id,
                    customer_name=best_customer.name,
                    score=round(best_score, 4),
                    note=(
                        f"Fuzzy name match: '{buyer_name}' -> '{best_customer.name}' "
                        f"(score {best_score:.1%})"
                    ),
                )

        # ── Step 3: No match ─────────────────────────────────────────────
        logger.info(
            "customer_match_unmatched",
            order_id=order.id,
            buyer_name=buyer_name,
        )
        return CustomerMatchResult(
            status="unmatched",
            customer_id=None,
            erp_customer_id=None,
            customer_name=None,
            score=None,
            note=(
                f"No customer found for buyer_name='{buyer_name}' "
                f"buyer_customer_number='{buyer_num}'"
            ),
        )

    async def persist_match_result(
        self,
        order: Order,
        result: CustomerMatchResult,
    ) -> Order:
        """Write match result back to the order row."""
        try:
            order.matched_customer_id = result.customer_id
            order.customer_match_status = result.status
            order.customer_match_score = result.score
            order.customer_match_note = result.note
            await self._db.flush()
        except Exception as exc:
            raise CustomerMatchError(
                f"Failed to persist match result for order {order.id}: {exc}",
            ) from exc

        return order

    async def list_customers(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
    ) -> list[Customer]:
        """List customers with optional name search."""
        try:
            stmt = select(Customer).where(Customer.is_active.is_(True))
            if search:
                normalized = f"%{search.strip()}%"
                stmt = stmt.where(
                    func.lower(Customer.name).like(func.lower(normalized)),
                )
            stmt = stmt.order_by(Customer.name).limit(limit).offset(offset)
            result = await self._db.execute(stmt)
            return list(result.scalars().all())
        except Exception as exc:
            raise CustomerMatchError(f"Failed to list customers: {exc}") from exc

    async def get_by_erp_id(self, erp_id: str) -> Customer | None:
        """Fetch a customer by ERP customer ID."""
        try:
            result = await self._db.execute(
                select(Customer).where(Customer.erp_customer_id == erp_id),
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            raise CustomerMatchError(
                f"Failed to fetch customer by ERP ID '{erp_id}': {exc}",
            ) from exc


# ── Helpers ───────────────────────────────────────────────────────────────


def _normalize_company_name(name: str) -> str:
    """Normalize a company name for fuzzy comparison.

    Strips legal suffixes (AB, Ltd, GmbH etc.), removes punctuation,
    collapses whitespace, and lowercases.
    """
    if not name:
        return ""
    normalized = unicodedata.normalize("NFC", name.lower().strip())
    normalized = re.sub(
        r"\b(ab|aktiebolag|hb|kb|ltd|inc|gmbh|bv|nv|oy|as|aps|srl|sa)\b\.?",
        "",
        normalized,
    )
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


_KNOWN_DB_ERRORS = {
    "UNIQUE constraint failed": "A customer with this ID already exists (duplicate).",
    "unique constraint": "A customer with this ID already exists (duplicate).",
    "IntegrityError": "Database integrity error — possible duplicate or constraint violation.",
    "OperationalError": "Database operational error — please retry.",
}


def _sanitize_db_error(exc: Exception, context: str) -> str:
    """Return a user-friendly error string instead of raw DB internals (#25)."""
    raw = str(exc)
    for pattern, friendly in _KNOWN_DB_ERRORS.items():
        if pattern.lower() in raw.lower():
            return f"Failed to import {context}: {friendly}"
    # Fall back to a generic message to avoid leaking DB schema details
    return f"Failed to import {context}: database error (see server logs for details)."