"""V1 API router — aggregates all v1 route modules."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.articles import router as articles_router
from app.api.v1.auth import router as auth_router
from app.api.v1.customers import router as customers_router
from app.api.v1.health import router as health_router
from app.api.v1.orders import router as orders_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health_router)
v1_router.include_router(auth_router)
v1_router.include_router(articles_router)
v1_router.include_router(customers_router)
v1_router.include_router(orders_router)
