"""Tests for show object validation and display formatting."""

import pytest

from models.show import Show
from utils.exceptions import ValidationError
from utils.json_explainer import explain_show


def test_show_from_api_payload_normalizes_values():
    """Build an immutable show model from a valid TVMaze object."""
    show = Show.from_api_payload(
        {
            "id": 42,
            "name": "  Example  ",
            "rating": {"average": 7},
            "genres": ["Drama", "Mystery"],
            "summary": "<p>Example summary</p>",
            "url": "https://example.test",
        }
    )

    assert show.name == "Example"
    assert show.rating == 7.0
    assert show.genres == ("Drama", "Mystery")
    assert "Summary: Example summary" in explain_show(show)


def test_show_allows_missing_average_rating():
    """Represent TVMaze shows without a published rating."""
    show = Show.from_api_payload(
        {
            "id": 1,
            "name": "Unrated",
            "rating": {"average": None},
            "genres": [],
            "summary": None,
            "url": None,
        }
    )

    assert show.rating is None


def test_direct_model_creation_rejects_invalid_rating():
    """Protect model invariants when bypassing the API factory."""
    with pytest.raises(ValidationError, match="rating"):
        Show(1, "Invalid", 11, (), None, None)


def test_factory_rejects_malformed_payload():
    """Raise a domain validation error for malformed show data."""
    with pytest.raises(ValidationError, match="id"):
        Show.from_api_payload({"id": "not-an-id"})
