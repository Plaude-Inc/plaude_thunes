"""
Configuration handling for plaude_thunes.

All configuration must be provided via constructor injection when initialising
ThunesClient. There is no automatic reading from environment variables or
Django settings — the calling application is responsible for supplying values.

Example::

    from plaude_thunes import ThunesClient

    client = ThunesClient(
        api_key="your_api_key",
        api_base_url="https://api.example.com/thunes",
        callback_key="webhook_key",
        callback_secret="webhook_secret",
        environment="production",
    )
"""

from typing import Optional


class ThunesConfig:
    """
    Holds all configuration for plaude_thunes.

    All values are provided at construction time — no environment variable or
    Django settings lookups are performed.

    Args:
        api_key: API key for Thunes gateway authentication.
        api_base_url: Full base URL, e.g. "https://api.example.com/thunes".
        callback_key: Webhook callback authentication key.
        callback_secret: Webhook callback authentication secret.
        environment: "sandbox" or "production" (default: "production").
        timeout: HTTP request timeout in seconds (default: 30).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        callback_key: Optional[str] = None,
        callback_secret: Optional[str] = None,
        environment: str = "production",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.callback_key = callback_key
        self.callback_secret = callback_secret
        self.environment = environment
        self.timeout = int(timeout)

    @property
    def is_sandbox(self) -> bool:
        return self.environment == "sandbox"

    def validate(self) -> None:
        """Raise ValueError if required config fields are missing."""
        if not self.api_key:
            raise ValueError(
                "ThunesConfig: 'api_key' is required. Pass it to ThunesClient(api_key=...)."
            )
        if not self.api_base_url:
            raise ValueError(
                "ThunesConfig: 'api_base_url' is required. Pass it to ThunesClient(api_base_url=...)."
            )

    def __repr__(self) -> str:
        api_key_preview = f"{self.api_key[:6]}..." if self.api_key else "None"
        return (
            f"ThunesConfig(api_key={api_key_preview!r}, "
            f"api_base_url={self.api_base_url!r}, "
            f"environment={self.environment!r})"
        )
