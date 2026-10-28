"""Tests for source routing, shared validation, and rating filters."""

import pytest

from models.media_item import MediaItem
from services.configuration_service import ApplicationConfig
from services.media_discovery_service import MediaDiscoveryService
from utils.exceptions import ApiError, ValidationError


class StubProvider:
    """Return fixed normalized media for discovery-service tests."""

    def __init__(self, items):
        self.items = items

    def search(self, term, media_type):
        return self.items

    def top_movies(self, limit):
        return self.items[:limit]


@pytest.fixture
def config():
    """Provide shared validation constraints for the use case."""
    return ApplicationConfig(
        api_base_url="https://api.example.test/",
        search_path="search",
        timeout_seconds=2,
        minimum_search_length=2,
        rating_minimum=0,
        rating_maximum=10,
        log_level="INFO",
    )


def test_search_routes_to_selected_source_and_filters_ratings(config):
    """Return only items from the selected provider meeting the threshold."""
    items = [
        MediaItem("1", "Lower Rated", "movie", "TMDB", 5.0),
        MediaItem("2", "Higher Rated", "movie", "TMDB", 8.5),
        MediaItem("3", "Unrated", "movie", "TMDB"),
    ]
    service = MediaDiscoveryService({"TMDB": StubProvider(items)}, config)

    results = service.search("TMDB", "movie", "  Film  ", 8)

    assert [item.title for item in results] == ["Higher Rated"]


@pytest.mark.parametrize("term", ["", " ", "x"])
def test_search_rejects_invalid_terms(config, term):
    """Reject blank and too-short phrases before calling the provider."""
    service = MediaDiscoveryService({"TMDB": StubProvider([])}, config)

    with pytest.raises(ValidationError):
        service.search("TMDB", "movie", term)


def test_search_rejects_unknown_provider(config):
    """Report a clear error for a provider name that is not configured."""
    service = MediaDiscoveryService({}, config)

    with pytest.raises(ApiError, match="not an available media provider"):
        service.search("Unknown", "movie", "Film")


def test_top_movies_caps_provider_response_to_100(config):
    """Return at most 100 results regardless of provider response size."""
    items = [
        MediaItem(str(index), f"Movie {index}", "movie", "Test", 8.0)
        for index in range(120)
    ]
    service = MediaDiscoveryService({"Test": StubProvider(items)}, config)

    assert len(service.top_movies("Test")) == 100


def test_top_movies_reports_unsupported_provider(config):
    """Avoid reporting a successful empty ranking for unsupported sources."""
    service = MediaDiscoveryService({"Test": StubProvider([])}, config)

    with pytest.raises(ApiError, match="does not provide a top movie list"):
        service.top_movies("Test")


def test_search_validates_rating_threshold(config):
    """Reject thresholds outside the configured rating scale."""
    service = MediaDiscoveryService({"TMDB": StubProvider([])}, config)

    with pytest.raises(ValidationError):
        service.create_criteria("TMDB", "movie", "Film", 11)
