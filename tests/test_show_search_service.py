"""Tests for the shared search use case and provider contract."""

import pytest

from models.show import Show
from services.configuration_service import ApplicationConfig
from services.provider import ShowSearchProvider
from services.show_search_service import SearchCriteria, ShowSearchService
from utils.exceptions import ValidationError


@pytest.fixture
def config():
    """Provide configuration used by the search use case."""
    return ApplicationConfig(
        api_base_url="https://example.test/",
        search_path="search/shows",
        timeout_seconds=2,
        minimum_search_length=2,
        rating_minimum=0,
        rating_maximum=10,
        log_level="INFO",
    )


class FakeProvider:
    """Provide normalized shows while recording provider calls."""

    def __init__(self):
        self.calls = []

    def search_shows(self, search_term):
        self.calls.append(search_term)
        return [
            Show(1, "High", 9.0, (), None, None),
            Show(2, "Low", 5.0, (), None, None),
            Show(3, "Unrated", None, (), None, None),
        ]


def test_search_provider_satisfies_provider_protocol():
    """Describe providers by the single operation needed by application code."""
    assert isinstance(FakeProvider(), ShowSearchProvider)


def test_search_validates_criteria_and_uses_provider(config):
    """Normalize whitespace and pass the shared criteria to the provider."""
    provider = FakeProvider()
    service = ShowSearchService(provider, config)

    criteria = service.create_criteria("  Example  ")
    shows = service.search(criteria)

    assert criteria == SearchCriteria("Example")
    assert provider.calls == ["Example"]
    assert [show.name for show in shows] == ["High", "Low", "Unrated"]


def test_search_service_applies_rating_filter(config):
    """Apply identical rating filtering in both interfaces."""
    provider = FakeProvider()
    service = ShowSearchService(provider, config)

    criteria = service.create_criteria("Example", "8")

    assert [show.name for show in service.search(criteria)] == ["High"]


@pytest.mark.parametrize(
    ("term", "rating"),
    [("x", None), ("Example", "11"), ("Example", "not-a-number")],
)
def test_search_service_rejects_invalid_criteria(config, term, rating):
    """Reject invalid inputs before any API provider request."""
    provider = FakeProvider()
    service = ShowSearchService(provider, config)

    with pytest.raises(ValidationError):
        service.create_criteria(term, rating)
    assert provider.calls == []
