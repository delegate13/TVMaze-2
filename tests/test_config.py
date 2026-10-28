"""Tests for configuration loading and validation."""

import json
import logging

import pytest

from services.configuration_service import ConfigurationService
from utils.exceptions import ConfigurationError


@pytest.fixture
def logger() -> logging.Logger:
    """Provide an isolated logger for configuration tests."""
    return logging.getLogger("test.configuration")


def test_loads_valid_configuration(tmp_path, logger):
    """Load valid JSON into an immutable runtime configuration."""
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "api_base_url": "https://example.test/",
                "search_path": "/shows",
                "timeout_seconds": 3,
                "minimum_search_length": 2,
                "rating_minimum": 0,
                "rating_maximum": 10,
                "log_level": "debug",
            }
        ),
        encoding="utf-8",
    )

    config = ConfigurationService(logger).load(path)

    assert config.api_base_url == "https://example.test/"
    assert config.search_path == "shows"
    assert config.timeout_seconds == 3
    assert config.log_level == "DEBUG"


def test_missing_configuration_raises_clear_error(tmp_path, logger):
    """Report a missing configuration file as a domain error."""
    with pytest.raises(ConfigurationError, match="not found"):
        ConfigurationService(logger).load(tmp_path / "missing.json")


def test_invalid_configuration_values_raise_error(tmp_path, logger):
    """Reject invalid rating bounds during configuration loading."""
    config_data = {
        "api_base_url": "https://example.test/",
        "search_path": "shows",
        "timeout_seconds": 3,
        "minimum_search_length": 2,
        "rating_minimum": 9,
        "rating_maximum": 2,
        "log_level": "INFO",
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config_data), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Rating bounds"):
        ConfigurationService(logger).load(path)


def test_invalid_json_raises_configuration_error(tmp_path, logger):
    """Convert malformed JSON into a configuration error."""
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Could not read"):
        ConfigurationService(logger).load(path)
