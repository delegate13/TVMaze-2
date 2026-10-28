"""Tests for the Tkinter desktop presentation layer."""

import logging
import os
import tkinter as tk
from pathlib import Path

import pytest

from models.media_item import MediaItem
from services.configuration_service import ApplicationConfig
from services.media_discovery_service import (
    MediaDiscoveryService,
    MediaSearchCriteria,
)
from ui.show_finder_window import (
    ShowFinderWindow,
    _configure_tk_runtime,
    launch_show_finder,
)
from utils.exceptions import ApiError


def _widget_text(widget):
    """Collect visible text from a widget and its descendants."""
    try:
        text = widget.cget("text")
    except tk.TclError:
        text = ""
    return [str(text)] + [
        child_text
        for child in widget.winfo_children()
        for child_text in _widget_text(child)
    ]


def _finish_background_task(window):
    """Wait for a search worker and apply its queued result deterministically."""
    window._worker_thread.join(timeout=5)
    assert not window._worker_thread.is_alive()
    window._poll_search_result()


@pytest.fixture
def config():
    """Provide runtime configuration for GUI tests."""
    return ApplicationConfig(
        api_base_url="https://example.test/",
        search_path="search/shows",
        timeout_seconds=2,
        minimum_search_length=2,
        rating_minimum=0,
        rating_maximum=10,
        log_level="INFO",
    )


@pytest.fixture
def window(config):
    """Create a hidden desktop window so tests never disturb the user."""
    _configure_tk_runtime()
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk runtime is unavailable: {error}")
    root.withdraw()
    logger = logging.getLogger("test.gui")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    finder = ShowFinderWindow(
        root=root,
        config=config,
        logger=logger,
        search_service=MediaDiscoveryService(
            providers={
                "TVMaze": type(
                    "EmptyProvider",
                    (),
                    {
                        "search": lambda self, term, media_type: [],
                        "top_movies": lambda self, limit: [],
                    },
                )()
            },
            config=config,
        ),
    )
    yield finder
    root.destroy()


def test_window_has_friendly_initial_state(window):
    """Build the desktop window with a useful initial search prompt."""
    assert window._root.title() == "Media Finder | Movies, Shows & Episodes"
    assert window._status_var.get() == "Ready when you are."
    assert window._results_view._content.winfo_children()
    assert tuple(window._root.resizable()) == (1, 1)


def test_window_has_standard_menus(window):
    """Provide familiar desktop menus and common actions."""
    menu_bar = window._menu.menu_bar

    assert [
        menu_bar.entrycget(index, "label")
        for index in range(menu_bar.index("end") + 1)
    ] == ["File", "Edit", "View", "Navigate", "Help"]


def test_new_search_resets_controls_results_and_status(window):
    """Reset the form and results from the File menu's new-search action."""
    window._search_var.set("Example")
    window._rating_var.set("8+")
    window._count_var.set("3 shows")
    window._results_view.render(
        [MediaItem("1", "Example", "show", "TVMaze", 8.0)]
    )

    window._new_search()

    assert window._search_var.get() == ""
    assert window._rating_var.get() == "Any rating"
    assert window._count_var.get() == ""
    assert window._status_var.get() == "Ready when you are."
    assert "Start with a search" in _widget_text(window._results_view)


def test_clear_results_preserves_current_search(window):
    """Clear the visible results while preserving the active search phrase."""
    window._search_var.set("Example")
    window._count_var.set("1 show")
    window._results_view.render(
        [MediaItem("1", "Example", "show", "TVMaze", 8.0)]
    )

    window._clear_results_view()

    assert window._search_var.get() == "Example"
    assert window._count_var.get() == ""
    assert "Start with a search" in _widget_text(window._results_view)


def test_enter_key_reports_short_search_term(window):
    """Show inline validation feedback and avoid starting an invalid search."""
    result = window._on_enter_pressed(None)

    assert result == "break"
    assert "at least 2 characters" in window._status_var.get()
    assert not window._search_in_progress


def test_search_runs_in_background_and_renders_show_cards(window):
    """Search asynchronously and display rating, genres, summary, and link."""
    expected_item = MediaItem(
        "1",
        "Example",
        "show",
        "TVMaze",
        8.5,
        overview="<p>A good <b>story</b>.</p>",
        url="https://example.test/show",
    )

    class Service:
        provider_names = ("TVMaze",)

        def create_criteria(self, source, media_type, term, minimum_rating):
            assert term == "Example"
            return MediaSearchCriteria(source, media_type, term, minimum_rating)

        def search_criteria(self, criteria):
            return [expected_item]

        def top_movies(self, source):
            return []

    window._search_service = Service()
    window._search_var.set("Example")
    window._start_search()
    _finish_background_task(window)

    assert not window._search_in_progress
    assert window._count_var.get() == "1 result"
    assert window._status_var.get() == "Search complete"
    assert "Example" in _widget_text(window._results_view)
    assert "A good story." in _widget_text(window._results_view)
    assert "View on TVMaze  ↗" in _widget_text(window._results_view)
    assert len(window._results_view._summary_labels) == 1


