"""Validation for application configuration data."""

from __future__ import annotations

import math
from numbers import Real
from typing import Any
from urllib.parse import urlparse

from utils.exceptions import ConfigurationError


def validate_configuration(data: Any) -> None:
    """Validate the required keys and primitive values in configuration JSON."""
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration must be a JSON object.")
    required_keys = {
        "api_base_url",
        "search_path",
        "timeout_seconds",
        "minimum_search_length",
        "rating_minimum",
        "rating_maximum",
        "log_level",
    }
    missing_keys = required_keys.difference(data)
    if missing_keys:
        raise ConfigurationError(
            "Missing configuration values: " + ", ".join(sorted(missing_keys))
        )
    if not isinstance(data["api_base_url"], str) or not data["api_base_url"].strip():
        raise ConfigurationError("api_base_url must be a non-empty string.")
    parsed_url = urlparse(data["api_base_url"])
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ConfigurationError(
            "api_base_url must be an absolute HTTP or HTTPS URL."
        )
    if not isinstance(data["search_path"], str) or not data["search_path"].strip():
        raise ConfigurationError("search_path must be a non-empty string.")
    if not isinstance(data["log_level"], str) or data["log_level"].upper() not in {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }:
        raise ConfigurationError("log_level must be a supported logging level.")

    timeout = _configuration_number(data["timeout_seconds"], "timeout_seconds")
    if timeout <= 0:
        raise ConfigurationError("timeout_seconds must be greater than zero.")
    minimum_length = data["minimum_search_length"]
    if isinstance(minimum_length, bool) or not isinstance(minimum_length, int):
        raise ConfigurationError("minimum_search_length must be an integer.")
    if minimum_length < 1:
        raise ConfigurationError("minimum_search_length must be at least one.")
    rating_minimum = _configuration_number(data["rating_minimum"], "rating_minimum")
    rating_maximum = _configuration_number(data["rating_maximum"], "rating_maximum")
    if rating_minimum < 0 or rating_maximum > 10 or rating_minimum >= rating_maximum:
        raise ConfigurationError(
            "Rating bounds must be ordered within the supported 0 to 10 range."
        )
    for key in ("provider_base_urls", "website_base_urls"):
        urls = data.get(key, {})
        if not isinstance(urls, dict):
            raise ConfigurationError(f"{key} must be an object.")
        for provider, url in urls.items():
            if not isinstance(provider, str) or not provider.strip():
                raise ConfigurationError("Provider names must be non-empty strings.")
            if not isinstance(url, str) or not url.strip():
                raise ConfigurationError(
                    f"Provider URL for {provider} must be a string."
                )
            parsed_provider_url = urlparse(url)
            if (
                parsed_provider_url.scheme not in {"http", "https"}
                or not parsed_provider_url.netloc
            ):
                raise ConfigurationError(
                    f"Provider URL for {provider} must be an absolute HTTP or HTTPS URL."
                )
    minimum_votes = data.get("imdb_minimum_votes", 25_000)
    if isinstance(minimum_votes, bool) or not isinstance(minimum_votes, int):
        raise ConfigurationError("imdb_minimum_votes must be an integer.")
    if minimum_votes < 0:
        raise ConfigurationError("imdb_minimum_votes cannot be negative.")


def _configuration_number(value: Any, name: str) -> float:
    """Convert a JSON numeric setting to a finite floating-point value."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ConfigurationError(f"{name} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise ConfigurationError(f"{name} must be finite.")
    return number
