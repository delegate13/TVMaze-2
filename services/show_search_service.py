"""Application use case for validating, retrieving, and filtering shows."""

from __future__ import annotations

from dataclasses import dataclass

from models.show import Show
from services.configuration_service import ApplicationConfig
from services.provider import ShowSearchProvider
from services.show_filter_service import ShowFilterService
from utils.input_validators import validate_rating_threshold, validate_search_term


@dataclass(frozen=True, slots=True)
class SearchCriteria:
    """Validated user criteria shared by GUI and command-line interfaces."""

    search_term: str
    minimum_rating: float | None = None


class ShowSearchService:
    """Coordinate query validation, API-provider access, and rating filtering."""

    def __init__(
        self,
        provider: ShowSearchProvider,
        config: ApplicationConfig,
        filter_service: ShowFilterService | None = None,
    ) -> None:
        """Inject the provider, configuration, and optional filtering service."""
        self._provider = provider
        self._config = config
        self._filter_service = (
            filter_service if filter_service is not None else ShowFilterService()
        )

    def create_criteria(
        self, search_term: str, minimum_rating: object | None = None
    ) -> SearchCriteria:
        """Validate raw interface inputs and return shared search criteria."""
        normalized_term = validate_search_term(
            search_term,
            minimum_length=self._config.minimum_search_length,
        )
        rating = (
            None
            if minimum_rating is None
            else validate_rating_threshold(
                minimum_rating,
                minimum=self._config.rating_minimum,
                maximum=self._config.rating_maximum,
            )
        )
        return SearchCriteria(normalized_term, rating)

    def search(self, criteria: SearchCriteria) -> list[Show]:
        """Search the configured provider and apply the optional rating filter."""
        shows = self._provider.search_shows(criteria.search_term)
        if criteria.minimum_rating is None:
            return shows
        return self._filter_service.filter_by_minimum_rating(
            shows, criteria.minimum_rating
        )
