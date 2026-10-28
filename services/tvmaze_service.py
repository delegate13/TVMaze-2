"""TVMaze HTTP client, isolated from command-line presentation."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import requests

from models.show import Show
from services.configuration_service import ApplicationConfig
from utils.exceptions import ApiError, ValidationError
from utils.validators import validate_api_response


class TVMazeService:
    """Search TVMaze using an injectable HTTP session and configuration."""

    def __init__(
        self,
        config: ApplicationConfig,
        logger: logging.Logger,
        session: requests.Session | None = None,
    ) -> None:
        """Initialize the service with configuration and HTTP dependencies."""
        self._config = config
        self._logger = logger
        self._session = session or requests.Session()
        self._search_url = urljoin(config.api_base_url, config.search_path)

    def search_shows(self, search_term: str) -> list[Show]:
        """Return shows matching a validated search phrase."""
        self._logger.info(
            "Sending TVMaze search request", extra={"search_term": search_term}
        )
        try:
            response = self._session.get(
                self._search_url,
                params={"q": search_term},
                timeout=self._config.timeout_seconds,
            )
            response.raise_for_status()
            payload: Any = response.json()
        except ValueError as error:
            self._logger.exception("TVMaze returned invalid JSON")
            raise ApiError("TVMaze returned an invalid response.") from error
        except requests.RequestException as error:
            self._logger.exception("TVMaze request failed")
            raise ApiError("Could not reach TVMaze. Please try again later.") from error

        try:
            validate_api_response(payload)
            return [Show.from_api_payload(item["show"]) for item in payload]
        except ValidationError as error:
            self._logger.exception("TVMaze response validation failed")
            raise ApiError("TVMaze returned data in an unexpected format.") from error
