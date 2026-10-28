"""Shared validation and orchestration for multi-source media discovery."""

from __future__ import annotations

from dataclasses import dataclass

from models.media_item import MediaItem, MediaType
from services.configuration_service import ApplicationConfig
from services.media_provider import MediaProvider
from services.tvmaze_service import TVMazeService
from utils.exceptions import ApiError
from utils.input_validators import validate_rating_threshold, validate_search_term

TOP_MOVIES_LIMIT = 100


@dataclass(frozen=True, slots=True)
class MediaSearchCriteria:
    """Validated inputs for one source-specific catalog search."""

    source: str
    media_type: MediaType
    term: str
    minimum_rating: float | None = None


class TVMazeMediaProvider:
    """Adapt the legacy TVMaze show client to the media-provider contract."""

    name = "TVMaze"

    def __init__(self, service: TVMazeService) -> None:
        """Inject the existing TVMaze API client."""
        self._service = service

    def search(self, term: str, media_type: MediaType) -> list[MediaItem]:
        """Convert TVMaze show search results into normalized media items."""
        if media_type != "show":
            raise ApiError("TVMaze search supports TV shows only.")
        return [
            MediaItem(
                id=str(show.id),
                title=show.name,
                media_type="show",
                source=self.name,
                rating=show.rating,
                overview=show.summary,
                url=show.url,
            )
            for show in self._service.search_shows(term)
        ]

    def top_movies(self, limit: int) -> list[MediaItem]:
        """TVMaze does not provide movie rankings."""
        return []


class MediaDiscoveryService:
    """Route searches to provider clients and apply shared rating filters."""

    def __init__(
        self,
        providers: dict[str, MediaProvider],
        config: ApplicationConfig,
    ) -> None:
        """Inject provider implementations and validated configuration."""
        self._providers = providers
        self._config = config

    @property
    def provider_names(self) -> tuple[str, ...]:
        """Return available provider labels in display order."""
        return tuple(self._providers)

    def search(
        self,
        source: str,
        media_type: MediaType,
        term: str,
        minimum_rating: object | None = None,
    ) -> list[MediaItem]:
        """Validate inputs, search one provider, and apply rating filtering."""
        return self.search_criteria(
            self.create_criteria(source, media_type, term, minimum_rating)
        )

    def create_criteria(
        self,
        source: str,
        media_type: MediaType,
        term: str,
        minimum_rating: object | None = None,
    ) -> MediaSearchCriteria:
        """Validate raw interface inputs and return search criteria."""
        normalized_term = validate_search_term(
            term, minimum_length=self._config.minimum_search_length
        )
        threshold = (
            None
            if minimum_rating is None
            else validate_rating_threshold(
                minimum_rating,
                minimum=self._config.rating_minimum,
                maximum=self._config.rating_maximum,
            )
        )
        self._provider(source)
        if media_type not in {"movie", "show", "episode"}:
            raise ApiError("Choose a supported media type.")
        return MediaSearchCriteria(source, media_type, normalized_term, threshold)

    def search_criteria(self, criteria: MediaSearchCriteria) -> list[MediaItem]:
        """Run validated criteria and filter unrated or low-rated results."""
        items = self._provider(criteria.source).search(
            criteria.term, criteria.media_type
        )
        if criteria.minimum_rating is None:
            return items
        return [
            item
            for item in items
            if item.rating is not None and item.rating >= criteria.minimum_rating
        ]

    def top_movies(self, source: str) -> list[MediaItem]:
        """Return up to 100 top-ranked movies from a supported provider."""
        items = self._provider(source).top_movies(TOP_MOVIES_LIMIT)
        if not items:
            raise ApiError(f"{source} does not provide a top movie list.")
        return items[:TOP_MOVIES_LIMIT]

    def _provider(self, source: str) -> MediaProvider:
        """Return the selected provider or a clear configuration error."""
        try:
            return self._providers[source]
        except KeyError as error:
            raise ApiError(f"{source} is not an available media provider.") from error
