"""
Central entry point for plaude_thunes — analogous to ``boto3.client()``.

ThunesClient composes the HTTP client, config, and domain services into a
single cohesive object that downstream applications interact with.

All configuration is passed explicitly at construction time::

    from plaude_thunes import ThunesClient

    client = ThunesClient(
        api_key="your_api_key",
        api_base_url="https://api.example.com/thunes",
        callback_key="webhook_key",
        callback_secret="webhook_secret",
        environment="production",   # or "sandbox"
    )

Or using the boto3-style factory::

    import plaude_thunes
    client = plaude_thunes.client("thunes", api_key="...", api_base_url="...")

Then use domain services::

    payers = client.payers.get_by_country_and_currency("NGA", "USD")
    quotation = client.transactions.create_quotation(...)
    client.credit_party.validate(payer_id=..., ...)
    client.webhook_validator.validate(request)
"""

import logging
from typing import Callable, Optional

import requests

from plaude_thunes.clients.thunes_client import ThunesHTTPClient
from plaude_thunes.config import ThunesConfig
from plaude_thunes.security.webhook import WebhookValidator
from plaude_thunes.services.credit_party import CreditPartyService
from plaude_thunes.services.payers import PayerService
from plaude_thunes.services.transactions import TransactionService

logger = logging.getLogger(__name__)


class ThunesClient:
    """
    Top-level SDK client — the primary interface for all Thunes operations.

    Attributes:
        payers (PayerService): Payer lookups and required-field resolution.
        transactions (TransactionService): Full transaction lifecycle.
        credit_party (CreditPartyService): Account validation and info.
        webhook_validator (WebhookValidator): Validates incoming Thunes webhooks.
        http (ThunesHTTPClient): Raw HTTP client (for advanced / custom calls).
        config (ThunesConfig): The resolved configuration.

    Args:
        api_key: Thunes gateway API key.
        api_base_url: Base URL for the Thunes gateway/proxy.
        callback_key: Webhook callback authentication key.
        callback_secret: Webhook callback authentication secret.
        environment: "sandbox" or "production" (default: "production").
        timeout: HTTP request timeout in seconds (default 30).
        request_hook: Optional callable for request logging / mutation.
                      Signature: ``(method: str, url: str, kwargs: dict) -> None``
        response_hook: Optional callable for response logging / metrics.
                       Signature: ``(response: requests.Response) -> None``
        session: Optional pre-configured ``requests.Session`` (useful for testing).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        callback_key: Optional[str] = None,
        callback_secret: Optional[str] = None,
        environment: Optional[str] = None,
        timeout: Optional[int] = None,
        request_hook: Optional[Callable] = None,
        response_hook: Optional[Callable] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = ThunesConfig(
            api_key=api_key,
            api_base_url=api_base_url,
            callback_key=callback_key,
            callback_secret=callback_secret,
            environment=environment or "production",
            timeout=timeout or 30,
        )
        self.config.validate()

        self.http = ThunesHTTPClient(
            config=self.config,
            request_hook=request_hook,
            response_hook=response_hook,
            session=session,
        )

        # Domain services — each receives the shared HTTP client
        self.payers = PayerService(self.http)
        self.transactions = TransactionService(self.http)
        self.credit_party = CreditPartyService(self.http)

        # Webhook validator — only available if callback credentials are configured
        if self.config.callback_key and self.config.callback_secret:
            self.webhook_validator = WebhookValidator(
                callback_key=self.config.callback_key,
                callback_secret=self.config.callback_secret,
            )
        else:
            self.webhook_validator = None

    def __repr__(self) -> str:
        return f"ThunesClient(config={self.config!r})"
