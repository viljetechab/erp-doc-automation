"""FastAPI exception handlers that return structured JSON error responses."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError

logger = structlog.get_logger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Attach exception handlers to the FastAPI app instance."""

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "application_error",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        import traceback

        tb = traceback.format_exc()
        logger.exception("unhandled_error", error=str(exc), traceback=tb)

        # Never expose internal tracebacks in the API response — log them instead.
        # The full traceback is available in structured logs for debugging.
        from app.config import get_settings
        is_debug = get_settings().app_debug

        # In production, hide internal error details from API callers for security.
        # In debug mode, surface the real exception message to aid development.
        message = str(exc) if is_debug else "An unexpected internal error occurred."

        content: dict = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": message,
            }
        }
        if is_debug:
            content["error"]["detail"] = tb

        return JSONResponse(status_code=500, content=content)