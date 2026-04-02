"""Auth service — token refresh, logout, OAuth and email/password user management."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, AuthenticationError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    token_blocklist,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = structlog.get_logger(__name__)

_ALLOWED_AVATAR_DOMAINS = re.compile(r"^https://graph\.microsoft\.com/")


def _sanitize_avatar_url(url: str | None) -> str | None:
    if not url:
        return None
    if _ALLOWED_AVATAR_DOMAINS.match(url):
        return url
    logger.warning("avatar_url_rejected", url=url[:100])
    return None


class AuthService:
    """Handles all authentication workflows."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Email / Password ──────────────────────────────────────────────────

    async def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        secret_key: str,
        algorithm: str,
        access_expire_minutes: int,
        refresh_expire_days: int,
    ) -> tuple[str, str, int, User]:
        """Create a new local user account and issue tokens.

        Raises:
            AppError: If email is already registered.
        """
        normalized = email.lower().strip()
        existing = await self._get_user_by_email(normalized)
        if existing:
            raise AppError("An account with this email already exists.")

        user = User(
            email=normalized,
            hashed_password=hash_password(password),
            display_name=display_name.strip(),
            avatar_url=None,
            auth_provider="local",
            provider_id=None,
            role="user",
            is_active=True,
        )
        self._db.add(user)
        await self._db.flush()
        logger.info("local_user_registered", user_id=user.id)

        return await self._issue_tokens(
            user,
            secret_key=secret_key,
            algorithm=algorithm,
            access_expire_minutes=access_expire_minutes,
            refresh_expire_days=refresh_expire_days,
        )

    async def login_with_password(
        self,
        *,
        email: str,
        password: str,
        secret_key: str,
        algorithm: str,
        access_expire_minutes: int,
        refresh_expire_days: int,
    ) -> tuple[str, str, int, User]:
        """Verify credentials and issue tokens.

        Raises:
            AuthenticationError: On bad credentials or inactive account.
        """
        normalized = email.lower().strip()
        user = await self._get_user_by_email(normalized)

        # Use constant-time comparison path even on miss to prevent user enumeration
        _DUMMY_HASH = "$2b$12$notarealhashjustpadding000000000000000000000000000000000"
        hashed = user.hashed_password if user else _DUMMY_HASH

        if not verify_password(password, hashed) or not user:
            raise AuthenticationError("Invalid email or password.")

        if not user.is_active:
            raise AuthenticationError("This account has been deactivated.")

        if user.hashed_password is None:
            raise AuthenticationError(
                "This account was created via OAuth. Please sign in with Microsoft."
            )

        logger.info("local_user_login", user_id=user.id)
        return await self._issue_tokens(
            user,
            secret_key=secret_key,
            algorithm=algorithm,
            access_expire_minutes=access_expire_minutes,
            refresh_expire_days=refresh_expire_days,
        )

    # ── Token Refresh ─────────────────────────────────────────────────────

    async def refresh(
        self,
        *,
        raw_token: str,
        secret_key: str,
        algorithm: str,
        access_expire_minutes: int,
        refresh_expire_days: int,
    ) -> tuple[str, str, int]:
        """Rotate a refresh token — revoke old, issue new pair."""
        token_hash = hash_refresh_token(raw_token)
        result = await self._db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored = result.scalar_one_or_none()

        if not stored:
            raise AuthenticationError("Invalid refresh token.")
        if stored.revoked:
            await self._revoke_all_user_tokens(stored.user_id)
            raise AuthenticationError("Refresh token has been revoked. All sessions terminated.")
        if stored.expires_at < datetime.now(timezone.utc):
            raise AuthenticationError("Refresh token has expired.")

        stored.revoked = True

        user_result = await self._db.execute(select(User).where(User.id == stored.user_id))
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active:
            raise AuthenticationError("User account not found or deactivated.")

        access_token, _jti = create_access_token(
            user.id, user.role,
            secret_key=secret_key, algorithm=algorithm, expire_minutes=access_expire_minutes,
        )
        new_raw, new_hash = generate_refresh_token()
        await self._store_refresh_token(user.id, new_hash, expire_days=refresh_expire_days)

        logger.info("token_refreshed", user_id=user.id)
        return access_token, new_raw, access_expire_minutes * 60

    # ── Logout ────────────────────────────────────────────────────────────

    async def logout(
        self,
        raw_token: str,
        access_jti: str | None = None,
        access_expire_minutes: int = 30,
    ) -> None:
        """Revoke a refresh token and blocklist the access token JTI."""
        token_hash = hash_refresh_token(raw_token)
        result = await self._db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored = result.scalar_one_or_none()
        if stored:
            stored.revoked = True
            logger.info("user_logged_out", user_id=stored.user_id)

        if access_jti:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=access_expire_minutes)
            token_blocklist.add(access_jti, expires_at)

    # ── OAuth User Management ─────────────────────────────────────────────

    async def get_or_create_oauth_user(
        self,
        *,
        provider: str,
        email: str,
        display_name: str,
        provider_id: str,
        avatar_url: str | None = None,
        secret_key: str,
        algorithm: str,
        access_expire_minutes: int,
        refresh_expire_days: int,
    ) -> tuple[str, str, int, User]:
        """Find or create a user from OAuth provider data, then issue tokens."""
        normalized_email = email.lower().strip()
        safe_avatar = _sanitize_avatar_url(avatar_url)

        user = await self._get_user_by_email(normalized_email)

        if user:
            if not user.provider_id:
                user.provider_id = provider_id
            if safe_avatar:
                user.avatar_url = safe_avatar
        else:
            user = User(
                email=normalized_email,
                hashed_password=None,
                display_name=display_name,
                avatar_url=safe_avatar,
                auth_provider=provider,
                provider_id=provider_id,
                role="user",
                is_active=True,
            )
            self._db.add(user)
            await self._db.flush()
            logger.info("oauth_user_created", user_id=user.id, provider=provider)

        logger.info("oauth_login", user_id=user.id, provider=provider)
        return await self._issue_tokens(
            user,
            secret_key=secret_key,
            algorithm=algorithm,
            access_expire_minutes=access_expire_minutes,
            refresh_expire_days=refresh_expire_days,
        )

    # ── User Lookup ───────────────────────────────────────────────────────

    async def get_user_by_id(self, user_id: str) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        return await self._get_user_by_email(email)

    # ── Private Helpers ───────────────────────────────────────────────────

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self._db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none()

    async def _issue_tokens(
        self,
        user: User,
        *,
        secret_key: str,
        algorithm: str,
        access_expire_minutes: int,
        refresh_expire_days: int,
    ) -> tuple[str, str, int, User]:
        access_token, _jti = create_access_token(
            user.id, user.role,
            secret_key=secret_key, algorithm=algorithm, expire_minutes=access_expire_minutes,
        )
        raw_refresh, token_hash = generate_refresh_token()
        await self._store_refresh_token(user.id, token_hash, expire_days=refresh_expire_days)
        return access_token, raw_refresh, access_expire_minutes * 60, user

    async def _store_refresh_token(self, user_id: str, token_hash: str, *, expire_days: int) -> None:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expire_days),
            revoked=False,
        )
        self._db.add(token)
        await self._db.flush()

    async def _revoke_all_user_tokens(self, user_id: str) -> None:
        result = await self._db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,  # noqa: E712
            )
        )
        for token in result.scalars().all():
            token.revoked = True
        logger.warning("all_tokens_revoked", user_id=user_id)
