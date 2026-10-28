"""Loading and validating application configuration."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from utils.exceptions import ConfigurationError
from utils.validators import validate_configuration


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
        parsed_url = urlparse(data["api_base_url"])
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ConfigurationError(
                "api_base_url must be an absolute HTTP or HTTPS URL."
            )
        if not data["search_path"].strip():
            raise ConfigurationError("search_path cannot be blank.")

        return ApplicationConfig(
            api_base_url=data["api_base_url"].rstrip("/") + "/",
            search_path=data["search_path"].lstrip("/"),
            timeout_seconds=float(data["timeout_seconds"]),
            minimum_search_length=data["minimum_search_length"],
            rating_minimum=float(data["rating_minimum"]),
            rating_maximum=float(data["rating_maximum"]),
            log_level=data["log_level"].upper(),
        )
