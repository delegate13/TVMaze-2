"""Application entry point for Media Finder."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from services.configuration_service import ApplicationConfig, ConfigurationService
from services.media_discovery_service import (
    MediaDiscoveryService,
    TVMazeMediaProvider,
)
from services.media_providers import (
    ImdbDatasetProvider,
    SimklProvider,
    TmdbProvider,
    TraktProvider,
)
from services.tvmaze_service import TVMazeService
from utils.application_paths import get_default_config_path, get_log_file_path
from utils.exceptions import ApplicationError
from utils.json_explainer import explain_media_items
from utils.logger import configure_logging

DEFAULT_CONFIG_PATH = get_default_config_path()
DEFAULT_LOG_PATH = get_log_file_path()


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for the application."""
    parser = argparse.ArgumentParser(
        description="Discover movies, television shows, and episodes across catalogs."
    )
    parser.add_argument(
        "search_term",
        nargs="?",
        help="search phrase (prompted when omitted)",
    )
    parser.add_argument(
        "--min-rating",
        help="optional minimum rating from 0 to 10",
    )
    parser.add_argument(
        "--source",
        choices=("TVMaze", "TMDB", "Trakt", "Simkl", "IMDb"),
        default="TVMaze",
        help="catalog provider for CLI searches (default: TVMaze)",
    )
    parser.add_argument(
        "--media-type",
        choices=("movie", "show", "episode"),
        default="show",
        help="catalog category to search (default: show)",
    )
    parser.add_argument(
        "--top-movies",
        action="store_true",
        help="list the top 100 movies from TMDB or IMDb",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="path to a JSON configuration file",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="use the command-line interface instead of the desktop window",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the desktop interface by default or the optional CLI."""
    parser = build_argument_parser()
    arguments = parser.parse_args(argv)
    logger = configure_logging(DEFAULT_LOG_PATH)
    logger.info("Application startup")

    try:
        config = ConfigurationService(logger=logger).load(arguments.config)
        configure_logging(DEFAULT_LOG_PATH, level=config.log_level)

        if (
            not arguments.cli
            and arguments.search_term is None
            and arguments.min_rating is None
            and not arguments.top_movies
        ):
            from ui.show_finder_window import launch_show_finder

            launch_show_finder(
                config=config,
                logger=logger,
                search_service=_create_media_service(config, logger),
            )
            return 0

        return _run_cli(arguments, config, logger)
    except ApplicationError as error:
        logger.exception("Application error")
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        logger.warning("Application interrupted by user")
        print("\nSearch cancelled.", file=sys.stderr)
        return 130
    except Exception:
        logger.exception("Unexpected application exception")
        print("An unexpected error occurred. See the application log.", file=sys.stderr)
        return 1


def _create_media_service(
    config: ApplicationConfig, logger: logging.Logger
) -> MediaDiscoveryService:
    """Compose the source-independent media discovery service."""
    tvmaze = TVMazeService(config=config, logger=logger)
    providers = {
        "TVMaze": TVMazeMediaProvider(tvmaze),
        "TMDB": TmdbProvider(config, logger),
        "Trakt": TraktProvider(config, logger),
        "Simkl": SimklProvider(config, logger),
        "IMDb": ImdbDatasetProvider(config, logger, config.imdb_minimum_votes),
    }
    return MediaDiscoveryService(providers, config)


def _run_cli(
    arguments: argparse.Namespace,
    config: ApplicationConfig,
    logger: logging.Logger,
) -> int:
    """Run one validated catalog search or top-movies request in the CLI."""
    try:
        search_service = _create_media_service(config, logger)
        if arguments.top_movies:
            items = search_service.top_movies(arguments.source)
        else:
            search_term = arguments.search_term
            if search_term is None:
                search_term = input("Enter a title or search phrase: ")
            criteria = search_service.create_criteria(
                arguments.source,
                arguments.media_type,
                search_term,
                arguments.min_rating,
            )
            logger.info(
                "User search",
                extra={
                    "search_term": criteria.term,
                    "source": criteria.source,
                    "media_type": criteria.media_type,
                },
            )
            items = search_service.search_criteria(criteria)

        if not items:
            print("No media items matched your search and rating criteria.")
            return 0
        print(explain_media_items(items))
        return 0
    except ApplicationError as error:
        logger.exception("Application error")
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
