"""FastAPI application factory.

Changes from initial version:
- Added SecurityHeadersMiddleware: CSP, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, Permissions-Policy (#12)
- Added startup warning when app_debug is True in non-development environments (#10)
- Integrated SlowAPI limiter as app state (rate limiting on auth routes) (#2)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.router import v1_router
from app.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import setup_logging
from app.db.init_db import init_db

# Configure logging before any module-level get_logger() calls
setup_logging(debug=get_settings().app_debug)

logger = structlog.get_logger(__name__)

# ── Rate Limiter (shared across routes) ──────────────────────────────────

limiter = Limiter(key_func=get_remote_address)


# ── Security Headers Middleware ───────────────────────────────────────────

async def security_headers_middleware(request: Request, call_next: object) -> Response:
    """Add security headers to every HTTP response (#12)."""
    response: Response = await call_next(request)  # type: ignore[operator]
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' https://graph.microsoft.com data:; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline';"
    )
    return response


# ── Lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — runs on startup and shutdown."""
    settings = get_settings()
    logger.info("application_starting", env=settings.app_env, cors_origins=settings.cors_origins)

    if settings.app_debug and settings.app_env != "development":
        logger.warning(
            "app_debug_enabled_in_production",
            message="APP_DEBUG=true leaks internal error details. Set APP_DEBUG=false in production.",
        )

    if settings.jwt_secret_key == "CHANGE-ME-IN-PRODUCTION" and settings.app_env != "development":
        logger.warning(
            "insecure_jwt_secret",
            message="JWT_SECRET_KEY is using the default insecure value. Set a proper secret before deploying.",
        )

    # Create database tables (POC convenience — use Alembic in production)
    await init_db()

    yield

    logger.info("application_shutting_down")


# ── App Factory ───────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="OrderFlow Pro — Order Pipeline",
        description=(
            "PDF order intake, AI extraction, review/edit, "
            "and Monitor ERP XML generation."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Rate limiter state (accessed by route decorators via request.app.state)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # CORS — must come before security headers so credentials work.
    # With withCredentials/cookies, browsers require Access-Control-Allow-Credentials: true
    # and an explicit origin (not *). If preflight shows ACAC empty on Azure App Service,
    # clear API → CORS origins in the Azure Portal so platform CORS does not override this.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers on all responses
    app.middleware("http")(security_headers_middleware)

    # Exception handlers
    register_error_handlers(app)

    # Routes
    app.include_router(v1_router)

    return app


# Module-level app instance for uvicorn
app = create_app()
