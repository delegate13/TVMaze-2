"""Validation for user-supplied search criteria."""

from __future__ import annotations

import math

from utils.exceptions import ValidationError


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
