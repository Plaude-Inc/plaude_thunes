"""
Shared pytest fixtures for plaude_thunes tests.
"""

import base64

import pytest
import responses as responses_lib

from plaude_thunes._client import ThunesClient
from plaude_thunes.config import ThunesConfig

API_BASE_URL = "https://test.api.example.com/thunes"
API_KEY = "test-api-key"
CALLBACK_KEY = "test-callback-key"
CALLBACK_SECRET = "test-callback-secret"


@pytest.fixture
def thunes_config():
    return ThunesConfig(
        api_key=API_KEY,
        api_base_url=API_BASE_URL,
        callback_key=CALLBACK_KEY,
        callback_secret=CALLBACK_SECRET,
        environment="sandbox",
    )


@pytest.fixture
def thunes_client(thunes_config):
    return ThunesClient(
        api_key=thunes_config.api_key,
        api_base_url=thunes_config.api_base_url,
        callback_key=thunes_config.callback_key,
        callback_secret=thunes_config.callback_secret,
    )


@pytest.fixture
def mocked_responses():
    """Activate the `responses` library for the duration of a test."""
    with responses_lib.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def valid_basic_auth_header():
    """Return a valid Basic Auth header value for test callback credentials."""
    encoded = base64.b64encode(f"{CALLBACK_KEY}:{CALLBACK_SECRET}".encode()).decode()
    return f"Basic {encoded}"


@pytest.fixture
def invalid_basic_auth_header():
    """Return an invalid Basic Auth header value."""
    encoded = base64.b64encode(b"wrong:credentials").decode()
    return f"Basic {encoded}"
