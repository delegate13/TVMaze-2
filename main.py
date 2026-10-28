"""Application entry point for the TVMaze Show Finder."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from services.configuration_service import ApplicationConfig, ConfigurationService
from services.show_filter_service import ShowFilterService
from services.tvmaze_service import TVMazeService
from utils.exceptions import ApplicationError
from utils.json_explainer import explain_shows
from utils.logger import configure_logging
from utils.validators import validate_rating_threshold, validate_search_term

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "application.log"


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for the application."""
    parser = argparse.ArgumentParser(
        description="Search TVMaze for television shows and filter by rating."
    )
    parser.add_argument(
        "search_term",
        nargs="?",
        help="show title or search phrase (prompted when omitted)",
    )
    parser.add_argument(
        "--min-rating",
        help="optional minimum rating from 0 to 10",
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
        ):
            from ui.show_finder_window import launch_show_finder

            launch_show_finder(config=config, logger=logger)
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


def _run_cli(
    arguments: argparse.Namespace,
    config: ApplicationConfig,
    logger: logging.Logger,
) -> int:
    """Run one validated search in the command-line interface."""
    try:
        search_term = arguments.search_term
        if search_term is None:
            search_term = input("Enter a show name to search: ")
        search_term = validate_search_term(
            search_term, minimum_length=config.minimum_search_length
        )

        minimum_rating = None
        if arguments.min_rating is not None:
            minimum_rating = validate_rating_threshold(
                arguments.min_rating,
                minimum=config.rating_minimum,
                maximum=config.rating_maximum,
            )

        logger.info("User search", extra={"search_term": search_term})
        shows = TVMazeService(config=config, logger=logger).search_shows(search_term)
        if minimum_rating is not None:
            shows = ShowFilterService().filter_by_minimum_rating(
                shows, minimum_rating
            )

        if not shows:
            print("No shows matched your search and rating criteria.")
            return 0
        print(explain_shows(shows))
        return 0
    except ApplicationError as error:
        logger.exception("Application error")
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
