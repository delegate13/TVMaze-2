"""Tests for the TVMaze API client without live network requests."""

import logging
from unittest.mock import Mock

import pytest
import requests

from services.configuration_service import ApplicationConfig
from services.tvmaze_service import TVMazeService
from utils.exceptions import ApiError


@pytest.fixture
def config():
    """Provide service settings suitable for mocked HTTP requests."""
    return ApplicationConfig(
        api_base_url="https://api.example.test/",
        search_path="search/shows",
        timeout_seconds=4,
        minimum_search_length=2,
        rating_minimum=0,
        rating_maximum=10,
        log_level="INFO",
    )


def show_payload(name="The Example"):
    """Build a valid TVMaze search result payload."""
    return {
        "show": {
            "id": 8,
            "name": name,
            "rating": {"average": 8.5},
            "genres": ["Drama"],
            "summary": "<p>A story.</p>",
            "url": "https://example.test/show",
        }
    }


def test_search_sends_query_and_returns_shows(config):
    """Pass the query and timeout to the HTTP dependency."""
    session = Mock()
    response = Mock()
    response.json.return_value = [show_payload()]
    session.get.return_value = response
    service = TVMazeService(config, logging.getLogger("test.api"), session)

    shows = service.search_shows("example")

    session.get.assert_called_once_with(
        "https://api.example.test/search/shows",
        params={"q": "example"},
        timeout=4,
    )
    assert shows[0].name == "The Example"
    assert shows[0].rating == 8.5


def test_http_errors_raise_api_error(config):
    """Translate transport and HTTP status errors for the CLI."""
    session = Mock()
    session.get.side_effect = requests.Timeout("timeout")
    service = TVMazeService(config, logging.getLogger("test.api"), session)

    with pytest.raises(ApiError, match="Could not reach"):
        service.search_shows("example")


def test_invalid_json_raises_api_error(config):
    """Handle a response that cannot be decoded as JSON."""
    session = Mock()
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("invalid json")
    session.get.return_value = response
    service = TVMazeService(config, logging.getLogger("test.api"), session)

    with pytest.raises(ApiError, match="invalid response"):
        service.search_shows("example")


def test_malformed_show_raises_api_error(config):
    """Reject incomplete external show data rather than exposing it."""
    session = Mock()
    response = Mock()
    response.json.return_value = [{"show": {"id": 1}}]
    session.get.return_value = response
    service = TVMazeService(config, logging.getLogger("test.api"), session)

    with pytest.raises(ApiError, match="unexpected format"):
        service.search_shows("example")
