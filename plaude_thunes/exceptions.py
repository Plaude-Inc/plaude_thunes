"""
Custom exceptions for plaude_thunes.

Hierarchy:
    ThunesSDKError
    ├── ThunesAPIError          - Non-2xx response from the Thunes gateway
    ├── ThunesAuthenticationError  - 401/403 from gateway, or invalid credentials
    ├── ThunesValidationError   - 400 / invalid input data
    ├── ThunesNotFoundError     - 404 resource not found
    ├── ThunesWebhookError      - Webhook validation or parsing failure
    └── ThunesConfigError       - Missing or invalid SDK configuration
"""

from typing import Optional


class ThunesSDKError(Exception):
    """Base class for all plaude_thunes exceptions."""


class ThunesAPIError(ThunesSDKError):
    """
    Raised when the Thunes gateway returns a non-2xx HTTP response.

    Attributes:
        status_code: HTTP status code returned by the API.
        response_body: Raw response body (dict or str).
        message: Human-readable error description.
    """

    def __init__(
        self,
        message: str = "Thunes API request failed",
        status_code: Optional[int] = None,
        response_body=None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        return " ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"status_code={self.status_code!r})"
        )


class ThunesAuthenticationError(ThunesAPIError):
    """Raised when API credentials are invalid or the request is unauthorized."""

    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, **kwargs)


class ThunesValidationError(ThunesAPIError):
    """
    Raised when input data fails validation.

    Attributes:
        errors: Field-level error details (dict or list).
    """

    def __init__(self, message: str = "Validation error", errors=None, **kwargs):
        super().__init__(message, **kwargs)
        self.errors = errors or {}

    def __str__(self) -> str:
        if self.errors:
            return f"{self.message}: {self.errors}"
        return self.message


class ThunesNotFoundError(ThunesAPIError):
    """Raised when a requested Thunes resource (payer, transaction) is not found."""

    def __init__(self, message: str = "Resource not found", **kwargs):
        super().__init__(message, status_code=404, **kwargs)


class ThunesWebhookError(ThunesSDKError):
    """
    Raised when a webhook request fails validation or cannot be parsed.

    Attributes:
        reason: Short reason code ("invalid_signature", "missing_header", etc.)
    """

    def __init__(self, message: str = "Webhook validation failed", reason: str = None):
        super().__init__(message)
        self.message = message
        self.reason = reason

    def __str__(self) -> str:
        if self.reason:
            return f"{self.message} [{self.reason}]"
        return self.message


class ThunesConfigError(ThunesSDKError):
    """Raised when required SDK configuration is missing or invalid."""
