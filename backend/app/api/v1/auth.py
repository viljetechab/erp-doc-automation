"""Auth API routes — email/password, Microsoft OAuth, token refresh, logout.

Do not use ``from __future__ import annotations`` in this module: with FastAPI
0.115 and SlowAPI's ``@limiter.limit``, postponed evaluation breaks JSON body
binding on these routes (422 responses expecting body fields in the query).

Token storage:
  Tokens are set as HttpOnly, SameSite=Lax cookies by the backend.
  JavaScript cannot read HttpOnly cookies — XSS cannot steal them.

  Cookie names:  of_access_token   (short-lived, Path=/)
                 of_refresh_token  (long-lived,  Path=/api/v1/auth)

  Secure=False in development (http). Secure=True everywhere else.
"""

import secrets

import structlog
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import AuthServiceDep, CurrentUserDep, OAuthServiceDep, SettingsDep
from app.core.exceptions import AppError, AuthenticationError
from app.schemas.auth import (
    AuthStatusResponse,
    EmailPasswordLoginRequest,
    OAuthCallbackRequest,
    RegisterRequest,
    UserResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

_ACCESS_COOKIE = "of_access_token"
_REFRESH_COOKIE = "of_refresh_token"


def _set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    access_expire_minutes: int,
    refresh_expire_days: int,
    secure: bool,
) -> None:
    response.set_cookie(
        key=_ACCESS_COOKIE, value=access_token,
        httponly=True, secure=secure, samesite="lax",
        max_age=access_expire_minutes * 60, path="/",
    )
    response.set_cookie(
        key=_REFRESH_COOKIE, value=refresh_token,
        httponly=True, secure=secure, samesite="lax",
        max_age=refresh_expire_days * 86_400, path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(_ACCESS_COOKIE, path="/")
    response.delete_cookie(_REFRESH_COOKIE, path="/api/v1/auth")


# ── Email / Password ──────────────────────────────────────────────────────


@router.post("/register", response_model=AuthStatusResponse, status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: RegisterRequest,
    auth_service: AuthServiceDep,
    settings: SettingsDep,
) -> Response:
    """Create a new local account."""
    try:
        access, refresh, _, user = await auth_service.register(
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            access_expire_minutes=settings.jwt_access_token_expire_minutes,
            refresh_expire_days=settings.jwt_refresh_token_expire_days,
        )
        resp = JSONResponse(
            content={"user": UserResponse.model_validate(user).model_dump(mode="json")},
            status_code=201,
        )
        _set_auth_cookies(
            resp,
            access_token=access, refresh_token=refresh,
            access_expire_minutes=settings.jwt_access_token_expire_minutes,
            refresh_expire_days=settings.jwt_refresh_token_expire_days,
            secure=settings.is_production,
        )
        return resp
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Registration failed: {exc}") from exc


@router.post("/login", response_model=AuthStatusResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: EmailPasswordLoginRequest,
    auth_service: AuthServiceDep,
    settings: SettingsDep,
) -> Response:
    """Sign in with email and password."""
    try:
        access, refresh, _, user = await auth_service.login_with_password(
            email=payload.email,
            password=payload.password,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            access_expire_minutes=settings.jwt_access_token_expire_minutes,
            refresh_expire_days=settings.jwt_refresh_token_expire_days,
        )
        resp = JSONResponse(
            content={"user": UserResponse.model_validate(user).model_dump(mode="json")},
        )
        _set_auth_cookies(
            resp,
            access_token=access, refresh_token=refresh,
            access_expire_minutes=settings.jwt_access_token_expire_minutes,
            refresh_expire_days=settings.jwt_refresh_token_expire_days,
            secure=settings.is_production,
        )
        return resp
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Login failed: {exc}") from exc


# ── Refresh ───────────────────────────────────────────────────────────────


@router.post("/refresh")
@limiter.limit("20/minute")
async def refresh_token(
    request: Request,
    auth_service: AuthServiceDep,
    settings: SettingsDep,
) -> Response:
    """Silently rotate tokens using the HttpOnly refresh cookie."""
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if not raw_refresh:
        raise AuthenticationError("No refresh token cookie present. Please log in again.")
    try:
        access, refresh, _ = await auth_service.refresh(
            raw_token=raw_refresh,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            access_expire_minutes=settings.jwt_access_token_expire_minutes,
            refresh_expire_days=settings.jwt_refresh_token_expire_days,
        )
        resp = JSONResponse(content={"ok": True})
        _set_auth_cookies(
            resp,
            access_token=access, refresh_token=refresh,
            access_expire_minutes=settings.jwt_access_token_expire_minutes,
            refresh_expire_days=settings.jwt_refresh_token_expire_days,
            secure=settings.is_production,
        )
        return resp
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Token refresh failed: {exc}") from exc


# ── Logout ────────────────────────────────────────────────────────────────


@router.post("/logout")
async def logout(
    request: Request,
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
    settings: SettingsDep,
) -> Response:
    """Revoke tokens and expire both cookies."""
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    raw_access = request.cookies.get(_ACCESS_COOKIE)

    jti: str | None = None
    if raw_access:
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(
                raw_access,
                secret_key=settings.jwt_secret_key,
                algorithm=settings.jwt_algorithm,
            )
            jti = payload.get("jti")
        except Exception:
            pass

    if raw_refresh:
        try:
            await auth_service.logout(
                raw_refresh,
                access_jti=jti,
                access_expire_minutes=settings.jwt_access_token_expire_minutes,
            )
        except AppError:
            pass

    resp = Response(status_code=204)
    _clear_auth_cookies(resp)
    return resp


# ── Current user ──────────────────────────────────────────────────────────


@router.get("/me", response_model=AuthStatusResponse)
async def get_me(current_user: CurrentUserDep) -> AuthStatusResponse:
    return AuthStatusResponse(user=UserResponse.model_validate(current_user))


# ── Microsoft OAuth ───────────────────────────────────────────────────────

_pending_oauth_states: dict[str, str] = {}
_MAX_PENDING_STATES = 500


def _generate_oauth_state(provider: str) -> str:
    state = secrets.token_urlsafe(32)
    if len(_pending_oauth_states) >= _MAX_PENDING_STATES:
        keys = list(_pending_oauth_states.keys())[: _MAX_PENDING_STATES // 2]
        for k in keys:
            del _pending_oauth_states[k]
    _pending_oauth_states[state] = provider
    return state


def _consume_oauth_state(state: str, expected_provider: str) -> None:
    provider = _pending_oauth_states.pop(state, None)
    if provider is None:
        raise AuthenticationError("Invalid or expired OAuth state. Please retry login.")
    if provider != expected_provider:
        raise AuthenticationError("OAuth state provider mismatch. Please retry login.")


@router.get("/microsoft/url")
async def microsoft_auth_url(oauth_service: OAuthServiceDep) -> dict:
    try:
        state = _generate_oauth_state("microsoft")
        url = oauth_service.get_microsoft_auth_url(state=state)
        return {"url": url, "state": state}
    except Exception as exc:
        raise AppError(f"Failed to generate Microsoft auth URL: {exc}") from exc


@router.post("/microsoft/callback", response_model=AuthStatusResponse)
@limiter.limit("10/minute")
async def microsoft_callback(
    request: Request,
    payload: OAuthCallbackRequest,
    auth_service: AuthServiceDep,
    oauth_service: OAuthServiceDep,
    settings: SettingsDep,
) -> Response:
    try:
        _consume_oauth_state(payload.state, "microsoft")
        user_info = await oauth_service.exchange_microsoft_code(payload.code)
        email = user_info.get("mail") or user_info.get("userPrincipalName")
        if not email:
            raise AuthenticationError("Microsoft did not provide an email address.")
        access, refresh, _, user = await auth_service.get_or_create_oauth_user(
            provider="microsoft",
            email=email,
            display_name=user_info.get("displayName", email),
            provider_id=user_info.get("id", ""),
            avatar_url=None,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            access_expire_minutes=settings.jwt_access_token_expire_minutes,
            refresh_expire_days=settings.jwt_refresh_token_expire_days,
        )
        resp = JSONResponse(
            content={"user": UserResponse.model_validate(user).model_dump(mode="json")},
        )
        _set_auth_cookies(
            resp,
            access_token=access, refresh_token=refresh,
            access_expire_minutes=settings.jwt_access_token_expire_minutes,
            refresh_expire_days=settings.jwt_refresh_token_expire_days,
            secure=settings.is_production,
        )
        return resp
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Microsoft login failed: {exc}") from exc
