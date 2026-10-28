"""Tests for rating filtering and reusable user-input validation."""

import pytest

from models.show import Show
from services.show_filter_service import ShowFilterService
from utils.api_validators import validate_api_response
from utils.configuration_validators import validate_configuration
from utils.exceptions import ValidationError
from utils.input_validators import (
    validate_rating_threshold,
    validate_search_term,
)


def test_filter_includes_ratings_equal_to_threshold():
    """Include the threshold itself and exclude unrated or lower-rated shows."""
    shows = [
        Show(1, "High", 8.0, (), None, None),
        Show(2, "Equal", 7.0, (), None, None),
        Show(3, "Low", 6.9, (), None, None),
        Show(4, "Unrated", None, (), None, None),
    ]

    result = ShowFilterService().filter_by_minimum_rating(shows, 7.0)

    assert [show.name for show in result] == ["High", "Equal"]


@pytest.mark.parametrize("value", ["", " ", "x", None])
def test_search_term_rejects_blank_or_short_values(value):
    """Reject search terms that cannot meet the configured minimum length."""
    with pytest.raises(ValidationError):
        validate_search_term(value, minimum_length=2)


def test_search_term_is_trimmed():
    """Normalize spaces around user-provided search terms."""
    assert validate_search_term("  Lost  ", minimum_length=2) == "Lost"


@pytest.mark.parametrize("value", ["abc", "-1", "10.1", "NaN", True])
def test_rating_threshold_rejects_invalid_values(value):
    """Reject nonnumeric, nonfinite, and out-of-range rating values."""
    with pytest.raises(ValidationError):
        validate_rating_threshold(value, minimum=0, maximum=10)


def test_rating_threshold_accepts_numeric_string():
    """Convert a valid CLI numeric argument into a float."""
    assert validate_rating_threshold("7.5", minimum=0, maximum=10) == 7.5


def test_configuration_validator_rejects_missing_settings():
    """Report incomplete configuration instead of applying silent defaults."""
    from utils.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError, match="Missing configuration"):
        validate_configuration({})


def test_api_response_validator_rejects_non_list_payload():
    """Reject an API response whose outer structure is not a result list."""
    with pytest.raises(ValidationError, match="must be a list"):
        validate_api_response({"show": {}})


def test_api_response_validator_rejects_missing_show_object():
    """Reject list entries that do not contain a show object."""
    with pytest.raises(ValidationError, match="contain a show object"):
        validate_api_response([{}])
