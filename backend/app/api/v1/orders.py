# orders.py
"""Order API routes — upload, list, get, update, approve, reject, download XML, delete.

Changes from initial version:
- serve_pdf() now validates source_filepath is under upload_dir (path traversal guard) (#8)
- Added DELETE /{order_id} endpoint (OrderService.delete_order was implemented but unexposed) (#24)
- All other behaviour preserved.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from urllib.parse import quote

import structlog
from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.api.deps import (
    CurrentUserDep,
    DbSessionDep,
    ERPPushServiceDep,
    OrderServiceDep,
    PDFExtractionDep,
    SettingsDep,
    XMLGeneratorDep,
)
from app.core.exceptions import AppError, FileValidationError
from app.models.order import OrderStatus
from app.schemas.order import (
    ERPPushResponse,
    OrderApproveResponse,
    OrderListItem,
    OrderResponse,
    OrderUpdateRequest,
)
from app.services import blob_storage
from app.services.order_service import OrderService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])

ALLOWED_MIME_TYPES = {"application/pdf"}
ALLOWED_EXTENSIONS = {".pdf"}
UPLOAD_CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MB


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_order_response(order, order_service: OrderService) -> OrderResponse:
    """Build an OrderResponse with confidence data from an Order model."""
    response = OrderResponse.model_validate(order)
    response.field_confidence = order_service.get_field_confidence(order)
    return response


def _validate_upload(file: UploadFile, max_size_bytes: int) -> None:
    """Validate the uploaded file's type and size."""
    if not file.filename:
        raise FileValidationError("Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Invalid file type '{ext}'. Only PDF files are allowed."
        )

    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError(
            f"Invalid content type '{file.content_type}'. Only PDF files are allowed."
        )

    if file.size is not None and file.size > max_size_bytes:
        raise FileValidationError(
            f"File too large ({file.size / (1024 * 1024):.1f} MB). "
            f"Maximum allowed: {max_size_bytes / (1024 * 1024):.0f} MB."
        )


