"""Reusable validation for user input, configuration, and API responses."""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from utils.exceptions import ConfigurationError, ValidationError


def validate_search_term(value: str, minimum_length: int) -> str:
    """Return a trimmed search phrase or raise a clear validation error."""
    if not isinstance(value, str):
        raise ValidationError("Search term must be text.")
    normalized = value.strip()
    if len(normalized) < minimum_length:
        raise ValidationError(
            f"Search term must contain at least {minimum_length} characters."
        )
    return normalized


def validate_rating_threshold(
    value: object, minimum: float, maximum: float
) -> float:
    """Parse and validate a finite numeric rating threshold."""
    if isinstance(value, bool):
        raise ValidationError("Rating threshold must be numeric.")
    try:
        threshold = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError) as error:
        raise ValidationError("Rating threshold must be numeric.") from error
    if not math.isfinite(threshold):
        raise ValidationError("Rating threshold must be a finite number.")
    if not minimum <= threshold <= maximum:
        raise ValidationError(
            f"Rating threshold must be between {minimum:g} and {maximum:g}."
        )
    return threshold


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
    if not isinstance(data["search_path"], str):
        raise ConfigurationError("search_path must be a string.")
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


def validate_api_response(payload: Any) -> None:
    """Validate the outer TVMaze search response and each show object."""
    if not isinstance(payload, list):
        raise ValidationError("API search response must be a list.")
    for result in payload:
        if not isinstance(result, dict) or "show" not in result:
            raise ValidationError("Each API result must contain a show object.")
        validate_show_payload(result["show"])


def validate_show_payload(payload: Any) -> None:
    """Validate fields consumed from a TVMaze show object."""
    if not isinstance(payload, dict):
        raise ValidationError("Show response must be an object.")
    show_id = payload.get("id")
    if isinstance(show_id, bool) or not isinstance(show_id, int) or show_id < 0:
        raise ValidationError("Show id must be a non-negative integer.")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("Show name must be a non-empty string.")
    rating = payload.get("rating")
    if not isinstance(rating, dict) or "average" not in rating:
        raise ValidationError("Show rating must contain an average value.")
    average = rating["average"]
    if average is not None:
        if isinstance(average, bool) or not isinstance(average, Real):
            raise ValidationError("Show rating average must be numeric or null.")
        if not math.isfinite(float(average)) or not 0 <= average <= 10:
            raise ValidationError("Show rating average must be between 0 and 10.")
    genres = payload.get("genres")
    if not isinstance(genres, list) or not all(
        isinstance(genre, str) for genre in genres
    ):
        raise ValidationError("Show genres must be a list of strings.")
    summary = payload.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise ValidationError("Show summary must be text or null.")
    url = payload.get("url")
    if url is not None and not isinstance(url, str):
        raise ValidationError("Show URL must be text or null.")


def _configuration_number(value: Any, name: str) -> float:
    """Convert a JSON numeric setting to a finite floating-point value."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ConfigurationError(f"{name} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise ConfigurationError(f"{name} must be finite.")
    return number