def test_rating_filter_is_applied_before_display(window):
    """Respect the selected minimum rating in the UI search flow."""
    class Service:
        def search(self, search_term, media_type):
            return [
                MediaItem("1", "Low", "show", "TVMaze", 5.0),
                MediaItem("2", "High", "show", "TVMaze", 9.0),
            ]

    window._search_service = MediaDiscoveryService(
        {"TVMaze": Service()}, window._config
    )
    window._search_var.set("Example")
    window._rating_var.set("8+")
    window._start_search()
    _finish_background_task(window)

    assert window._count_var.get() == "1 result"
    assert "High" in _widget_text(window._results_view)


def test_empty_search_results_show_helpful_message(window):
    """Explain what to do when the API returns no matching shows."""
    class Service:
        provider_names = ("TVMaze",)

        def create_criteria(self, source, media_type, search_term, minimum_rating):
            return MediaSearchCriteria(source, media_type, search_term, minimum_rating)

        def search_criteria(self, criteria):
            return []

        def top_movies(self, source):
            return []

    window._search_service = Service()
    window._search_var.set("Missing")
    window._start_search()
    _finish_background_task(window)

    assert window._count_var.get() == "0 results"
    assert window._status_var.get() == "Search complete"


@pytest.mark.parametrize(
    ("exception_type", "error_detail", "message"),
    [
        (ApiError, "TVMaze is unavailable", "TVMaze is unavailable"),
        (RuntimeError, "internal detail", "Something went wrong"),
    ],
)
def test_search_errors_are_user_friendly(
    window, exception_type, error_detail, message
):
    """Display errors without exposing unexpected exception internals."""
    class Service:
        provider_names = ("TVMaze",)

        def create_criteria(self, source, media_type, search_term, minimum_rating):
            return MediaSearchCriteria(source, media_type, search_term, minimum_rating)

        def search_criteria(self, criteria):
            raise exception_type(error_detail)

        def top_movies(self, source):
            return []

    window._search_service = Service()
    window._search_var.set("Example")
    window._start_search()
    _finish_background_task(window)

    assert message in window._status_var.get()
    if exception_type is RuntimeError:
        assert "internal detail" not in window._status_var.get()


def test_canvas_resize_updates_result_width_and_summary_wrap(window):
    """Keep summary text responsive as the application window is resized."""
    window._results_view.render(
        [MediaItem("3", "Long Show", "show", "TVMaze", 7.0, overview="A summary")]
    )

    class Event:
        width = 520

    window._results_view._on_canvas_resized(Event())
    window._results_view._on_content_resized(None)

    assert window._results_view._summary_labels[0].cget("wraplength") == 450
    assert window._results_view._canvas.cget("scrollregion")


def test_launch_function_runs_the_desktop_event_loop(config, monkeypatch):
    """Create a root and enter the window event loop through the launcher."""
    root = object()
    launched = []
    monkeypatch.setattr("ui.show_finder_window.tk.Tk", lambda: root)
    class FakeWindow:
        def __init__(self, root, config, logger, search_service):
            launched.append((root, config, logger, search_service))

        def run(self):
            launched.append("run")

    monkeypatch.setattr("ui.show_finder_window.ShowFinderWindow", FakeWindow)

    logger = logging.getLogger("test.gui.launch")
    search_service = MediaDiscoveryService(
        providers={
            "TVMaze": type(
                "EmptyProvider",
                (),
                {
                    "search": lambda self, term, media_type: [],
                    "top_movies": lambda self, limit: [],
                },
            )()
        },
        config=config,
    )
    launch_show_finder(config, logger, search_service)

    assert launched == [(root, config, logger, search_service), "run"]


def test_tk_runtime_paths_are_discovered(monkeypatch):
    """Resolve Tcl/Tk script paths shipped under the Python install prefix."""
    monkeypatch.delenv("TCL_LIBRARY", raising=False)
    monkeypatch.delenv("TK_LIBRARY", raising=False)

    _configure_tk_runtime()

    assert (Path(os.environ["TCL_LIBRARY"]) / "init.tcl").is_file()
    assert (Path(os.environ["TK_LIBRARY"]) / "tk.tcl").is_file()
