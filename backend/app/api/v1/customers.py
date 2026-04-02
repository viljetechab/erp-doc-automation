"""Customer API routes — import CSV, list customers, match an order."""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, UploadFile, File, Query

from app.api.deps import CurrentUserDep, DbSessionDep, OrderServiceDep
from app.core.exceptions import AppError, FileValidationError
from app.schemas.customer import CustomerImportResponse, CustomerMatchResult
from app.services.customer_service import CustomerService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])

ALLOWED_CSV_EXTENSIONS = {".csv"}
MAX_CSV_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/import", response_model=CustomerImportResponse)
async def import_customers(
    file: UploadFile = File(
        ..., description="Customer List CSV export from ERP System",
    ),
    *,
    _current_user: CurrentUserDep,
    db: DbSessionDep,
) -> CustomerImportResponse:
    """Import or refresh the customer database from a ERP System Customer List CSV.

    Idempotent: re-uploading the same file updates existing records
    and adds new ones without creating duplicates.
    """
    try:
        if not file.filename:
            raise FileValidationError("Filename is required")

        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_CSV_EXTENSIONS:
            raise FileValidationError(
                f"Invalid file type '{ext}'. Only CSV files are accepted.",
            )

        try:
            raw_bytes = await file.read()
        except Exception as exc:
            raise FileValidationError(
                f"Failed to read uploaded file: {exc}",
            ) from exc
        finally:
            try:
                await file.close()
            except Exception:
                pass

        if len(raw_bytes) > MAX_CSV_BYTES:
            raise FileValidationError(
                f"File too large ({len(raw_bytes) / (1024 * 1024):.1f} MB). "
                "Max is 10 MB.",
            )

        try:
            csv_content = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                csv_content = raw_bytes.decode("latin-1")
            except Exception as exc:
                raise FileValidationError(
                    f"Could not decode CSV file. Try saving as UTF-8: {exc}",
                ) from exc

        service = CustomerService(db)
        result = await service.import_from_csv(csv_content)

        logger.info(
            "customer_import_api",
            filename=file.filename,
            imported=result.imported,
            skipped=result.skipped,
        )
        return result

    except AppError:
        raise
    except Exception as exc:
        logger.error("customer_import_unexpected_error", error=str(exc))
        raise AppError(
            f"Customer import failed unexpectedly: {exc}",
        ) from exc


@router.post("/{order_id}/match", response_model=CustomerMatchResult)
async def match_order_customer(
    order_id: str,
    *,
    _current_user: CurrentUserDep,
    db: DbSessionDep,
    order_service: OrderServiceDep,
) -> CustomerMatchResult:
    """Run customer matching for a single order and persist the result.

    Safe to call multiple times — subsequent calls overwrite the previous result.
    """
    try:
        order = await order_service.get_by_id(order_id)
        service = CustomerService(db)
        result = await service.match_order_to_customer(order)
        await service.persist_match_result(order, result)

        logger.info(
            "order_customer_match",
            order_id=order_id,
            status=result.status,
            score=result.score,
        )
        return result

    except AppError:
        raise
    except Exception as exc:
        logger.error(
            "match_order_customer_failed", error=str(exc), order_id=order_id,
        )
        raise AppError(
            f"Customer matching failed for order {order_id}: {exc}",
        ) from exc


@router.get("", response_model=list[dict])
async def list_customers(
    _current_user: CurrentUserDep,
    db: DbSessionDep,
    search: str | None = Query(None, max_length=200),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List all customers with optional name search filter."""
    try:
        service = CustomerService(db)
        customers = await service.list_customers(
            limit=limit, offset=offset, search=search,
        )
        return [
            {
                "id": c.id,
                "erp_customer_id": c.erp_customer_id,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
            }
            for c in customers
        ]
    except AppError:
        raise
    except Exception as exc:
        logger.error("list_customers_failed", error=str(exc))
        raise AppError(f"Failed to list customers: {exc}") from exc
