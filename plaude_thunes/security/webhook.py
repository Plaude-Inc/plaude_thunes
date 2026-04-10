"""
Webhook signature validation for Thunes callbacks.

Thunes authenticates webhook deliveries using HTTP Basic Auth.
The Authorization header contains Base64-encoded "key:secret".

This module is framework-agnostic: it works with Django HttpRequest,
DRF Request, or any object that exposes a .headers dict-like interface.
"""

import base64
import logging
from typing import Optional

from plaude_thunes.exceptions import ThunesWebhookError

logger = logging.getLogger(__name__)


class WebhookValidator:
    """
    Validates incoming Thunes webhook requests using Basic Auth credentials.

    Usage::

        validator = WebhookValidator(callback_key="mykey", callback_secret="mysecret")

        # In a view:
        if not validator.is_valid(request):
            return HttpResponse("Unauthorized", status=401)

        # Or raise on failure:
        validator.validate(request)   # raises ThunesWebhookError if invalid

    Downstream apps can subclass this and override `extract_credentials()`
    to support alternate auth schemes.
    """

    def __init__(self, callback_key: str, callback_secret: str):
        """
        Args:
            callback_key: The expected Basic Auth username (callback key).
            callback_secret: The expected Basic Auth password (callback secret).
        """
        if not callback_key or not callback_secret:
            raise ValueError(
                "callback_key and callback_secret must be non-empty strings."
            )
        self._callback_key = callback_key
        self._callback_secret = callback_secret

    def extract_credentials(self, request) -> Optional[tuple]:
        """
        Extract (key, secret) from the request's Authorization header.

        Returns:
            Tuple of (key, secret) or None if extraction fails.

        Override this method to support alternative header formats.
        """
        auth_header = self._get_header(request, "Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            logger.warning(
                "Missing or malformed Authorization header in Thunes webhook"
            )
            return None

        try:
            encoded = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            key, secret = decoded.split(":", 1)
            return key, secret
        except (
            IndexError,
            ValueError,
            UnicodeDecodeError,
            base64.binascii.Error,
        ) as exc:
            logger.warning("Failed to decode webhook Authorization header: %s", exc)
            return None

    def is_valid(self, request) -> bool:
        """
        Check whether the webhook request carries valid credentials.

        Args:
            request: Django HttpRequest, DRF Request, or any object
                     with .headers or .META dict.

        Returns:
            True if credentials match, False otherwise.
        """
        credentials = self.extract_credentials(request)
        if credentials is None:
            return False
        key, secret = credentials
        return key == self._callback_key and secret == self._callback_secret

    def validate(self, request) -> None:
        """
        Assert that the webhook request is valid, raising on failure.

        Args:
            request: The incoming webhook request.

        Raises:
            ThunesWebhookError: If credentials are missing or invalid.
        """
        credentials = self.extract_credentials(request)
        if credentials is None:
            raise ThunesWebhookError(
                "Webhook validation failed: missing or malformed Authorization header.",
                reason="missing_header",
            )
        key, secret = credentials
        if key != self._callback_key or secret != self._callback_secret:
            raise ThunesWebhookError(
                "Webhook validation failed: invalid credentials.",
                reason="invalid_credentials",
            )

    @staticmethod
    def _get_header(request, name: str) -> Optional[str]:
        """Retrieve a header value from Django/DRF request objects."""
        # DRF / Django: request.headers is a case-insensitive dict
        if hasattr(request, "headers"):
            return request.headers.get(name)
        # Django raw META fallback
        if hasattr(request, "META"):
            meta_key = f"HTTP_{name.upper().replace('-', '_')}"
            return request.META.get(meta_key)
        return None
