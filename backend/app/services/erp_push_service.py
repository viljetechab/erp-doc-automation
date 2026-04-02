"""ERP System push service — sends generated ORDERS420 XML to the ERP System REST API.

Responsibilities (single):
    POST the stored XML string to ERP System and return a structured result.

Design decisions:
- Uses httpx.AsyncClient for non-blocking I/O (consistent with rest of app).
- Returns ERPPushResult (not raises) for all failure cases so the route
  can persist the result and surface a useful message to the UI.
- When credentials are not configured, returns an error immediately —
  no HTTP call is made (fail-fast, no confusing timeouts or 401s).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ERP push outcome statuses — stored on the Order row
ERP_STATUS_SUCCESS = "success"
ERP_STATUS_FAILED = "failed"


@dataclass(frozen=True)
class ERPPushResult:
    """Structured outcome of an ERP push attempt."""

    success: bool
    message: str
    status: str  # ERP_STATUS_SUCCESS | ERP_STATUS_FAILED
    http_status_code: int | None = None


class ERPPushService:
    """Pushes ORDERS420 XML to the ERP System REST API.

    Lifecycle: singleton (settings are fixed at startup). Inject via deps.py.
    """

    def __init__(self, settings) -> None:
        self._base_url: str = settings.monitor_erp_base_url.rstrip("/")
        self._api_key: str = settings.monitor_erp_api_key
        self._timeout: int = settings.monitor_erp_timeout_seconds
        self._configured: bool = settings.has_monitor_erp_config

    # ── Public API ────────────────────────────────────────────────────────

    async def push_order_xml(
        self, xml_string: str, order_number: str | None
    ) -> ERPPushResult:
        """POST the ORDERS420 XML to ERP System.

        Args:
            xml_string:   Full UTF-8 XML string (already generated and stored).
            order_number: Human-readable order number for log context.

        Returns:
            ERPPushResult — always returns, never raises.
        """
        if not self._configured:
            logger.warning(
                "erp_push_skipped_no_config",
                order_number=order_number,
            )
            return ERPPushResult(
                success=False,
                message=(
                    "ERP System is not configured. "
                    "Set MONITOR_ERP_BASE_URL and MONITOR_ERP_API_KEY in your .env file."
                ),
                status=ERP_STATUS_FAILED,
            )

        if not xml_string or not xml_string.strip():
            return ERPPushResult(
                success=False,
                message="No XML to push — approve the order to generate XML first.",
                status=ERP_STATUS_FAILED,
            )

        endpoint = f"{self._base_url}/orders"
        headers = {
            "Content-Type": "application/xml; charset=utf-8",
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    endpoint,
                    content=xml_string.encode("utf-8"),
                    headers=headers,
                )

            if response.is_success:
                logger.info(
                    "erp_push_success",
                    order_number=order_number,
                    http_status=response.status_code,
                )
                return ERPPushResult(
                    success=True,
                    message=f"Order pushed to ERP System successfully (HTTP {response.status_code}).",
                    status=ERP_STATUS_SUCCESS,
                    http_status_code=response.status_code,
                )

            # Non-2xx — log and surface a human-readable error
            logger.warning(
                "erp_push_http_error",
                order_number=order_number,
                http_status=response.status_code,
                response_body=response.text[:500],
            )
            return ERPPushResult(
                success=False,
                message=(
                    f"ERP System rejected the request "
                    f"(HTTP {response.status_code}): {response.text[:200]}"
                ),
                status=ERP_STATUS_FAILED,
                http_status_code=response.status_code,
            )

        except httpx.TimeoutException:
            logger.error(
                "erp_push_timeout",
                order_number=order_number,
                timeout_seconds=self._timeout,
            )
            return ERPPushResult(
                success=False,
                message=(
                    f"ERP System did not respond within {self._timeout} seconds. "
                    "Check connectivity and try again."
                ),
                status=ERP_STATUS_FAILED,
            )

        except httpx.RequestError as exc:
            logger.error(
                "erp_push_connection_error",
                order_number=order_number,
                error=str(exc),
            )
            return ERPPushResult(
                success=False,
                message=f"Could not reach ERP System: {exc}",
                status=ERP_STATUS_FAILED,
            )