def _sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe basename while preserving extension."""
    basename = Path(filename).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", basename)
    return sanitized or "upload.pdf"


async def _save_upload_to_disk(
    file: UploadFile,
    file_path: Path,
    *,
    max_size_bytes: int,
) -> None:
    """Persist upload in chunks and enforce max size even if UploadFile.size is missing."""
    total_size = 0
    with file_path.open("wb") as buffer:
        while True:
            chunk = await file.read(UPLOAD_CHUNK_SIZE_BYTES)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > max_size_bytes:
                raise FileValidationError(
                    f"File too large ({total_size / (1024 * 1024):.1f} MB). "
                    f"Maximum allowed: {max_size_bytes / (1024 * 1024):.0f} MB."
                )
            buffer.write(chunk)


def _assert_path_within_upload_dir(file_path: Path, upload_dir: str) -> None:
    """Raise FileValidationError if file_path escapes upload_dir (#8).

    Prevents path traversal attacks where a compromised DB row contains
    source_filepath='../../../etc/passwd'.
    """
    resolved = file_path.resolve()
    allowed_root = Path(upload_dir).resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError:
        logger.error(
            "path_traversal_attempt",
            filepath=str(file_path),
            upload_dir=upload_dir,
        )
        raise FileValidationError("Requested file path is outside the upload directory.")


# ── Route Handlers ───────────────────────────────────────────────────────


@router.post("/upload", response_model=OrderResponse, status_code=201)
async def upload_pdf(
    file: UploadFile = File(..., description="PDF order file to parse"),
    *,
    _current_user: CurrentUserDep,
    db: DbSessionDep,
    settings: SettingsDep,
    extraction_service: PDFExtractionDep,
    order_service: OrderServiceDep,
) -> OrderResponse:
    """Upload a PDF order → extract data via AI → create order record.

    Storage strategy (auto-detected from config):
    - Azure Blob Storage (AZURE_STORAGE_CONNECTION_STRING is set):
        1. Stage file to /tmp on the runner
        2. Run extraction from the temp path
        3. Upload to blob; store blob_name in source_filepath
        4. Delete the temp file
    - Local filesystem (development, no connection string set):
        Saves directly to upload_dir as before.
    """
    _validate_upload(file, settings.max_upload_size_bytes)

    safe_filename = _sanitize_filename(file.filename or "unknown.pdf")
    unique_name = f"{uuid.uuid4().hex}_{safe_filename}"

    if not settings.has_llm_config:
        raise FileValidationError(
            "No LLM provider is configured. "
            "For standard OpenAI set OPENAI_API_KEY in your .env. "
            "For Azure OpenAI set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, "
            "and AZURE_OPENAI_DEPLOYMENT."
        )

    if settings.use_azure_storage:
        # ── Azure Blob Storage path ──────────────────────────────────────
        # Stage to /tmp so pdf_extraction (fitz) can open a real file path.
        tmp_path = Path("/tmp") / unique_name
        try:
            await _save_upload_to_disk(
                file, tmp_path, max_size_bytes=settings.max_upload_size_bytes
            )
        except FileValidationError:
            tmp_path.unlink(missing_ok=True)
            raise
        except OSError as exc:
            tmp_path.unlink(missing_ok=True)
            logger.error("file_stage_failed", error=str(exc), filename=file.filename)
            raise FileValidationError(f"Failed to stage uploaded file: {exc}") from exc
        finally:
            await file.close()

        logger.info("pdf_staged_to_tmp", filename=file.filename, tmp_path=str(tmp_path))

        try:
            extracted = await extraction_service.extract(tmp_path)
            raw_json = extracted.model_dump_json()

            # Upload to blob — blob_name is what we store in the DB
            blob_data = tmp_path.read_bytes()
            blob_storage.upload_blob(settings, unique_name, blob_data)

            order = await order_service.create_from_extraction(
                extracted,
                source_filename=file.filename or "unknown.pdf",
                source_filepath=unique_name,  # blob name, not a local path
                raw_json=raw_json,
            )
        except AppError:
            raise
        except Exception as exc:
            logger.error("upload_extraction_failed", error=str(exc), filename=file.filename)
            try:
                order = await order_service.create_failed(
                    source_filename=file.filename or "unknown.pdf",
                    source_filepath=unique_name,
                    error_message=str(exc),
                )
            except Exception as persist_exc:
                logger.error("failed_order_persist_error", error=str(persist_exc))
                raise AppError(
                    f"Extraction failed ({exc}) and could not save error record: {persist_exc}"
                ) from persist_exc
        finally:
            tmp_path.unlink(missing_ok=True)  # Always clean up temp file

    else:
        # ── Local filesystem path (development) ──────────────────────────
        upload_dir = Path(settings.upload_dir)
        file_path = upload_dir / unique_name

        try:
            await _save_upload_to_disk(
                file, file_path, max_size_bytes=settings.max_upload_size_bytes
            )
        except FileValidationError:
            file_path.unlink(missing_ok=True)
            raise
        except OSError as exc:
            file_path.unlink(missing_ok=True)
            logger.error("file_save_failed", error=str(exc), filename=file.filename)
            raise FileValidationError(f"Failed to save uploaded file: {exc}") from exc
        finally:
            await file.close()

        logger.info("pdf_uploaded", filename=file.filename, path=str(file_path))

        try:
            extracted = await extraction_service.extract(file_path)
            raw_json = extracted.model_dump_json()

            order = await order_service.create_from_extraction(
                extracted,
                source_filename=file.filename or "unknown.pdf",
                source_filepath=str(file_path),
                raw_json=raw_json,
            )
        except AppError:
            raise
        except Exception as exc:
            logger.error("upload_extraction_failed", error=str(exc), filename=file.filename)
            try:
                order = await order_service.create_failed(
                    source_filename=file.filename or "unknown.pdf",
                    source_filepath=str(file_path),
                    error_message=str(exc),
                )
            except Exception as persist_exc:
                logger.error("failed_order_persist_error", error=str(persist_exc))
                raise AppError(
                    f"Extraction failed ({exc}) and could not save error record: {persist_exc}"
                ) from persist_exc

    # Auto-match customer (non-blocking)
    try:
        from app.services.customer_service import CustomerService

        customer_svc = CustomerService(db)
        match_result = await customer_svc.match_order_to_customer(order)
        await customer_svc.persist_match_result(order, match_result)
        logger.info(
            "upload_customer_match",
            order_id=order.id,
            match_status=match_result.status,
        )
    except Exception as match_exc:
        logger.warning(
            "upload_customer_match_failed",
            order_id=order.id,
            error=str(match_exc),
        )

    try:
        return _build_order_response(order, order_service)
    except Exception as exc:
        logger.error("response_serialization_failed", error=str(exc), order_id=order.id)
        raise AppError(
            f"Order created but response serialization failed: {exc}"
        ) from exc


@router.get("", response_model=list[OrderListItem])
async def list_orders(
    order_service: OrderServiceDep,
    _current_user: CurrentUserDep,
    status: OrderStatus | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[OrderListItem]:
    """List all orders with optional status filter."""
    try:
        orders = await order_service.list_orders(
            status=status, limit=limit, offset=offset
        )
        return [
            OrderListItem(
                id=order.id,
                status=order.status,
                source_filename=order.source_filename,
                order_number=order.order_number,
                order_date=order.order_date,
                buyer_name=order.buyer_name,
                buyer_reference=order.buyer_reference,
                line_item_count=line_item_count,
                has_low_confidence=order_service.has_low_confidence(order),
                customer_match_status=order.customer_match_status,
                created_at=order.created_at,
            )
            for order, line_item_count in orders
        ]
    except AppError:
        raise
    except Exception as exc:
        logger.error("list_orders_failed", error=str(exc))
        raise AppError(f"Failed to list orders: {exc}") from exc


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    order_service: OrderServiceDep,
    _current_user: CurrentUserDep,
) -> OrderResponse:
    """Get a single order by ID with full details."""
    try:
        order = await order_service.get_by_id(order_id)
        return _build_order_response(order, order_service)
    except AppError:
        raise
    except Exception as exc:
        logger.error("get_order_failed", error=str(exc), order_id=order_id)
        raise AppError(f"Failed to fetch order {order_id}: {exc}") from exc


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: str,
    update: OrderUpdateRequest,
    order_service: OrderServiceDep,
    _current_user: CurrentUserDep,
) -> OrderResponse:
    """Update order fields during review."""
    try:
        order = await order_service.update_order(order_id, update)
        return _build_order_response(order, order_service)
    except AppError:
        raise
    except Exception as exc:
        logger.error("update_order_failed", error=str(exc), order_id=order_id)
        raise AppError(f"Failed to update order {order_id}: {exc}") from exc


@router.delete("/{order_id}", status_code=204)
async def delete_order(
    order_id: str,
    order_service: OrderServiceDep,
    _current_user: CurrentUserDep,
) -> Response:
    """Delete an order record and its associated file (#24).

    Only orders in EXTRACTION_FAILED or REJECTED status may be deleted
    to prevent accidental deletion of orders under review.
    """
    try:
        order = await order_service.get_by_id(order_id)
        deletable_statuses = {OrderStatus.EXTRACTION_FAILED, OrderStatus.REJECTED}
        if order.status not in deletable_statuses:
            raise AppError(
                f"Only orders with status {[s.value for s in deletable_statuses]} "
                f"can be deleted. Current status: '{order.status}'.",
                error_code="ORDER_NOT_DELETABLE",
                status_code=409,
            )
        await order_service.delete_order(order_id)
    except AppError:
        raise
    except Exception as exc:
        logger.error("delete_order_failed", error=str(exc), order_id=order_id)
        raise AppError(f"Failed to delete order {order_id}: {exc}") from exc
    return Response(status_code=204)


@router.post("/{order_id}/approve", response_model=OrderApproveResponse)
async def approve_order(
    order_id: str,
    order_service: OrderServiceDep,
    xml_service: XMLGeneratorDep,
    _current_user: CurrentUserDep,
) -> OrderApproveResponse:
    """Approve an order: generate Monitor XML and persist."""
    try:
        order = await order_service.get_by_id(order_id)
        xml_string = xml_service.generate(order)
        order = await order_service.approve_order(order_id, xml_string)

        return OrderApproveResponse(
            id=order.id,
            status=order.status,
            message="Order approved and XML generated successfully",
            xml_download_url=f"/api/v1/orders/{order.id}/xml",
        )
    except AppError:
        raise
    except Exception as exc:
        logger.error("approve_order_failed", error=str(exc), order_id=order_id)
        raise AppError(f"Failed to approve order {order_id}: {exc}") from exc


@router.post("/{order_id}/reject", response_model=OrderResponse)
async def reject_order(
    order_id: str,
    order_service: OrderServiceDep,
    _current_user: CurrentUserDep,
) -> OrderResponse:
    """Reject an order — returns it for editing and re-approval."""
    try:
        order = await order_service.reject_order(order_id)
        return _build_order_response(order, order_service)
    except AppError:
        raise
    except Exception as exc:
        logger.error("reject_order_failed", error=str(exc), order_id=order_id)
        raise AppError(f"Failed to reject order {order_id}: {exc}") from exc


@router.get("/{order_id}/xml")
async def download_xml(
    order_id: str,
    order_service: OrderServiceDep,
    _current_user: CurrentUserDep,
) -> Response:
    """Download the generated Monitor XML for an approved order."""
    try:
        order = await order_service.get_by_id(order_id)

        if not order.generated_xml:
            raise FileValidationError(
                "No XML has been generated for this order. Approve the order first."
            )

        filename = f"order_{order.order_number or order.id}.xml"
        return Response(
            content=order.generated_xml,
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except AppError:
        raise
    except Exception as exc:
        logger.error("download_xml_failed", error=str(exc), order_id=order_id)
        raise AppError(f"Failed to download XML for order {order_id}: {exc}") from exc


@router.get("/{order_id}/pdf")
async def serve_pdf(
    order_id: str,
    order_service: OrderServiceDep,
    _current_user: CurrentUserDep,
    settings: SettingsDep,
) -> Response:
    """Serve the original uploaded PDF for preview.

    Storage strategy (auto-detected from config):
    - Azure Blob Storage: streams PDF bytes directly from blob.
    - Local filesystem: serves the file via FileResponse (with path traversal guard).
    """
    try:
        order = await order_service.get_by_id(order_id)
        safe_name = quote(order.source_filename, safe="")

        if settings.use_azure_storage:
            # ── Azure Blob Storage ────────────────────────────────────────
            # source_filepath stores the blob name (e.g. "abc123_order.pdf")
            try:
                pdf_bytes = blob_storage.download_blob(settings, order.source_filepath)
            except Exception as exc:
                logger.error("blob_download_failed", error=str(exc), order_id=order_id)
                raise FileValidationError(
                    f"PDF file could not be retrieved from storage: {order.source_filename}"
                ) from exc

            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"inline; filename*=UTF-8''{safe_name}",
                    "Cache-Control": "private, max-age=3600",
                },
            )

        else:
            # ── Local filesystem (development) ────────────────────────────
            pdf_path = Path(order.source_filepath)
            _assert_path_within_upload_dir(pdf_path, settings.upload_dir)

            if not pdf_path.exists():
                raise FileValidationError(
                    f"PDF file not found on disk: {order.source_filename}"
                )

            return FileResponse(
                path=pdf_path,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"inline; filename*=UTF-8''{safe_name}",
                    "Cache-Control": "private, max-age=3600",
                },
            )

    except AppError:
        raise
    except Exception as exc:
        logger.error("serve_pdf_failed", error=str(exc), order_id=order_id)
        raise AppError(f"Failed to serve PDF for order {order_id}: {exc}") from exc


@router.get("/{order_id}/preview-xml")
async def preview_xml(
    order_id: str,
    order_service: OrderServiceDep,
    xml_service: XMLGeneratorDep,
    _current_user: CurrentUserDep,
) -> Response:
    """Generate XML preview without persisting — for side-by-side comparison."""
    try:
        order = await order_service.get_by_id(order_id)
        xml_string = xml_service.generate(order)

        return Response(
            content=xml_string,
            media_type="application/xml",
            headers={"Cache-Control": "no-store"},
        )
    except AppError:
        raise
    except Exception as exc:
        logger.error("preview_xml_failed", error=str(exc), order_id=order_id)
        raise AppError(
            f"Failed to generate XML preview for order {order_id}: {exc}"
        ) from exc


@router.post("/{order_id}/push-to-erp", response_model=ERPPushResponse)
async def push_to_erp(
    order_id: str,
    order_service: OrderServiceDep,
    erp_push_service: ERPPushServiceDep,
    xml_generator: XMLGeneratorDep,
    settings: SettingsDep,
    db: DbSessionDep,
    _current_user: CurrentUserDep,
) -> ERPPushResponse:
    """Push the order XML to ERP System."""
    try:
        order = await order_service.get_by_id(order_id)

        if not order.generated_xml:
            order.generated_xml = xml_generator.generate(order)
            await db.flush()

        if not settings.has_monitor_erp_config:
            return ERPPushResponse(
                success=False,
                message=(
                    "ERP System is not configured. "
                    "Add MONITOR_ERP_BASE_URL and MONITOR_ERP_API_KEY to your .env file."
                ),
                erp_push_status="failed",
            )

        result = await erp_push_service.push_order_xml(
            order.generated_xml, order.order_number
        )

        await order_service.record_erp_push(
            order_id,
            success=result.success,
            status=result.status,
        )

        return ERPPushResponse(
            success=result.success,
            message=result.message,
            erp_push_status=result.status,
        )

    except AppError:
        raise
    except Exception as exc:
        logger.error("push_to_erp_failed", error=str(exc), order_id=order_id)
        raise AppError(f"Failed to push order {order_id} to ERP: {exc}") from exc