"""
plaude_thunes - A reusable Python SDK for integrating with the Thunes payment API.

Designed for use with Django + DRF projects. Follows clean architecture and
provides extensible views, services, and a boto3-style client entry point.

Basic usage::

    from plaude_thunes import ThunesClient

    client = ThunesClient(api_key="your_key", api_base_url="https://api.example.com/thunes")
    payers = client.payers.get_by_country_and_currency("NGA", "USD")

Factory-style usage::

    import plaude_thunes
    client = plaude_thunes.client("thunes", api_key="...", api_base_url="...")
"""

from plaude_thunes._client import ThunesClient  # noqa: F401
from plaude_thunes.services.integration import ThunesPayerService  # noqa: F401

__version__ = "0.1.0"
__all__ = ["ThunesClient", "ThunesPayerService"]


def client(service_name: str = "thunes", **kwargs) -> ThunesClient:
    """
    Factory function (boto3-style) to create a ThunesClient.

    Args:
        service_name: Currently only "thunes" is supported.
        **kwargs: Passed directly to ThunesClient constructor.
                  Supported: api_key, api_base_url, callback_key,
                             callback_secret, environment, timeout.

    Returns:
        ThunesClient: Configured client instance.

    Raises:
        ValueError: If service_name is not "thunes".

    Example::

        import plaude_thunes
        c = plaude_thunes.client("thunes", api_key="abc", api_base_url="https://...")
    """
    if service_name != "thunes":
        raise ValueError(f"Unknown service: '{service_name}'. Only 'thunes' is supported.")
    return ThunesClient(**kwargs)
