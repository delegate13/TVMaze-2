"""Tests for the Tkinter desktop presentation layer."""

import logging
import tkinter as tk

import pytest

from models.show import Show
from services.configuration_service import ApplicationConfig
from ui.show_finder_window import ShowFinderWindow, launch_show_finder
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
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk runtime is unavailable: {error}")
    root.withdraw()
    finder = ShowFinderWindow(
        root=root,
        config=config,
        logger=logging.getLogger("test.gui"),
        service_factory=lambda config, logger: None,
    )
    yield finder
    root.destroy()


def test_window_has_friendly_initial_state(window):
    """Build the desktop window with a useful initial search prompt."""
    assert window._root.title() == "TVMaze | Show Finder"
    assert window._status_var.get() == "Ready when you are."
    assert window._results_frame.winfo_children()


def test_enter_key_reports_short_search_term(window):
    """Show inline validation feedback and avoid starting an invalid search."""
    result = window._on_enter_pressed(None)

    assert result == "break"
    assert "at least 2 characters" in window._status_var.get()
    assert not window._search_in_progress


def test_search_runs_in_background_and_renders_show_cards(window):
    """Search asynchronously and display rating, genres, summary, and link."""
    expected_show = Show(
        1,
        "Example",
        8.5,
        ("Drama", "Mystery"),
        "<p>A good <b>story</b>.</p>",
        "https://example.test/show",
    )

    class Service:
        def search_shows(self, search_term):
            assert search_term == "Example"
            return [expected_show]

    window._service = Service()
    window._search_var.set("Example")
    window._start_search()
    window._worker_thread.join(timeout=2)
    window._poll_search_result()

    assert not window._search_in_progress
    assert window._count_var.get() == "1 show"
    assert window._status_var.get() == "Search complete"
    assert "Example" in _widget_text(window._results_frame)
    assert "A good story." in _widget_text(window._results_frame)
    assert "View on TVMaze  ↗" in _widget_text(window._results_frame)
    assert len(window._summary_labels) == 1


def test_rating_filter_is_applied_before_display(window):
    """Respect the selected minimum rating in the UI search flow."""
    class Service:
        def search_shows(self, _search_term):
            return [
                Show(1, "Low", 5.0, (), None, None),
                Show(2, "High", 9.0, (), None, None),
            ]

    window._service = Service()
    window._search_var.set("Example")
    window._rating_var.set("8+")
    window._start_search()
    window._worker_thread.join(timeout=2)
    window._poll_search_result()

    assert window._count_var.get() == "1 show"
    assert "High" in _widget_text(window._results_frame)


def test_empty_search_results_show_helpful_message(window):
    """Explain what to do when the API returns no matching shows."""
    class Service:
        def search_shows(self, _search_term):
            return []

    window._service = Service()
    window._search_var.set("Missing")
    window._start_search()
    window._worker_thread.join(timeout=2)
    window._poll_search_result()

    assert window._count_var.get() == "0 shows"
    assert window._status_var.get() == "Search complete"


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (ApiError("TVMaze is unavailable"), "TVMaze is unavailable"),
        (RuntimeError("internal detail"), "Something went wrong"),
    ],
)
def test_search_errors_are_user_friendly(window, exception, message):
    """Display errors without exposing unexpected exception internals."""
    class Service:
        def search_shows(self, _search_term):
            raise exception

    window._service = Service()
    window._search_var.set("Example")
    window._start_search()
    window._worker_thread.join(timeout=2)
    window._poll_search_result()

    assert message in window._status_var.get()
    if isinstance(exception, RuntimeError):
        assert "internal detail" not in window._status_var.get()


def test_canvas_resize_updates_result_width_and_summary_wrap(window):
    """Keep summary text responsive as the application window is resized."""
    window._render_results(
        [Show(3, "Long Show", 7.0, (), "A summary", None)]
    )

    class Event:
        width = 520

    window._on_canvas_resized(Event())
    window._on_results_resized(None)

    assert window._summary_labels[0].cget("wraplength") == 450
    assert window._canvas.cget("scrollregion")


def test_launch_function_runs_the_desktop_event_loop(config, monkeypatch):
    """Create a root and enter the window event loop through the launcher."""
    root = object()
    launched = []
    monkeypatch.setattr("ui.show_finder_window.tk.Tk", lambda: root)
    class FakeWindow:
        def __init__(self, root, config, logger):
            launched.append((root, config, logger))

        def run(self):
            launched.append("run")

    monkeypatch.setattr("ui.show_finder_window.ShowFinderWindow", FakeWindow)

    logger = logging.getLogger("test.gui.launch")
    launch_show_finder(config, logger)

    assert launched == [(root, config, logger), "run"]
