"""Auth request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


# ── Requests ──────────────────────────────────────────────────────────────


class OAuthCallbackRequest(BaseModel):
    """OAuth authorization code exchange with CSRF state validation."""
    code: str
    state: str


class EmailPasswordLoginRequest(BaseModel):
    """Email + password login."""
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """New local account registration."""
    email: EmailStr
    password: str
    display_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("display_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Display name cannot be blank.")
        return v.strip()


# ── Responses ─────────────────────────────────────────────────────────────


class UserResponse(BaseModel):
    """Public user profile."""
    id: str
    email: str
    display_name: str
    avatar_url: str | None
    role: str
    auth_provider: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthStatusResponse(BaseModel):
    """Response for /auth/me and login endpoints."""
    user: UserResponse
