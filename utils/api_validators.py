"""Validation for external show search responses."""

from __future__ import annotations

from typing import Any

from utils.exceptions import ValidationError


def validate_api_response(payload: Any) -> None:
    """Validate the outer TVMaze search response and each show object."""
    if not isinstance(payload, list):
        raise ValidationError("API search response must be a list.")
    for result in payload:
        if (
            not isinstance(result, dict)
            or "show" not in result
            or not isinstance(result["show"], dict)
        ):
            raise ValidationError("Each API result must contain a show object.")
