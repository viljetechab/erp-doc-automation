"""Articles API routes — search, validate, and import article/part numbers.

These endpoints allow the frontend to:
1. Search articles by ``artikelnummer`` or ``artikelbenamning`` (type-ahead).
2. Batch-validate a list of part numbers against the catalogue.
3. Import/update articles from CSV or XLSX files.

Security considerations:
- SQL injection: prevented by SQLAlchemy parameterised queries
- LIKE wildcards: user input is escaped (%, _) before embedding in pattern
- Input length: capped at 100 chars for search, 50 per part number
- Result limits: hard-capped at 30 to prevent payload abuse
- Auth: all routes require a valid JWT
"""

from __future__ import annotations

import re
from pathlib import Path

import structlog
from fastapi import APIRouter, Query, UploadFile, File
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUserDep, DbSessionDep
from app.core.exceptions import AppError, FileValidationError
from app.models.article import Article
from app.schemas.article_import import ArticleImportResponse
from app.services.article_import_service import ArticleImportService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/articles", tags=["articles"])

# Upper bound on search results to prevent excessive payloads.
_MAX_SEARCH_RESULTS = 30
_DEFAULT_SEARCH_LIMIT = 15
_MAX_QUERY_LENGTH = 100
_MAX_PART_NUMBER_LENGTH = 50
_MAX_VALIDATE_BATCH = 50


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcard characters (% and _) in user input.

    This prevents users from injecting wildcards that could cause
    unintended broad matches or performance degradation.
    """
    return re.sub(r"([%_\\])", r"\\\1", value)


# ── Search ───────────────────────────────────────────────────────────────


@router.get("/search")
async def search_articles(
    db: DbSessionDep,
    _current_user: CurrentUserDep,
    q: str = Query(
        "",
        min_length=0,
        max_length=_MAX_QUERY_LENGTH,
        description="Search term (min 2 chars for results)",
    ),
    limit: int = Query(_DEFAULT_SEARCH_LIMIT, ge=1, le=_MAX_SEARCH_RESULTS),
) -> list[dict]:
    """Return articles whose ``artikelnummer`` or ``artikelbenamning``
    match the query (case-insensitive substring search).

    Returns a compact list of dicts to keep the payload small.
    Empty or too-short queries return an empty list.
    """
    trimmed = q.strip()
    if len(trimmed) < 2:
        return []

    escaped = _escape_like(trimmed)
    pattern = f"%{escaped}%"

    stmt = (
        select(
            Article.id,
            Article.artikelnummer,
            Article.artikelbenamning,
            Article.standardpris,
        )
        .where(
            or_(
                func.lower(Article.artikelnummer).like(
                    func.lower(pattern), escape="\\"
                ),
                func.lower(Article.artikelbenamning).like(
                    func.lower(pattern), escape="\\"
                ),
            )
        )
        .order_by(Article.artikelnummer)
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": row.id,
            "artikelnummer": row.artikelnummer,
            "artikelbenamning": row.artikelbenamning,
            "standardpris": float(row.standardpris) if row.standardpris else None,
        }
        for row in rows
    ]


# ── Validate ─────────────────────────────────────────────────────────────


@router.get("/validate")
async def validate_part_numbers(
    db: DbSessionDep,
    _current_user: CurrentUserDep,
    part_numbers: str = Query(
        ...,
        max_length=2000,
        description="Comma-separated list of part numbers to validate",
    ),
) -> dict:
    """Check which part numbers exist in the articles catalogue.

    Returns ``{ valid: [...], invalid: [...] }`` where each valid entry
    includes the matched article data.

    Guards:
    - Strips whitespace and rejects empty/over-length values
    - Caps batch size to prevent DoS via huge IN clauses
    """
    raw_parts = [
        p.strip()[:_MAX_PART_NUMBER_LENGTH]
        for p in part_numbers.split(",")
        if p.strip()
    ]
    # Deduplicate and cap batch size
    unique_parts = list(dict.fromkeys(raw_parts))[:_MAX_VALIDATE_BATCH]

    if not unique_parts:
        return {"valid": [], "invalid": []}

    # Single query — fetch all matching articles in one round-trip.
    stmt = select(
        Article.artikelnummer,
        Article.artikelbenamning,
        Article.standardpris,
    ).where(Article.artikelnummer.in_(unique_parts))

    result = await db.execute(stmt)
    found_map: dict[str, dict] = {}
    for row in result.all():
        found_map[row.artikelnummer] = {
            "artikelnummer": row.artikelnummer,
            "artikelbenamning": row.artikelbenamning,
            "standardpris": float(row.standardpris) if row.standardpris else None,
        }

    valid = []
    invalid = []
    for pn in unique_parts:
        if pn in found_map:
            valid.append(found_map[pn])
        else:
            invalid.append(pn)

    return {"valid": valid, "invalid": invalid}


# ── Import ────────────────────────────────────────────────────────────────

_ALLOWED_IMPORT_EXTENSIONS = {".csv", ".xlsx"}
_MAX_IMPORT_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/import", response_model=ArticleImportResponse)
async def import_articles(
    file: UploadFile = File(
        ..., description="Article Catalogue CSV or XLSX export from ERP System",
    ),
    *,
    _current_user: CurrentUserDep,
    db: DbSessionDep,
) -> ArticleImportResponse:
    """Import or update articles from a ERP System Article Catalogue file.

    Supports both CSV (semicolon/comma delimited) and XLSX formats.
    Upserts by artikelnummer — existing articles are updated, new ones inserted.
    """
    try:
        if not file.filename:
            raise FileValidationError("Filename is required")

        ext = Path(file.filename).suffix.lower()
        if ext not in _ALLOWED_IMPORT_EXTENSIONS:
            raise FileValidationError(
                f"Invalid file type '{ext}'. Only CSV and XLSX files are accepted.",
            )

        try:
            raw_bytes = await file.read()
        except Exception as exc:
            raise FileValidationError(f"Failed to read uploaded file: {exc}") from exc
        finally:
            try:
                await file.close()
            except Exception:
                pass

        if len(raw_bytes) > _MAX_IMPORT_BYTES:
            raise FileValidationError(
                f"File too large ({len(raw_bytes) / (1024 * 1024):.1f} MB). "
                "Max is 20 MB.",
            )

        service = ArticleImportService(db)

        if ext == ".xlsx":
            result = await service.import_articles(xlsx_bytes=raw_bytes)
        else:
            try:
                csv_content = raw_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    csv_content = raw_bytes.decode("latin-1")
                except Exception as exc:
                    raise FileValidationError(
                        f"Could not decode CSV. Try saving as UTF-8: {exc}",
                    ) from exc
            result = await service.import_articles(csv_content=csv_content)

        logger.info(
            "article_import_api",
            filename=file.filename,
            imported=result.imported,
            updated=result.updated,
            skipped=result.skipped,
        )
        return result

    except AppError:
        raise
    except Exception as exc:
        logger.error("article_import_unexpected_error", error=str(exc))
        raise AppError(f"Article import failed unexpectedly: {exc}") from exc
