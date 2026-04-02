"""OAuth service — handles Microsoft authorization code exchange.

Google OAuth has been removed. Only Microsoft is supported.

Flow:
1. Frontend redirects user to Microsoft authorization URL
2. Microsoft redirects back with a code
3. Backend exchanges code for an access token via Microsoft identity platform
4. Backend uses access token to fetch user profile from Microsoft Graph
5. auth_service.get_or_create_oauth_user() handles the rest
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
import structlog

from app.config import Settings

logger = structlog.get_logger(__name__)

OAUTH_HTTP_TIMEOUT = 15.0


class OAuthService:
    """Stateless OAuth helper — exchanges Microsoft codes for user info."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ── Microsoft OAuth 2.0 ───────────────────────────────────────────────

    def get_microsoft_auth_url(self, state: str | None = None) -> str:
        """Build the Microsoft OAuth consent screen URL."""
        tenant = self._settings.microsoft_tenant_id
        params = {
            "client_id": self._settings.microsoft_client_id,
            "redirect_uri": self._settings.microsoft_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile User.Read",
            "response_mode": "query",
        }
        if state:
            params["state"] = state
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{urlencode(params)}"

    async def exchange_microsoft_code(self, code: str) -> dict:
        """Exchange a Microsoft authorization code for user info.

        Returns:
            dict with keys: mail (or userPrincipalName), displayName, id

        Raises:
            AppError on failure.
        """
        from app.core.exceptions import AppError

        tenant = self._settings.microsoft_tenant_id

        async with httpx.AsyncClient(timeout=OAUTH_HTTP_TIMEOUT) as client:
            # 1. Exchange code for tokens
            token_resp = await client.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data={
                    "client_id": self._settings.microsoft_client_id,
                    "client_secret": self._settings.microsoft_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self._settings.microsoft_redirect_uri,
                    "scope": "openid email profile User.Read",
                },
            )
            if token_resp.status_code != 200:
                logger.error("microsoft_token_exchange_failed", body=token_resp.text)
                raise AppError(
                    "Failed to exchange Microsoft authorization code.",
                    error_code="OAUTH_ERROR",
                    status_code=400,
                )
            tokens = token_resp.json()
            access_token = tokens.get("access_token")
            if not access_token:
                raise AppError(
                    "Microsoft did not return an access token.",
                    error_code="OAUTH_ERROR",
                    status_code=400,
                )

            # 2. Fetch user profile from Microsoft Graph
            profile_resp = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if profile_resp.status_code != 200:
                logger.error("microsoft_profile_failed", body=profile_resp.text)
                raise AppError(
                    "Failed to fetch Microsoft user profile.",
                    error_code="OAUTH_ERROR",
                    status_code=400,
                )
            return profile_resp.json()
