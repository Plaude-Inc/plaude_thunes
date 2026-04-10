"""
Tests for plaude_thunes.config.ThunesConfig
"""

import pytest

from plaude_thunes.config import ThunesConfig


class TestThunesConfigConstructorInjection:
    def test_all_values_from_constructor(self):
        cfg = ThunesConfig(
            api_key="mykey",
            api_base_url="https://api.example.com/thunes",
            callback_key="cbkey",
            callback_secret="cbsecret",
            environment="sandbox",
            timeout=60,
        )
        assert cfg.api_key == "mykey"
        assert cfg.api_base_url == "https://api.example.com/thunes"
        assert cfg.callback_key == "cbkey"
        assert cfg.callback_secret == "cbsecret"
        assert cfg.environment == "sandbox"
        assert cfg.timeout == 60
        assert cfg.is_sandbox is True

    def test_defaults(self):
        cfg = ThunesConfig(api_key="k", api_base_url="https://example.com")
        assert cfg.environment == "production"
        assert cfg.timeout == 30
        assert cfg.is_sandbox is False


class TestThunesConfigValidation:
    def test_validate_raises_if_api_key_missing(self):
        cfg = ThunesConfig(api_base_url="https://example.com")
        with pytest.raises(ValueError, match="api_key"):
            cfg.validate()

    def test_validate_raises_if_base_url_missing(self):
        cfg = ThunesConfig(api_key="key")
        with pytest.raises(ValueError, match="api_base_url"):
            cfg.validate()

    def test_validate_passes_with_all_required(self):
        cfg = ThunesConfig(api_key="key", api_base_url="https://example.com")
        cfg.validate()  # Should not raise
