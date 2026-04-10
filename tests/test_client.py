"""
Tests for plaude_thunes.clients.thunes_client.ThunesHTTPClient
and plaude_thunes._client.ThunesClient
"""

import pytest
import responses as responses_lib

from plaude_thunes._client import ThunesClient
from plaude_thunes.clients.thunes_client import ThunesHTTPClient
from plaude_thunes.exceptions import (
    ThunesAPIError,
    ThunesAuthenticationError,
    ThunesNotFoundError,
    ThunesValidationError,
)

API_BASE = "https://test.api.example.com/thunes"


class TestThunesHTTPClientResponseHandling:
    """Unit tests for _handle_response error mapping."""

    def _make_http_client(self):
        from plaude_thunes.config import ThunesConfig

        cfg = ThunesConfig(api_key="key", api_base_url=API_BASE)
        return ThunesHTTPClient(config=cfg)

    @responses_lib.activate
    def test_successful_get_returns_json(self):
        responses_lib.add(
            responses_lib.GET,
            f"{API_BASE}/purpose-of-remittance",
            json={"status": "success", "data": [{"purpose": "EDUCATION"}]},
            status=200,
        )
        client = self._make_http_client()
        result = client.get_purpose_of_remittance()
        assert result["status"] == "success"
        assert result["data"][0]["purpose"] == "EDUCATION"

    @responses_lib.activate
    def test_401_raises_authentication_error(self):
        responses_lib.add(
            responses_lib.GET,
            f"{API_BASE}/payer/999",
            json={"detail": "Authentication credentials were not provided."},
            status=401,
        )
        client = self._make_http_client()
        with pytest.raises(ThunesAuthenticationError):
            client._request("GET", "/payer/999")

    @responses_lib.activate
    def test_404_raises_not_found_error(self):
        responses_lib.add(
            responses_lib.GET,
            f"{API_BASE}/payer/999",
            json={"detail": "Not found"},
            status=404,
        )
        client = self._make_http_client()
        with pytest.raises(ThunesNotFoundError):
            client._request("GET", "/payer/999")

    @responses_lib.activate
    def test_400_raises_validation_error(self):
        responses_lib.add(
            responses_lib.POST,
            f"{API_BASE}/payers/credit-party-validation",
            json={"detail": "Invalid payer_id"},
            status=400,
        )
        client = self._make_http_client()
        with pytest.raises(ThunesValidationError):
            client._request("POST", "/payers/credit-party-validation", json={})

    @responses_lib.activate
    def test_500_raises_api_error(self):
        responses_lib.add(
            responses_lib.GET,
            f"{API_BASE}/purpose-of-remittance",
            json={"detail": "Internal server error"},
            status=500,
        )
        client = self._make_http_client()
        with pytest.raises(ThunesAPIError) as exc_info:
            client._request("GET", "/purpose-of-remittance")
        assert exc_info.value.status_code == 500

    @responses_lib.activate
    def test_get_payer_details_returns_none_on_error(self):
        responses_lib.add(
            responses_lib.GET,
            f"{API_BASE}/payer/bad-id",
            json={"detail": "Not found"},
            status=404,
        )
        client = self._make_http_client()
        result = client.get_payer_details("bad-id")
        assert result is None

    @responses_lib.activate
    def test_request_hook_is_called(self):
        calls = []
        responses_lib.add(
            responses_lib.GET,
            f"{API_BASE}/purpose-of-remittance",
            json={"status": "success", "data": []},
            status=200,
        )
        from plaude_thunes.config import ThunesConfig

        cfg = ThunesConfig(api_key="key", api_base_url=API_BASE)
        client = ThunesHTTPClient(
            config=cfg,
            request_hook=lambda method, url, kwargs: calls.append((method, url)),
        )
        client.get_purpose_of_remittance()
        assert len(calls) == 1
        assert calls[0][0] == "GET"


class TestThunesClientFactory:
    def test_client_has_service_attributes(self, thunes_client):
        assert thunes_client.payers is not None
        assert thunes_client.transactions is not None
        assert thunes_client.credit_party is not None
        assert thunes_client.webhook_validator is not None

    def test_client_without_callback_creds_has_no_validator(self):
        client = ThunesClient(api_key="key", api_base_url=API_BASE)
        assert client.webhook_validator is None

    def test_factory_function(self):
        import plaude_thunes

        client = plaude_thunes.client("thunes", api_key="k", api_base_url=API_BASE)
        assert isinstance(client, ThunesClient)

    def test_factory_function_invalid_service(self):
        import plaude_thunes

        with pytest.raises(ValueError, match="Unknown service"):
            plaude_thunes.client("s3", api_key="k", api_base_url=API_BASE)
