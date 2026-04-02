"""Custom exception classes for structured error handling.

Each exception maps to a specific HTTP status code and carries
a machine-readable error code plus a human-readable message.
"""

from __future__ import annotations


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


class ValidationError(AppError):
    """Raised when input data fails business-rule validation."""

    def __init__(self, message: str, *, error_code: str = "VALIDATION_ERROR") -> None:
        super().__init__(message, error_code=error_code, status_code=422)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, identifier: str | int) -> None:
        super().__init__(
            f"{resource} with id '{identifier}' not found",
            error_code="NOT_FOUND",
            status_code=404,
        )


class ExtractionError(AppError):
    """Raised when PDF extraction fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="EXTRACTION_FAILED", status_code=502)


class FileValidationError(AppError):
    """Raised when an uploaded file fails validation (type, size)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="FILE_VALIDATION_ERROR", status_code=400)


class XMLGenerationError(AppError):
    """Raised when Monitor XML generation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="XML_GENERATION_ERROR", status_code=500)


class ConflictError(AppError):
    """Raised when a resource already exists (e.g. duplicate email)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="CONFLICT", status_code=409)


class AuthenticationError(AppError):
    """Raised when authentication fails (bad credentials, expired token, etc.)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="AUTHENTICATION_ERROR", status_code=401)


class CustomerMatchError(AppError):
    """Raised when customer matching fails unexpectedly (not 'no match found')."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="CUSTOMER_MATCH_ERROR", status_code=500)
