"""Tests for authentication — security utilities, auth service, and edge cases."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


# ── Password Hashing ─────────────────────────────────────────────────────


class TestPasswordHashing:
    """Tests for bcrypt password hashing."""

    def test_hash_and_verify_succeeds(self):
        plain = "my-secure-password-2024"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password_fails(self):
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Bcrypt uses a different salt each time."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2  # Different salts
        assert verify_password("same-password", h1) is True
        assert verify_password("same-password", h2) is True


# ── JWT Access Tokens ─────────────────────────────────────────────────────


class TestJWTTokens:
    """Tests for JWT creation and decoding."""

    SECRET = "test-secret-key-for-unit-tests"
    ALGORITHM = "HS256"

    def test_create_and_decode_access_token(self):
        token = create_access_token(
            "user-123",
            "admin",
            secret_key=self.SECRET,
            algorithm=self.ALGORITHM,
            expire_minutes=30,
        )
        payload = decode_access_token(
            token,
            secret_key=self.SECRET,
            algorithm=self.ALGORITHM,
        )
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_decode_with_wrong_secret_raises(self):
        token = create_access_token(
            "user-123",
            "user",
            secret_key=self.SECRET,
            algorithm=self.ALGORITHM,
        )
        from jose import JWTError

        with pytest.raises(JWTError):
            decode_access_token(
                token,
                secret_key="wrong-secret",
                algorithm=self.ALGORITHM,
            )

    def test_expired_token_raises(self):
        """Token with 0-minute expiry should be expired immediately."""
        from jose import JWTError, jwt

        # Create a token that expired 1 minute ago
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-123",
            "role": "user",
            "exp": now - timedelta(minutes=1),
            "iat": now - timedelta(minutes=2),
            "type": "access",
        }
        token = jwt.encode(payload, self.SECRET, algorithm=self.ALGORITHM)
        with pytest.raises(JWTError):
            decode_access_token(
                token,
                secret_key=self.SECRET,
                algorithm=self.ALGORITHM,
            )


# ── Refresh Tokens ────────────────────────────────────────────────────────


class TestRefreshTokens:
    """Tests for refresh token generation and hashing."""

    def test_generate_returns_token_and_hash(self):
        raw, hashed = generate_refresh_token()
        assert len(raw) > 20  # URL-safe base64
        assert len(hashed) == 64  # SHA-256 hex digest

    def test_hash_is_deterministic(self):
        raw, hashed = generate_refresh_token()
        assert hash_refresh_token(raw) == hashed

    def test_different_tokens_each_time(self):
        raw1, _ = generate_refresh_token()
        raw2, _ = generate_refresh_token()
        assert raw1 != raw2

    def test_hash_does_not_match_wrong_token(self):
        _, hashed = generate_refresh_token()
        wrong_hash = hash_refresh_token("completely-different-token")
        assert wrong_hash != hashed
