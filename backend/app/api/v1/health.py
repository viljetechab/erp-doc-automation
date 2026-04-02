"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Simple liveness check."""
    return {"status": "ok", "service": "orderflow-pro-backend"}
