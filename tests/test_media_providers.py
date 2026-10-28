"""Unit tests for public provider clients and the local IMDb dataset reader."""

import csv
import gzip
import logging
from urllib.parse import urlparse

import pytest

from services.configuration_service import ApplicationConfig
from services.media_providers import (
    ImdbDatasetProvider,
    SimklProvider,
    TmdbProvider,
    TraktProvider,
)
from utils.exceptions import ApiError


class FakeResponse:
    """Provide a minimal requests.Response test double."""

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    """Capture requests and return configured JSON payloads."""

    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payloads.pop(0))


@pytest.fixture
def config():
    """Provide API and website base URLs without external requests."""
    return ApplicationConfig(
        api_base_url="https://api.tvmaze.test/",
        search_path="search/shows",
        timeout_seconds=2,
        minimum_search_length=2,
        rating_minimum=0,
        rating_maximum=10,
        log_level="INFO",
        provider_base_urls={
            "tmdb": "https://api.tmdb.test/3/",
            "trakt": "https://api.trakt.test/",
            "simkl": "https://api.simkl.test/",
        },
        website_base_urls={
            "tmdb": "https://www.tmdb.test/",
            "trakt": "https://trakt.test/",
            "simkl": "https://simkl.test/",
            "imdb": "https://imdb.test/",
        },
    )


def test_tmdb_search_uses_access_token_and_normalizes_movies(config, monkeypatch):
    """Send configured authentication and map the TMDB movie response."""
    monkeypatch.setenv("TMDB_ACCESS_TOKEN", "test-token")
    session = FakeSession(
        {
            "results": [
                {
                    "id": 42,
                    "title": "Sample Movie",
                    "vote_average": 8.5,
                    "release_date": "2020-05-01",
                    "overview": "Description",
                }
            ]
        }
    )

    movies = TmdbProvider(config, logging.getLogger("test.tmdb"), session).search(
        "Sample", "movie"
    )

    assert movies[0].title == "Sample Movie"
    assert movies[0].year == 2020
    assert movies[0].url == "https://www.tmdb.test/movie/42"
    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer test-token"


def test_tmdb_top_movies_fetches_multiple_pages(config, monkeypatch):
    """Collect and cap results across the pages required for 100 movies."""
    monkeypatch.setenv("TMDB_ACCESS_TOKEN", "test-token")
    session = FakeSession(
        *[
            {
                "results": [
                    {
                        "id": page * 20 + index,
                        "title": f"Movie {page}-{index}",
                        "vote_average": 7.5,
                    }
                    for index in range(20)
                ]
            }
            for page in range(1, 6)
        ]
    )

    movies = TmdbProvider(config, logging.getLogger("test.tmdb"), session).top_movies()

    assert len(movies) == 100
    assert len(session.calls) == 5


def test_tmdb_requires_credentials(config, monkeypatch):
    """Report a user-actionable setup error when no token is configured."""
    monkeypatch.delenv("TMDB_ACCESS_TOKEN", raising=False)

    with pytest.raises(ApiError, match="TMDB_ACCESS_TOKEN"):
        TmdbProvider(config, logging.getLogger("test.tmdb")).search("Sample", "movie")


def test_trakt_public_search_maps_show_results(config, monkeypatch):
    """Use a public Trakt application id and map its wrapped show response."""
    monkeypatch.setenv("TRAKT_CLIENT_ID", "client-id")
    session = FakeSession(
        [
            {
                "type": "show",
                "show": {
                    "title": "Sample Series",
                    "year": 2021,
                    "rating": 8.1,
                    "ids": {"trakt": 12, "slug": "sample-series"},
                },
            }
        ]
    )

    shows = TraktProvider(config, logging.getLogger("test.trakt"), session).search(
        "Sample", "show"
    )

    assert shows[0].title == "Sample Series"
    assert shows[0].url == "https://trakt.test/shows/sample-series"
    assert session.calls[0][1]["headers"]["trakt-api-key"] == "client-id"


