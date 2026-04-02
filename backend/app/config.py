"""Application configuration loaded from environment variables.

Only Microsoft OAuth is supported for authentication.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_DEFAULT = "CHANGE-ME-IN-PRODUCTION"
_MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Centralised application settings.

    All values can be overridden via environment variables or a `.env` file
    located in the backend root directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    app_env: str = Field(default="development", description="Runtime environment")
    app_debug: bool = Field(default=False, description="Enable debug mode")
    app_host: str = Field(default="0.0.0.0", description="Server bind host")
    app_port: int = Field(default=8000, description="Server bind port")

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/orderflow_pro.db",
        description="SQLAlchemy async database URL",
    )

    # ── OpenAI (standard — used in development / local) ──────────────────
    openai_api_key: str = Field(
        default="",
        description="Standard OpenAI API key. Leave blank when using Azure OpenAI.",
    )
    openai_model: str = Field(
        default="gpt-4o",
        description="Standard OpenAI model name (e.g. gpt-4o). Ignored when using Azure OpenAI.",
    )
    openai_max_tokens: int = Field(
        default=8192, description="Max tokens for extraction response (applies to both providers)."
    )

    # ── Azure OpenAI (production) ─────────────────────────────────────────
    azure_openai_api_key: str = Field(
        default="",
        description="Azure OpenAI API key (from Azure Portal → resource → Keys and Endpoint).",
    )
    azure_openai_endpoint: str = Field(
        default="",
        description=(
            "Azure OpenAI endpoint URL, e.g. https://MY-RESOURCE.openai.azure.com . "
            "Setting this value activates Azure OpenAI — standard OpenAI is ignored."
        ),
    )
    azure_openai_deployment: str = Field(
        default="",
        description=(
            "Azure OpenAI deployment name (the name you gave when deploying a model "
            "in Azure AI Studio / Azure OpenAI Studio). This is used as the model "
            "parameter in every API call."
        ),
    )
    azure_openai_api_version: str = Field(
        default="2024-08-01-preview",
        description="Azure OpenAI API version string (e.g. 2024-08-01-preview).",
    )

    # ── Supplier Defaults ────────────────────────────────────────────────
    # These are fallback values used when the PDF extraction finds no supplier info.
    # Set these to match the actual supplier for each client deployment.
    supplier_name: str = Field(default="Demo Supplier Ltd")
    supplier_edi_code: str = Field(default="0000000")
    supplier_street: str = Field(default="1 Business Street")
    supplier_zip_city: str = Field(default="00000 DEMO CITY")
    supplier_country: str = Field(default="Demo Country")

    # ── ERP Push Integration ────────────────────────────────────────────
    # Supports Monitor ERP and compatible REST-based ERP systems.
    # The "Push to ERP" button is safely disabled when these are blank.
    monitor_erp_base_url: str = Field(
        default="",
        alias="erp_base_url",
        description="ERP REST API base URL (e.g. https://erp.example.com/api)",
        validation_alias="erp_base_url",
    )
    monitor_erp_api_key: str = Field(
        default="",
        alias="erp_api_key",
        description="ERP API key for authentication",
        validation_alias="erp_api_key",
    )
    monitor_erp_timeout_seconds: int = Field(
        default=30,
        alias="erp_timeout_seconds",
        description="HTTP timeout in seconds for ERP push requests",
        validation_alias="erp_timeout_seconds",
    )

    # ── Auth / JWT ───────────────────────────────────────────────────────
    jwt_secret_key: str = Field(
        default=_INSECURE_JWT_DEFAULT,
        description="Secret key for signing JWT tokens — MUST be a random 64-byte secret in production",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(
        default=30, description="Access token lifetime in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, description="Refresh token lifetime in days"
    )

    # ── OAuth — Microsoft ─────────────────────────────────────────────
    microsoft_client_id: str = Field(
        default="", description="Microsoft OAuth client ID"
    )
    microsoft_client_secret: str = Field(
        default="", description="Microsoft OAuth client secret"
    )
    microsoft_redirect_uri: str = Field(
        default="http://localhost:5173/auth/microsoft/callback",
        description="Microsoft OAuth redirect URI",
    )
    microsoft_tenant_id: str = Field(
        default="common", description="Microsoft tenant (common for multi-tenant)"
    )

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:3000",
        ],
        description="Allowed CORS origins",
    )

    # ── File Storage ─────────────────────────────────────────────────────
    upload_dir: str = Field(
        default="./data/uploads",
        description=(
            "Local staging directory for uploaded PDFs. "
            "Used as temp space before blob upload in production, "
            "and as the permanent store in local development."
        ),
    )
    max_upload_size_mb: int = Field(default=50, description="Maximum upload size in MB")

    # ── Azure Blob Storage ────────────────────────────────────────────────
    azure_storage_connection_string: str = Field(
        default="",
        description=(
            "Azure Storage connection string "
            "(Storage Account → Access keys → key1 → Connection string). "
            "Setting this activates blob storage — local upload_dir is used only "
            "as a temp staging area."
        ),
    )
    azure_storage_container_name: str = Field(
        default="uploads",
        description="Azure Blob Storage container name (create it in the portal first).",
    )

    # ── Computed ─────────────────────────────────────────────────────────
    _BASE_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent

    @field_validator("upload_dir")
    @classmethod
    def ensure_upload_dir_exists(cls, v: str) -> str:
        """Create the upload directory if it does not exist."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return v

    @model_validator(mode="after")
    def validate_jwt_secret_in_production(self) -> "Settings":
        """Reject insecure JWT defaults in non-development environments."""
        if self.app_env not in ("development", "test"):
            if self.jwt_secret_key == _INSECURE_JWT_DEFAULT:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a unique random value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(64))\""
                )
            if len(self.jwt_secret_key) < _MIN_JWT_SECRET_LENGTH:
                raise ValueError(
                    f"JWT_SECRET_KEY must be at least {_MIN_JWT_SECRET_LENGTH} characters."
                )
        return self

    @property
    def use_azure_storage(self) -> bool:
        """True when Azure Blob Storage is configured (connection string is non-empty)."""
        return bool(self.azure_storage_connection_string.strip())

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def use_azure_openai(self) -> bool:
        """True when Azure OpenAI is configured (endpoint is non-empty)."""
        return bool(self.azure_openai_endpoint.strip())

    @property
    def has_llm_config(self) -> bool:
        """True when a fully configured LLM provider is available for PDF extraction."""
        if self.use_azure_openai:
            return bool(
                self.azure_openai_endpoint.strip()
                and self.azure_openai_api_key.strip()
                and self.azure_openai_deployment.strip()
            )
        return bool(self.openai_api_key.strip())

    @property
    def has_openai_key(self) -> bool:
        return self.has_llm_config

    @property
    def has_monitor_erp_config(self) -> bool:
        """Check whether ERP push credentials are configured."""
        return bool(
            self.monitor_erp_base_url.strip() and self.monitor_erp_api_key.strip()
        )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()  # type: ignore[call-arg]
