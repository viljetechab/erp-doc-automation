"""Order service — business logic for order CRUD and workflow transitions."""

from __future__ import annotations

import json

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.models.order import Order, OrderLineItem, OrderStatus
from app.schemas.extraction import ExtractedOrderData
from app.schemas.order import OrderUpdateRequest

logger = structlog.get_logger(__name__)

# Threshold below which a field is considered "low confidence"
LOW_CONFIDENCE_THRESHOLD = 0.8


class OrderService:
    """Handles order persistence, status transitions, and business rules."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_from_extraction(
        self,
        extraction: ExtractedOrderData,
        *,
        source_filename: str,
        source_filepath: str,
        raw_json: str,
        uploaded_by_user_id: str | None = None,
    ) -> Order:
        """Create a new Order from extracted PDF data.

        Sets the status to EXTRACTED and persists all header + line item data.
        """
        # Serialize confidence map
        confidence_json = (
            json.dumps(extraction.field_confidence)
            if extraction.field_confidence
            else None
        )

        order = Order(
            status=OrderStatus.EXTRACTED,
            source_filename=source_filename,
            source_filepath=source_filepath,
            extraction_raw_json=raw_json,
            extraction_confidence_json=confidence_json,
            extraction_notes=extraction.extraction_notes,
            uploaded_by_user_id=uploaded_by_user_id,
            # Header fields
            order_number=extraction.order_number,
            order_date=extraction.order_date,
            buyer_name=extraction.buyer_name,
            buyer_street=extraction.buyer_street,
            buyer_zip_city=extraction.buyer_zip_city,
            buyer_country=extraction.buyer_country,
            buyer_reference=extraction.buyer_reference,
            buyer_customer_number=extraction.buyer_customer_number,
            supplier_edi_code=extraction.supplier_edi_code,
            supplier_name=extraction.supplier_name,
            supplier_street=extraction.supplier_street,
            supplier_zip_city=extraction.supplier_zip_city,
            supplier_country=extraction.supplier_country,
            goods_marking=extraction.goods_marking,
            delivery_name=extraction.delivery_name,
            delivery_street1=extraction.delivery_street1,
            delivery_street2=extraction.delivery_street2,
            delivery_zip_city=extraction.delivery_zip_city,
            delivery_country=extraction.delivery_country,
            delivery_is_buyer_address=extraction.delivery_is_buyer_address,
            delivery_method=extraction.delivery_method,
            transport_payer=extraction.transport_payer,
            payment_terms_days=extraction.payment_terms_days,
            currency=extraction.currency,
        )

        # Create line items — use header delivery_date as fallback if line-level is missing
        header_delivery_date = extraction.delivery_date
        for item in extraction.line_items:
            line_delivery_date = item.delivery_date or header_delivery_date
            line = OrderLineItem(
                row_number=item.row_number,
                part_number=item.part_number,
                supplier_part_number=item.supplier_part_number,
                description=item.description,
                additional_text=item.additional_text,
                quantity=item.quantity,
                unit=item.unit,
                delivery_date=line_delivery_date,
                unit_price=item.unit_price,
                discount=item.discount_percent,
                reference_number=item.reference_number,
            )
            order.line_items.append(line)

        try:
            self._db.add(order)
            await self._db.flush()
        except Exception as exc:
            logger.error("order_create_flush_failed", error=str(exc))
            raise AppError(f"Failed to persist new order: {exc}") from exc

        logger.info(
            "order_created",
            order_id=order.id,
            order_number=order.order_number,
            line_count=len(order.line_items),
        )

        # Re-fetch with selectinload so line_items are eagerly loaded before
        # the object leaves the async session context. Without this, Pydantic
        # triggers a lazy load outside the greenlet which raises MissingGreenlet.
        return await self.get_by_id(order.id)


    async def create_failed(
        self,
        *,
        source_filename: str,
        source_filepath: str,
        error_message: str,
        uploaded_by_user_id: str | None = None,
    ) -> Order:
        """Create an order record when extraction fails, preserving the error."""
        order = Order(
            status=OrderStatus.EXTRACTION_FAILED,
            source_filename=source_filename,
            source_filepath=source_filepath,
            extraction_error=error_message,
            uploaded_by_user_id=uploaded_by_user_id,
        )
        try:
            self._db.add(order)
            await self._db.flush()
        except Exception as exc:
            logger.error("failed_order_persist_error", error=str(exc))
            raise AppError(f"Failed to persist failed order: {exc}") from exc

        logger.warning(
            "order_extraction_failed", order_id=order.id, error=error_message
        )

        # Re-fetch with selectinload to avoid MissingGreenlet on serialization.
        return await self.get_by_id(order.id)

    async def get_by_id(
        self, order_id: str, *, owner_id: str | None = None
    ) -> Order:
        """Fetch an order by ID with eagerly loaded line items.

        Args:
            order_id: UUID of the order to fetch.
            owner_id: When provided, the order must have been uploaded by this
                user.  Orders with ``uploaded_by_user_id=NULL`` (created before
                the ownership column was introduced) are always returned so that
                legacy data is not hidden.

        Raises:
            NotFoundError: If the order does not exist or the caller does not
                own it.
        """
        stmt = (
            select(Order)
            .options(selectinload(Order.line_items))
            .where(Order.id == order_id)
        )
        try:
            result = await self._db.execute(stmt)
            order = result.scalar_one_or_none()
        except Exception as exc:
            raise AppError(
                f"Database query failed for order {order_id}: {exc}",
            ) from exc
        if order is None:
            raise NotFoundError("Order", order_id)
        # Enforce ownership: if the order has an owner AND a caller was given,
        # they must match.  NULL owners are accessible to everyone (legacy rows).
        if (
            owner_id is not None
            and order.uploaded_by_user_id is not None
            and order.uploaded_by_user_id != owner_id
        ):
            raise NotFoundError("Order", order_id)
        return order

    async def list_orders(
        self,
        *,
        status: OrderStatus | None = None,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
    ) -> list[tuple[Order, int]]:
        """List orders with precomputed line-item counts (newest first).

        Args:
            user_id: When provided, only orders uploaded by this user are
                returned.  Omit (or pass ``None``) to return all orders (admin
                use-case or internal callers).
        """
        line_counts = (
            select(
                OrderLineItem.order_id,
                func.count(OrderLineItem.id).label("line_item_count"),
            )
            .group_by(OrderLineItem.order_id)
            .subquery()
        )

        stmt = (
            select(
                Order,
                func.coalesce(line_counts.c.line_item_count, 0).label(
                    "line_item_count"
                ),
            )
            .outerjoin(line_counts, line_counts.c.order_id == Order.id)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(Order.status == status)
        if user_id is not None:
            stmt = stmt.where(Order.uploaded_by_user_id == user_id)

        try:
            result = await self._db.execute(stmt)
            return [
                (order, int(line_item_count)) for order, line_item_count in result.all()
            ]
        except Exception as exc:
            raise AppError(f"Failed to query order list: {exc}") from exc

    async def update_order(self, order_id: str, update: OrderUpdateRequest) -> Order:
        """Update order header fields and/or line items during review.

        Only allows updates when the order is in EXTRACTED or IN_REVIEW status.
        """
        order = await self.get_by_id(order_id)

        allowed_statuses = {
            OrderStatus.EXTRACTED,
            OrderStatus.IN_REVIEW,
            OrderStatus.REJECTED,
        }
        if order.status not in allowed_statuses:
            raise ValidationError(
                f"Cannot edit order in status '{order.status}'. "
                f"Allowed statuses: {', '.join(s.value for s in allowed_statuses)}"
            )

        # Update header fields (only non-None values)
        update_data = update.model_dump(exclude_unset=True, exclude={"line_items"})
        for field, value in update_data.items():
            setattr(order, field, value)

        # Update line items if provided
        if update.line_items is not None:
            # Replace all line items with the new set
            order.line_items.clear()
            for item_schema in update.line_items:
                line = OrderLineItem(
                    order_id=order.id,
                    row_number=item_schema.row_number,
                    part_number=item_schema.part_number,
                    supplier_part_number=item_schema.supplier_part_number,
                    description=item_schema.description,
                    additional_text=item_schema.additional_text,
                    quantity=item_schema.quantity,
                    unit=item_schema.unit,
                    delivery_date=item_schema.delivery_date,
                    unit_price=item_schema.unit_price,
                    discount=item_schema.discount,
                    reference_number=item_schema.reference_number,
                )
                order.line_items.append(line)

        # Transition to IN_REVIEW if first edit
        if order.status == OrderStatus.EXTRACTED:
            order.status = OrderStatus.IN_REVIEW

        try:
            await self._db.flush()
        except Exception as exc:
            raise AppError(f"Failed to persist order update: {exc}") from exc

        logger.info("order_updated", order_id=order.id)

        # Re-fetch with selectinload to avoid MissingGreenlet on serialization.
        return await self.get_by_id(order.id)

    async def approve_order(self, order_id: str, generated_xml: str) -> Order:
        """Approve an order and store the generated XML.

        Transitions the order to APPROVED status.
        """
        order = await self.get_by_id(order_id)

        allowed_statuses = {
            OrderStatus.EXTRACTED,
            OrderStatus.IN_REVIEW,
            OrderStatus.REJECTED,
        }
        if order.status not in allowed_statuses:
            raise ValidationError(
                f"Cannot approve order in status '{order.status}'. "
                f"Must be in EXTRACTED or IN_REVIEW status."
            )

        order.status = OrderStatus.APPROVED
        order.generated_xml = generated_xml

        try:
            await self._db.flush()
        except Exception as exc:
            raise AppError(f"Failed to persist order approval: {exc}") from exc

        logger.info(
            "order_approved",
            order_id=order.id,
            order_number=order.order_number,
        )
        return order

    async def reject_order(self, order_id: str) -> Order:
        """Reject an order — returns it to IN_REVIEW for editing.

        The Reject → Edit → Re-approve flow per meeting requirements.
        """
        order = await self.get_by_id(order_id)

        # Can reject from EXTRACTED or APPROVED (to re-review)
        allowed_statuses = {
            OrderStatus.EXTRACTED,
            OrderStatus.IN_REVIEW,
            OrderStatus.APPROVED,
        }
        if order.status not in allowed_statuses:
            raise ValidationError(
                f"Cannot reject order in status '{order.status}'. "
                f"Allowed statuses: {', '.join(s.value for s in allowed_statuses)}"
            )

        order.status = OrderStatus.REJECTED
        order.generated_xml = None

        try:
            await self._db.flush()
        except Exception as exc:
            raise AppError(f"Failed to persist order rejection: {exc}") from exc

        logger.info("order_rejected", order_id=order.id)
        return order

    async def delete_order(self, order_id: str) -> None:
        """Permanently delete an order and all its line items.

        Raises:
            NotFoundError: If the order does not exist.
        """
        order = await self.get_by_id(order_id)
        try:
            await self._db.delete(order)
            await self._db.flush()
        except Exception as exc:
            raise AppError(f"Failed to delete order {order_id}: {exc}") from exc
        logger.info("order_deleted", order_id=order_id)

    async def record_erp_push(
        self,
        order_id: str,
        *,
        success: bool,
        status: str,
    ) -> Order:
        """Persist the result of an ERP push attempt on the Order row.

        Does NOT change the order's workflow status — the order stays APPROVED
        regardless of whether the push succeeded or failed.

        Args:
            order_id: ID of the order to update.
            success:  Whether the push succeeded.
            status:   'success' or 'failed' (from ERPPushResult.status).
        """
        from datetime import datetime, timezone  # local import to avoid circular deps

        order = await self.get_by_id(order_id)
        order.erp_pushed_at = datetime.now(timezone.utc)
        order.erp_push_status = status

        try:
            await self._db.flush()
        except Exception as exc:
            raise AppError(
                f"Failed to persist ERP push result for order {order_id}: {exc}",
            ) from exc

        logger.info(
            "erp_push_recorded",
            order_id=order_id,
            success=success,
            erp_push_status=status,
        )
        return order

    @staticmethod
    def get_field_confidence(order: Order) -> dict[str, float]:
        """Deserialize confidence JSON from the order."""
        if not order.extraction_confidence_json:
            return {}
        try:
            return json.loads(order.extraction_confidence_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @staticmethod
    def has_low_confidence(order: Order) -> bool:
        """Check if any field has confidence below the threshold."""
        if not order.extraction_confidence_json:
            return False
        try:
            confidence = json.loads(order.extraction_confidence_json)
            return any(
                score < LOW_CONFIDENCE_THRESHOLD for score in confidence.values()
            )
        except (json.JSONDecodeError, TypeError):
            return False