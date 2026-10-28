"""Tests for CLI orchestration and user-facing error handling."""

import logging
from types import SimpleNamespace

import pytest

import main as application
from models.show import Show
from services.configuration_service import ApplicationConfig
from utils.exceptions import ConfigurationError


@pytest.fixture
def configured_cli(monkeypatch):
    """Replace runtime dependencies so CLI tests never perform network I/O."""
    logger = logging.getLogger("test.cli")
    config = ApplicationConfig(
        api_base_url="https://example.test/",
        search_path="search/shows",
        timeout_seconds=2,
        minimum_search_length=2,
        rating_minimum=0,
        rating_maximum=10,
        log_level="INFO",
    )
    shows = [Show(1, "Example", 8.0, ("Drama",), None, None)]
    monkeypatch.setattr(application, "configure_logging", lambda *args, **kwargs: logger)
    monkeypatch.setattr(
        application.ConfigurationService,
        "load",
        lambda self, path: config,
    )
    monkeypatch.setattr(
        application,
        "TVMazeService",
        lambda config, logger: SimpleNamespace(
            search_shows=lambda search_term: shows
        ),
    )
    return logger


def test_main_prints_search_results(configured_cli, capsys):
    """Print successful search results and return a success exit code."""
    assert application.main(["Example"]) == 0
    assert "Example (ID: 1)" in capsys.readouterr().out


def test_main_opens_desktop_interface_by_default(configured_cli, monkeypatch):
    """Launch the GUI when no CLI search arguments are supplied."""
    launched = []
    monkeypatch.setattr(
        "ui.show_finder_window.launch_show_finder",
        lambda config, logger: launched.append((config, logger)),
    )

    assert application.main([]) == 0
    assert len(launched) == 1


def test_main_keeps_cli_available_with_explicit_flag(configured_cli, capsys):
    """Use the command-line interface when the caller opts in."""
    assert application.main(["--cli", "Example"]) == 0
    assert "Example (ID: 1)" in capsys.readouterr().out


def test_main_filters_search_results(configured_cli, capsys):
    """Apply a valid optional rating threshold before rendering results."""
    assert application.main(["Example", "--min-rating", "9"]) == 0
    assert "No shows matched" in capsys.readouterr().out


def test_main_reports_application_errors(configured_cli, monkeypatch, capsys):
    """Display expected application failures without a traceback on stdout."""
    monkeypatch.setattr(
        application.ConfigurationService,
        "load",
        lambda self, path: (_ for _ in ()).throw(ConfigurationError("bad config")),
    )

    assert application.main(["Example"]) == 1
    assert "Error: bad config" in capsys.readouterr().err


def test_main_handles_unexpected_errors(configured_cli, monkeypatch, capsys):
    """Log unexpected failures and show a generic safe message."""
    monkeypatch.setattr(
        application.ConfigurationService,
        "load",
        lambda self, path: (_ for _ in ()).throw(RuntimeError("internal detail")),
    )

    assert application.main(["Example"]) == 1
    output = capsys.readouterr().err
    assert "unexpected error occurred" in output
    assert "internal detail" not in output


def test_main_handles_interrupted_prompt(configured_cli, monkeypatch, capsys):
    """Return the standard interrupt exit code when input is cancelled."""
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    assert application.main(["--cli"]) == 130
    assert "Search cancelled" in capsys.readouterr().err
