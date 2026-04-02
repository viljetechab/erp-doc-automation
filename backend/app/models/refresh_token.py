"""Refresh token model — tracks issued refresh tokens for secure rotation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class RefreshToken(Base, UUIDMixin, TimestampMixin):
    """Persisted refresh token — stored as a SHA-256 hash, never raw.

    Token rotation: when a refresh token is used, the old one is revoked
    and a new one is issued. This limits the damage window if a token leaks.

    Attributes:
        user_id:    FK to users.id — owner of this token.
        token_hash: SHA-256 hex digest of the raw token value.
        expires_at: Absolute expiry timestamp (UTC).
        revoked:    Set to True when the token is rotated or explicitly logged out.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id!r} user_id={self.user_id!r} revoked={self.revoked}>"