def test_trakt_public_search_maps_episode_results(config, monkeypatch):
    """Include the parent show and episode number in public episode results."""
    monkeypatch.setenv("TRAKT_CLIENT_ID", "client-id")
    session = FakeSession(
        [
            {
                "type": "episode",
                "episode": {
                    "title": "Pilot",
                    "season": 1,
                    "number": 2,
                    "rating": 8.0,
                    "ids": {"trakt": 12},
                },
                "show": {"title": "Sample Series"},
            }
        ]
    )

    episodes = TraktProvider(config, logging.getLogger("test.trakt"), session).search(
        "Pilot", "episode"
    )

    assert episodes[0].title == "Sample Series · S01E02 · Pilot"
    assert episodes[0].media_type == "episode"
    assert episodes[0].url is None


def test_trakt_result_urls_cannot_override_configured_host(config, monkeypatch):
    """Keep generated result links on the configured provider domain."""
    monkeypatch.setenv("TRAKT_CLIENT_ID", "client-id")
    session = FakeSession(
        [
            {
                "show": {
                    "title": "Sample Series",
                    "ids": {"trakt": 12, "slug": "https://attacker.test/path"},
                }
            }
        ]
    )

    shows = TraktProvider(config, logging.getLogger("test.trakt"), session).search(
        "Sample", "show"
    )

    assert shows[0].url.startswith("https://trakt.test/")
    assert urlparse(shows[0].url).hostname == "trakt.test"


def test_simkl_public_search_maps_movie_results(config, monkeypatch):
    """Normalize a movie returned by Simkl's public search endpoint."""
    monkeypatch.setenv("SIMKL_CLIENT_ID", "client-id")
    session = FakeSession(
        [
            {
                "title": "Sample Film",
                "year": 2019,
                "rating": 7.2,
                "ids": {"simkl": 91},
            }
        ]
    )

    movies = SimklProvider(config, logging.getLogger("test.simkl"), session).search(
        "Sample", "movie"
    )

    assert movies[0].title == "Sample Film"
    assert movies[0].url == "https://simkl.test/movies/91"


def test_provider_rejects_malformed_response(config, monkeypatch):
    """Reject an unexpected API response rather than pretending it is empty."""
    monkeypatch.setenv("TMDB_ACCESS_TOKEN", "test-token")
    provider = TmdbProvider(
        config, logging.getLogger("test.tmdb"), FakeSession({"unexpected": []})
    )

    with pytest.raises(ApiError, match="unexpected format"):
        provider.search("Sample", "movie")


def test_imdb_dataset_ranks_movies_by_rating_and_votes(config, monkeypatch, tmp_path):
    """Join official-format IMDb TSV files and return the top eligible movies."""
    ratings_path = tmp_path / "title.ratings.tsv.gz"
    with gzip.open(ratings_path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("tconst", "averageRating", "numVotes"),
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(
            [
                {"tconst": "tt1", "averageRating": "8.0", "numVotes": "50000"},
                {"tconst": "tt2", "averageRating": "9.0", "numVotes": "40000"},
                {"tconst": "tt3", "averageRating": "10.0", "numVotes": "100"},
            ]
        )
    basics_path = tmp_path / "title.basics.tsv.gz"
    with gzip.open(basics_path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("tconst", "titleType", "primaryTitle", "startYear"),
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(
            [
                {"tconst": "tt1", "titleType": "movie", "primaryTitle": "First", "startYear": "2000"},
                {"tconst": "tt2", "titleType": "movie", "primaryTitle": "Second", "startYear": "2001"},
                {"tconst": "tt3", "titleType": "movie", "primaryTitle": "Low votes", "startYear": "2002"},
            ]
        )
    monkeypatch.setenv("IMDB_DATASET_DIRECTORY", str(tmp_path))

    provider = ImdbDatasetProvider(config, logging.getLogger("test.imdb"), 1000)
    movies = provider.top_movies()

    assert [movie.title for movie in movies] == ["Second", "First"]
    assert movies[0].url == "https://imdb.test/title/tt2/"
    assert provider.search("first", "movie")[0].title == "First"


def test_imdb_requires_both_official_dataset_files(config, monkeypatch, tmp_path):
    """Show an explicit setup error if the selected data folder is incomplete."""
    monkeypatch.setenv("IMDB_DATASET_DIRECTORY", str(tmp_path))
    provider = ImdbDatasetProvider(config, logging.getLogger("test.imdb"), 0)

    with pytest.raises(ApiError, match="title.ratings.tsv.gz"):
        provider.top_movies()
