"""Official public catalog clients normalized to the shared media model."""

from __future__ import annotations

import csv
import gzip
import logging
import math
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

import requests

from models.media_item import MediaItem, MediaType
from services.configuration_service import ApplicationConfig
from utils.exceptions import ApiError

TOP_MOVIES_LIMIT = 100
TMDB_PAGE_SIZE = 20
SEARCH_RESULT_LIMIT = 50
IMDB_RATINGS_FILE = "title.ratings.tsv.gz"
IMDB_BASICS_FILE = "title.basics.tsv.gz"


class HttpMediaProvider:
    """Shared HTTP behavior for supported media catalog services."""

    name = "Catalog"

    def __init__(
        self,
        config: ApplicationConfig,
        logger: logging.Logger,
        session: requests.Session | None = None,
    ) -> None:
        """Inject configuration, logging, and an optional HTTP session."""
        self._config = config
        self._logger = logger
        self._session = session or requests.Session()

    def _get(
        self,
        provider: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Request and decode one provider response with consistent errors."""
        base_url = self._config.provider_base_urls.get(provider)
        if not base_url:
            raise ApiError(f"{self.name} is not configured.")
        url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
        self._logger.info(
            "Sending catalog request",
            extra={"provider": self.name, "endpoint": path},
        )
        try:
            response = self._session.get(
                url,
                headers=headers,
                params=params,
                timeout=self._config.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            self._logger.exception("%s request failed", self.name)
            raise ApiError(
                f"Could not reach {self.name}. Please try again later."
            ) from error
        except ValueError as error:
            self._logger.exception("%s returned invalid JSON", self.name)
            raise ApiError(f"{self.name} returned an invalid response.") from error


class TmdbProvider(HttpMediaProvider):
    """Search TMDB movies and shows and retrieve its top-rated movies."""

    name = "TMDB"

    def search(self, term: str, media_type: MediaType) -> list[MediaItem]:
        """Search TMDB's movie or television catalog."""
        if media_type == "episode":
            raise ApiError("TMDB search supports movies and TV shows, not episodes.")
        token = os.environ.get("TMDB_ACCESS_TOKEN", "").strip()
        if not token:
            raise ApiError(
                "TMDB requires a read access token in TMDB_ACCESS_TOKEN."
            )
        category = "movie" if media_type == "movie" else "tv"
        payload = self._get(
            "tmdb",
            f"search/{category}",
            headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
            params={"query": term},
        )
        return [
            item
            for result in _results(payload, "TMDB")
            if (item := _tmdb_item(result, media_type, self._config)) is not None
        ]

    def top_movies(self, limit: int = TOP_MOVIES_LIMIT) -> list[MediaItem]:
        """Return the first 100 movies from TMDB's top-rated listing."""
        token = os.environ.get("TMDB_ACCESS_TOKEN", "").strip()
        if not token:
            raise ApiError(
                "TMDB requires a read access token in TMDB_ACCESS_TOKEN."
            )
        movies: list[MediaItem] = []
        page = 1
        while len(movies) < limit and page <= math.ceil(limit / TMDB_PAGE_SIZE):
            payload = self._get(
                "tmdb",
                "movie/top_rated",
                headers={
                    "Authorization": f"Bearer {token}",
                    "accept": "application/json",
                },
                params={"page": page},
            )
            movies.extend(
                item
                for result in _results(payload, "TMDB")
                if (item := _tmdb_item(result, "movie", self._config)) is not None
            )
            page += 1
        return movies[:limit]


class TraktProvider(HttpMediaProvider):
    """Search Trakt's public movie and television catalogs."""

    name = "Trakt"

    def search(self, term: str, media_type: MediaType) -> list[MediaItem]:
        """Search public Trakt records without accessing a user account."""
        client_id = os.environ.get("TRAKT_CLIENT_ID", "").strip()
        if not client_id:
            raise ApiError("Trakt requires an application id in TRAKT_CLIENT_ID.")
        category = {
            "movie": "movie",
            "show": "show",
            "episode": "episode",
        }[media_type]
        payload = self._get(
            "trakt",
            f"search/{category}",
            headers={
                "Content-Type": "application/json",
                "trakt-api-version": "2",
                "trakt-api-key": client_id,
            },
            params={"query": term, "limit": SEARCH_RESULT_LIMIT},
        )
        results = _list_payload(payload, "Trakt")
        items: list[MediaItem] = []
        for result in results:
            record = result.get(category)
            if not isinstance(record, dict):
                continue
            ids = record.get("ids")
            if not isinstance(ids, dict):
                continue
            title = record.get("title")
            slug = ids.get("slug")
            identifier = ids.get("trakt", slug)
            if media_type == "episode":
                show = result.get("show")
                if isinstance(show, dict) and isinstance(show.get("title"), str):
                    season = record.get("season")
                    number = record.get("number")
                    if isinstance(season, int) and isinstance(number, int):
                        title = f"{show['title']} · S{season:02d}E{number:02d} · {title or ''}"
                    else:
                        title = f"{show['title']} · {title or ''}"
            if (
                not isinstance(title, str)
                or not title.strip()
                or not _valid_identifier(identifier)
            ):
                continue
            items.append(
                MediaItem(
                    id=str(identifier),
                    title=title,
                    media_type=media_type,
                    source=self.name,
                    rating=_optional_rating(record.get("rating")),
                    year=_optional_year(record.get("year")),
                    url=_website_url(
                        self._config,
                        "trakt",
                        f"{'movies' if category == 'movie' else 'shows'}/{slug}",
                    )
                    if isinstance(slug, str) and category != "episode"
                    else None,
                )
            )
        return items

    def top_movies(self, limit: int) -> list[MediaItem]:
        """Report that Trakt has no ranked top-rated movie list in this client."""
        raise ApiError("Trakt does not provide a top-rated movie list.")


class SimklProvider(HttpMediaProvider):
    """Search Simkl's public movie and television catalogs."""

    name = "Simkl"

    def search(self, term: str, media_type: MediaType) -> list[MediaItem]:
        """Search public Simkl records without accessing a user account."""
        if media_type == "episode":
            raise ApiError("Simkl public search supports movies and shows, not episodes.")
        client_id = os.environ.get("SIMKL_CLIENT_ID", "").strip()
        if not client_id:
            raise ApiError("Simkl requires an application id in SIMKL_CLIENT_ID.")
        category = "movie" if media_type == "movie" else "tv"
        payload = self._get(
            "simkl",
            f"search/{category}",
            headers={"simkl-api-key": client_id, "Content-Type": "application/json"},
            params={"q": term, "extended": "full", "limit": SEARCH_RESULT_LIMIT},
        )
        results = _list_payload(payload, "Simkl")
        items: list[MediaItem] = []
        for result in results:
            record = result.get(category)
            if not isinstance(record, dict) and isinstance(result.get("title"), str):
                record = result
            if not isinstance(record, dict):
                continue
            ids = record.get("ids")
            title = record.get("title")
            identifier = ids.get("simkl") if isinstance(ids, dict) else None
            if (
                not isinstance(title, str)
                or not title.strip()
                or not _valid_identifier(identifier)
            ):
                continue
            items.append(
                MediaItem(
                    id=str(identifier),
                    title=title,
                    media_type=media_type,
                    source=self.name,
                    rating=_optional_rating(record.get("rating")),
                    year=_optional_year(record.get("year")),
                    url=_website_url(
                        self._config,
                        "simkl",
                        f"{'movies' if category == 'movie' else 'tv'}/{identifier}",
                    ),
                )
            )
        return items

    def top_movies(self, limit: int) -> list[MediaItem]:
        """Report that Simkl has no documented ranked movie list in this client."""
        raise ApiError("Simkl does not provide a top-rated movie list.")


class ImdbDatasetProvider:
    """Read the official IMDb non-commercial TSV snapshot files."""

    name = "IMDb"

    def __init__(
        self,
        config: ApplicationConfig,
        logger: logging.Logger,
        minimum_votes: int,
    ) -> None:
        """Inject logging for local dataset loading and validation."""
        self._config = config
        self._logger = logger
        self._minimum_votes_threshold = minimum_votes
        self._cached_directory: Path | None = None
        self._cached_movies: list[MediaItem] | None = None

    def search(self, term: str, media_type: MediaType) -> list[MediaItem]:
        """Filter the highest-rated IMDb movies using the local dataset files."""
        if media_type != "movie":
            raise ApiError("IMDb datasets in this app provide movie searches only.")
        return [
            item
            for item in self.top_movies(TOP_MOVIES_LIMIT)
            if term.casefold() in item.title.casefold()
        ]

    def top_movies(self, limit: int = TOP_MOVIES_LIMIT) -> list[MediaItem]:
        """Join IMDb ratings and title basics for the top qualifying movies."""
        directory = os.environ.get("IMDB_DATASET_DIRECTORY", "").strip()
        if not directory:
            raise ApiError(
                "Select the folder containing IMDb's title.ratings.tsv.gz and "
                "title.basics.tsv.gz files, or set IMDB_DATASET_DIRECTORY."
            )
        ratings_file = Path(directory) / IMDB_RATINGS_FILE
        basics_file = Path(directory) / IMDB_BASICS_FILE
        dataset_directory = Path(directory)
        if (
            self._cached_directory == dataset_directory
            and self._cached_movies is not None
        ):
            return self._cached_movies[:limit]
        if not ratings_file.is_file() or not basics_file.is_file():
            raise ApiError(
                "IMDb dataset folder must contain title.ratings.tsv.gz and "
                "title.basics.tsv.gz."
            )

        try:
            ratings: dict[str, tuple[float, int]] = {}
            with gzip.open(ratings_file, "rt", encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream, delimiter="\t"):
                    try:
                        votes = int(row["numVotes"])
                        rating = float(row["averageRating"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    title_id = row.get("tconst", "")
                    if title_id and votes >= self._minimum_votes_threshold and 0 <= rating <= 10:
                        ratings[title_id] = (rating, votes)
            ranked_movies: list[tuple[float, int, MediaItem]] = []
            with gzip.open(basics_file, "rt", encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream, delimiter="\t"):
                    title_id = row.get("tconst", "")
                    title = row.get("primaryTitle", "")
                    if (
                        title_id not in ratings
                        or row.get("titleType") != "movie"
                        or not title
                        or title == r"\N"
                    ):
                        continue
                    rating, votes = ratings[title_id]
                    year = _optional_year(row.get("startYear"))
                    ranked_movies.append(
                        (
                            rating,
                            votes,
                            MediaItem(
                            id=title_id,
                            title=title,
                            media_type="movie",
                            source=self.name,
                            rating=rating,
                            year=year,
                            url=_website_url(
                                self._config, "imdb", f"title/{title_id}/"
                            ),
                            ),
                        )
                    )
            ranked_movies.sort(key=lambda result: (result[0], result[1]), reverse=True)
            movies = [item for _rating, _votes, item in ranked_movies[:TOP_MOVIES_LIMIT]]
            self._cached_directory = dataset_directory
            self._cached_movies = movies
            return movies[:limit]
        except (OSError, EOFError, csv.Error) as error:
            self._logger.exception("Could not read IMDb dataset")
            raise ApiError("The IMDb dataset files could not be read.") from error

def _results(payload: Any, source: str) -> list[dict[str, Any]]:
    """Validate a paginated catalog response before item conversion."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ApiError(f"{source} returned data in an unexpected format.")
    return [result for result in payload["results"] if isinstance(result, dict)]


def _list_payload(payload: Any, source: str) -> list[dict[str, Any]]:
    """Validate a list catalog response before item conversion."""
    if not isinstance(payload, list):
        raise ApiError(f"{source} returned data in an unexpected format.")
    return [result for result in payload if isinstance(result, dict)]


def _tmdb_item(
    payload: dict[str, Any],
    media_type: MediaType,
    config: ApplicationConfig,
) -> MediaItem | None:
    """Normalize one TMDB movie or television response."""
    title = payload.get("title", payload.get("name"))
    identifier = payload.get("id")
    if (
        not isinstance(title, str)
        or not title.strip()
        or isinstance(identifier, bool)
        or not isinstance(identifier, int)
        or identifier <= 0
    ):
        return None
    date = payload.get("release_date", payload.get("first_air_date"))
    return MediaItem(
        id=str(identifier),
        title=title,
        media_type=media_type,
        source="TMDB",
        rating=_optional_rating(payload.get("vote_average")),
        year=_optional_year(date[:4] if isinstance(date, str) else None),
        overview=payload.get("overview") if isinstance(payload.get("overview"), str) else None,
        url=_website_url(
            config,
            "tmdb",
            f"{'movie' if media_type == 'movie' else 'tv'}/{identifier}",
        ),
    )


def _website_url(
    config: ApplicationConfig, provider: str, path: str
) -> str | None:
    """Build a provider website link only when that site is configured."""
    base_url = config.website_base_urls.get(provider)
    if not base_url:
        return None
    safe_path = quote(path.lstrip("/"), safe="/")
    return urljoin(base_url.rstrip("/") + "/", safe_path)


def _valid_identifier(value: Any) -> bool:
    """Accept only usable numeric IDs or non-empty slug strings."""
    if isinstance(value, bool):
        return False
    return isinstance(value, int) and value > 0 or isinstance(value, str) and bool(value.strip())


def _optional_rating(value: Any) -> float | None:
    """Convert a valid optional provider rating to the shared 0-10 scale."""
    try:
        rating = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return rating if 0 <= rating <= 10 else None


def _optional_year(value: Any) -> int | None:
    """Convert a valid year or date prefix into an integer year."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None
