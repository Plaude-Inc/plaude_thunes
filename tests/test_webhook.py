"""
Tests for plaude_thunes.security.webhook.WebhookValidator
and plaude_thunes.api.views.webhooks.BaseThunesWebhookView
"""

import base64
from unittest.mock import MagicMock

import pytest

from plaude_thunes.exceptions import ThunesWebhookError
from plaude_thunes.security.webhook import WebhookValidator

# ---------------------------------------------------------------------------
# WebhookValidator unit tests
# ---------------------------------------------------------------------------

CALLBACK_KEY = "test-key"
CALLBACK_SECRET = "test-secret"


def _make_request(auth_header=None):
    """Helper: create a minimal request mock with the given Authorization header."""
    request = MagicMock()
    request.headers = {}
    if auth_header:
        request.headers["Authorization"] = auth_header
    return request


def _encode_credentials(key, secret):
    return "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode()


class TestWebhookValidatorIsValid:
    def setup_method(self):
        self.validator = WebhookValidator(CALLBACK_KEY, CALLBACK_SECRET)

    def test_valid_credentials_returns_true(self):
        request = _make_request(_encode_credentials(CALLBACK_KEY, CALLBACK_SECRET))
        assert self.validator.is_valid(request) is True

    def test_wrong_credentials_returns_false(self):
        request = _make_request(_encode_credentials("wrong", "credentials"))
        assert self.validator.is_valid(request) is False

    def test_missing_auth_header_returns_false(self):
        request = _make_request(auth_header=None)
        assert self.validator.is_valid(request) is False

    def test_non_basic_scheme_returns_false(self):
        request = _make_request("Bearer sometoken")
        assert self.validator.is_valid(request) is False

    def test_malformed_base64_returns_false(self):
        request = _make_request("Basic NOT-VALID-BASE64!!!")
        assert self.validator.is_valid(request) is False


class TestWebhookValidatorValidate:
    def setup_method(self):
        self.validator = WebhookValidator(CALLBACK_KEY, CALLBACK_SECRET)

    def test_validate_passes_silently_on_valid_request(self):
        request = _make_request(_encode_credentials(CALLBACK_KEY, CALLBACK_SECRET))
        self.validator.validate(request)  # Should not raise

    def test_validate_raises_on_missing_header(self):
        request = _make_request(auth_header=None)
        with pytest.raises(ThunesWebhookError) as exc_info:
            self.validator.validate(request)
        assert exc_info.value.reason == "missing_header"

    def test_validate_raises_on_invalid_credentials(self):
        request = _make_request(_encode_credentials("bad", "creds"))
        with pytest.raises(ThunesWebhookError) as exc_info:
            self.validator.validate(request)
        assert exc_info.value.reason == "invalid_credentials"


class TestWebhookValidatorConstructorValidation:
    def test_empty_key_raises(self):
        with pytest.raises(ValueError):
            WebhookValidator("", "secret")

    def test_empty_secret_raises(self):
        with pytest.raises(ValueError):
            WebhookValidator("key", "")


# ---------------------------------------------------------------------------
# BaseThunesWebhookView integration tests
# ---------------------------------------------------------------------------


class TestBaseThunesWebhookView:
    """
    Test the webhook view using Django's RequestFactory for lightweight HTTP testing.
    These tests do not require a database.
    """

    def setup_method(self):
        from rest_framework.test import APIRequestFactory

        from plaude_thunes.api.views.webhooks import BaseThunesWebhookView

        self.factory = APIRequestFactory()
        self.view = BaseThunesWebhookView.as_view()

    def _auth_header(self, key=CALLBACK_KEY, secret=CALLBACK_SECRET):
        return "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode()

    def _post(self, data, auth_header=None, view_class=None):
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.post(
            "/thunes/webhook/",
            data=data,
            format="json",
            HTTP_AUTHORIZATION=auth_header or self._auth_header(),
        )
        from plaude_thunes.api.views.webhooks import BaseThunesWebhookView

        # Build a concrete subclass that returns Django settings callback creds
        class SettingsWebhookView(BaseThunesWebhookView):
            callback_key = CALLBACK_KEY
            callback_secret = CALLBACK_SECRET

        view_cls = view_class or SettingsWebhookView
        return view_cls.as_view()(request)

    def test_valid_webhook_returns_200(self):
        response = self._post({"id": "tx-001", "status_message": "PENDING"})
        assert response.status_code == 200

    def test_invalid_credentials_returns_401(self):
        bad_auth = "Basic " + base64.b64encode(b"wrong:creds").decode()
        response = self._post({"id": "tx-001"}, auth_header=bad_auth)
        assert response.status_code == 401

    def test_empty_payload_returns_400(self):
        response = self._post({})
        assert response.status_code == 400

    def test_handle_event_is_called_with_data(self):
        events = []

        from plaude_thunes.api.views.webhooks import BaseThunesWebhookView

        class CapturingWebhookView(BaseThunesWebhookView):
            callback_key = CALLBACK_KEY
            callback_secret = CALLBACK_SECRET

            def handle_event(self, data):
                events.append(data)

        response = self._post(
            {"id": "tx-001", "status_class_message": "COMPLETED"},
            view_class=CapturingWebhookView,
        )
        assert response.status_code == 200
        assert len(events) == 1
        assert events[0]["id"] == "tx-001"
