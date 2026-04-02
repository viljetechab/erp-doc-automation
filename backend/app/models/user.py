"""User model — stores local and OAuth-authenticated users."""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    """Application user — supports both local (email/password) and OAuth login.

    Attributes:
        email:           Unique email address (login identifier).
        hashed_password: Bcrypt hash — None for OAuth-only accounts.
        display_name:    Human-readable name shown in the UI.
        avatar_url:      Profile picture URL (populated by OAuth providers).
        role:            Authorization role — 'admin' or 'user'.
        auth_provider:   How the account was created — 'microsoft'.
        provider_id:     External user ID from the OAuth provider (unique per provider).
        is_active:       Soft-delete flag — inactive users cannot log in.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    auth_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local"
    )
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r} provider={self.auth_provider!r}>"
