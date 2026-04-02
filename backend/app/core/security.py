"""Security utilities — JWT creation/verification and password hashing.

Key changes from initial version:
- Replaced python-jose (CVE-2024-33664) with PyJWT>=2.9.0 (#9)
- Added ``jti`` (JWT ID) claim to access tokens for logout blocklisting (#6)
- Added in-memory token blocklist with TTL-based expiry (#6)
  NOTE: For multi-process / multi-instance deployments replace
  ``_TokenBlocklist`` with a Redis-backed implementation.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError  # noqa: F401 — re-exported for callers

# ── Password Hashing ──────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── Token Blocklist ───────────────────────────────────────────────────────


class _TokenBlocklist:
    """Thread-safe in-memory set of revoked JTI values with TTL expiry.

    Production note: replace with Redis SETEX for multi-process deployments.
    """

    def __init__(self) -> None:
        self._store: dict[str, datetime] = {}  # jti -> expires_at
        self._lock = threading.Lock()

    def add(self, jti: str, expires_at: datetime) -> None:
        """Mark a JTI as revoked until its expiry time."""
        with self._lock:
            self._store[jti] = expires_at
            self._prune()

    def is_revoked(self, jti: str) -> bool:
        """Return True if the JTI is currently on the blocklist."""
        with self._lock:
            expiry = self._store.get(jti)
            if expiry is None:
                return False
            if datetime.now(timezone.utc) > expiry:
                del self._store[jti]
                return False
            return True

    def _prune(self) -> None:
        """Remove expired entries. Must be called under self._lock."""
        now = datetime.now(timezone.utc)
        self._store = {jti: exp for jti, exp in self._store.items() if exp > now}


# Module-level singleton — shared across all requests in the same process.
token_blocklist = _TokenBlocklist()


# ── JWT Tokens ────────────────────────────────────────────────────────────


def create_access_token(
    user_id: str,
    role: str,
    *,
    secret_key: str,
    algorithm: str = "HS256",
    expire_minutes: int = 30,
) -> tuple[str, str]:
    """Create a short-lived JWT access token.

    Returns:
        (encoded_token, jti) — the jti is required for blocklisting on logout.

    Claims: sub, role, jti, exp, iat, type="access"
    """
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "exp": now + timedelta(minutes=expire_minutes),
        "iat": now,
        "type": "access",
    }
    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return token, jti


def decode_access_token(
    token: str,
    *,
    secret_key: str,
    algorithm: str = "HS256",
) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Returns the decoded payload dict on success.
    Raises ``jwt.exceptions.InvalidTokenError`` on failure.
    """
    payload: dict[str, Any] = jwt.decode(
        token,
        secret_key,
        algorithms=[algorithm],
    )
    if payload.get("type") != "access":
        raise InvalidTokenError("Token is not an access token")
    return payload


# ── Refresh Tokens ────────────────────────────────────────────────────────


def generate_refresh_token() -> tuple[str, str]:
    """Generate a cryptographically secure refresh token.

    Returns:
        (raw_token, token_hash) — store only the hash in the database.
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def hash_refresh_token(raw_token: str) -> str:
    """Hash a raw refresh token for database lookup."""
    return hashlib.sha256(raw_token.encode()).hexdigest()
