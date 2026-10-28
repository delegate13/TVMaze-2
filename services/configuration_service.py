"""Loading and validating application configuration."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from utils.configuration_validators import validate_configuration
from utils.exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class ApplicationConfig:
    """Immutable runtime settings loaded from JSON."""

    api_base_url: str
    search_path: str
    timeout_seconds: float
    minimum_search_length: int
    rating_minimum: float
    rating_maximum: float
    log_level: str
    provider_base_urls: Mapping[str, str] = field(default_factory=dict)
    imdb_minimum_votes: int = 25_000
    website_base_urls: Mapping[str, str] = field(default_factory=dict)


class ConfigurationService:
    """Read configuration files and convert them into typed settings."""

    def __init__(self, logger: logging.Logger) -> None:
        """Initialize the service with its logging dependency."""
        self._logger = logger

    def load(self, config_path: Path) -> ApplicationConfig:
        """Load, validate, and return configuration from a JSON file."""
        self._logger.info("Loading configuration", extra={"config_path": str(config_path)})
        try:
            with config_path.open(encoding="utf-8") as config_file:
                data: Any = json.load(config_file)
        except FileNotFoundError as error:
            self._logger.error("Configuration file not found: %s", config_path)
            raise ConfigurationError(
                f"Configuration file was not found: {config_path}"
            ) from error
        except (OSError, json.JSONDecodeError) as error:
            self._logger.exception("Could not read configuration file")
            raise ConfigurationError(
                f"Could not read configuration file: {error}"
            ) from error

        validate_configuration(data)

        return ApplicationConfig(
            api_base_url=data["api_base_url"].rstrip("/") + "/",
            search_path=data["search_path"].lstrip("/"),
            timeout_seconds=float(data["timeout_seconds"]),
            minimum_search_length=data["minimum_search_length"],
            rating_minimum=float(data["rating_minimum"]),
            rating_maximum=float(data["rating_maximum"]),
            log_level=data["log_level"].upper(),
            provider_base_urls=data.get("provider_base_urls", {}),
            imdb_minimum_votes=data.get("imdb_minimum_votes", 25_000),
            website_base_urls=data.get("website_base_urls", {}),
        )
