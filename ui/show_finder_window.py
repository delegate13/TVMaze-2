"""Friendly desktop interface for multi-source media discovery."""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from models.media_item import MediaItem, MediaType
from services.configuration_service import ApplicationConfig
from services.media_discovery_service import (
    MediaDiscoveryService,
    MediaSearchCriteria,
)
from ui.menu_bar import MenuActions, ShowFinderMenu
from ui.results_view import ShowResultsView
from utils.exceptions import ApplicationError, ValidationError

BACKGROUND = "#F3F5F9"
SURFACE = "#FFFFFF"
INK = "#17233B"
MUTED = "#69758B"
ACCENT = "#5865E8"
ACCENT_HOVER = "#4855D4"
SUCCESS = "#16866A"
ERROR = "#B84045"
CARD_BORDER = "#E6EAF1"

SearchResult = tuple[list[MediaItem] | None, str | None]


class ShowFinderWindow:
    """Build and manage the Tkinter media discovery experience."""

    def __init__(
        self,
        root: tk.Tk,
        config: ApplicationConfig,
        logger: logging.Logger,
        search_service: MediaDiscoveryService,
    ) -> None:
        """Create the interface and inject its service dependencies."""
        self._root = root
        self._config = config
        self._logger = logger
        self._search_service = search_service
        self._search_results: queue.Queue[SearchResult] = queue.Queue()
        self._search_in_progress = False

        self._root.title("Media Finder | Movies, Shows & Episodes")
        self._root.geometry("980x760")
        self._root.minsize(680, 580)
        self._root.resizable(True, True)
        self._root.configure(background=BACKGROUND)
        self._configure_styles()
        self._build_layout()
        self._menu = ShowFinderMenu(
            root=self._root,
            search_entry=self._search_entry,
            actions=MenuActions(
                new_search=self._new_search,
                clear_results=self._clear_results_view,
                focus_search=self._focus_search,
                search=self._start_search,
                scroll_top=self._results_view.scroll_top,
                scroll_bottom=self._results_view.scroll_bottom,
                previous_page=self._results_view.previous_page,
                next_page=self._results_view.next_page,
            ),
        )
        self._root.bind("<Return>", self._on_enter_pressed)

    def run(self) -> None:
        """Start the desktop application's event loop."""
        self._root.mainloop()

    def _focus_search(self) -> None:
        """Move keyboard focus to the media search field."""
        self._search_entry.focus_set()

    def _new_search(self) -> None:
        """Reset the search controls and clear previously displayed items."""
        self._search_var.set("")
        self._rating_var.set("Any rating")
        self._clear_results_view()
        self._set_status("Ready when you are.", MUTED)
        self._focus_search()

    def _clear_results_view(self) -> None:
        """Clear displayed results without changing the current search text."""
        self._count_var.set("")
        self._results_view.show_empty_state(
            "Start with a search",
            "Choose a source and media type, then search a title or keyword.",
        )

    def _configure_styles(self) -> None:
        """Set a consistent, calm visual style for themed widgets."""
        style = ttk.Style(self._root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(
            "TFrame",
            background=BACKGROUND,
        )
        style.configure("Card.TFrame", background=SURFACE)
        style.configure(
            "TLabel",
            background=BACKGROUND,
            foreground=INK,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Title.TLabel",
            background=BACKGROUND,
            foreground=INK,
            font=("Segoe UI Semibold", 25),
        )
        style.configure(
            "Subtitle.TLabel",
            background=BACKGROUND,
            foreground=MUTED,
            font=("Segoe UI", 11),
        )
        style.configure(
            "CardTitle.TLabel",
            background=SURFACE,
            foreground=INK,
            font=("Segoe UI Semibold", 13),
        )
        style.configure(
            "CardMeta.TLabel",
            background=SURFACE,
            foreground=MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Section.TLabel",
            background=BACKGROUND,
            foreground=INK,
            font=("Segoe UI Semibold", 11),
        )
        style.configure(
            "Status.TLabel",
            background=BACKGROUND,
            foreground=MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "TEntry",
            fieldbackground=SURFACE,
            foreground=INK,
            padding=(11, 10),
            bordercolor=CARD_BORDER,
            lightcolor=CARD_BORDER,
            darkcolor=CARD_BORDER,
        )
        style.configure(
            "TCombobox",
            fieldbackground=SURFACE,
            foreground=INK,
            padding=(9, 8),
            bordercolor=CARD_BORDER,
            arrowcolor=MUTED,
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(20, 10),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Accent.TButton",
            background=[("active", ACCENT_HOVER), ("disabled", "#A9AFD8")],
            foreground=[("disabled", "#F8F8FC")],
        )
        style.configure(
            "Link.TButton",
            background=SURFACE,
            foreground=ACCENT,
            borderwidth=0,
            padding=(0, 3),
            font=("Segoe UI Semibold", 9),
        )
        style.map("Link.TButton", foreground=[("active", ACCENT_HOVER)])

    def _build_layout(self) -> None:
        """Create the header, search controls, status, and results region."""
        outer = ttk.Frame(self._root, padding=(42, 34, 42, 26))
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text="MEDIA FINDER  /  DISCOVER", foreground=ACCENT).pack(
            anchor=tk.W, pady=(0, 12)
        )
        ttk.Label(outer, text="Find your next favorite", style="Title.TLabel").pack(
            anchor=tk.W
        )
        ttk.Label(
            outer,
            text="Search movies, shows, and episodes across independent catalogs.",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, pady=(5, 23))

        search_panel = ttk.Frame(outer, style="Card.TFrame", padding=(18, 17))
        search_panel.pack(fill=tk.X)
        ttk.Label(search_panel, text="TITLE OR KEYWORD", style="CardMeta.TLabel").grid(
            row=0, column=0, sticky=tk.W, pady=(0, 7)
        )
        ttk.Label(search_panel, text="MEDIA TYPE", style="CardMeta.TLabel").grid(
            row=0, column=1, sticky=tk.W, padx=(12, 0), pady=(0, 7)
        )
        ttk.Label(search_panel, text="SOURCE", style="CardMeta.TLabel").grid(
            row=0, column=2, sticky=tk.W, padx=(12, 0), pady=(0, 7)
        )
        ttk.Label(search_panel, text="MINIMUM RATING", style="CardMeta.TLabel").grid(
            row=0, column=3, sticky=tk.W, padx=(12, 0), pady=(0, 7)
        )

        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(search_panel, textvariable=self._search_var)
        self._search_entry.grid(row=1, column=0, sticky=tk.EW)
        self._search_entry.configure(
            font=("Segoe UI", 11),
        )
        self._search_entry.insert(0, "")

        self._media_type_var = tk.StringVar(value="TV Shows")
        media_type_picker = ttk.Combobox(
            search_panel,
            textvariable=self._media_type_var,
            values=("Movies", "TV Shows", "Episodes"),
            state="readonly",
            width=12,
        )
        media_type_picker.grid(row=1, column=1, sticky=tk.EW, padx=(12, 0))

        self._source_var = tk.StringVar(value="TVMaze")
        source_picker = ttk.Combobox(
            search_panel,
            textvariable=self._source_var,
            values=self._search_service.provider_names,
            state="readonly",
            width=12,
        )
        source_picker.grid(row=1, column=2, sticky=tk.EW, padx=(12, 0))

        self._rating_var = tk.StringVar(value="Any rating")
        rating_options = {
            self._config.rating_minimum,
            self._config.rating_maximum,
            *(
                float(rating)
                for rating in range(
                    int(self._config.rating_minimum) + 1,
                    int(self._config.rating_maximum) + 1,
                )
            ),
        }
        rating_values = ["Any rating"] + [
            f"{rating:g}+"
            for rating in sorted(rating_options)
            if self._config.rating_minimum <= rating <= self._config.rating_maximum
        ]
        rating_picker = ttk.Combobox(
            search_panel,
            textvariable=self._rating_var,
            values=rating_values,
            state="readonly",
            width=14,
        )
        rating_picker.grid(row=1, column=3, sticky=tk.EW, padx=(12, 0))

        self._search_button = ttk.Button(
            search_panel,
            text="Search",
            style="Accent.TButton",
            command=self._start_search,
        )
        self._search_button.grid(row=1, column=4, sticky=tk.EW, padx=(12, 0))
        self._top_movies_button = ttk.Button(
            search_panel,
            text="Top 100 Movies",
            command=self._start_top_movies,
        )
        self._top_movies_button.grid(
            row=2, column=4, sticky=tk.EW, padx=(12, 8), pady=(9, 0)
        )
        search_panel.columnconfigure(0, weight=1)
        for column in range(1, 5):
            search_panel.columnconfigure(column, weight=0)

        status_row = ttk.Frame(outer)
        status_row.pack(fill=tk.X, pady=(17, 12))
        self._status_var = tk.StringVar(value="Ready when you are.")
        self._status_label = ttk.Label(
            status_row, textvariable=self._status_var, style="Status.TLabel"
        )
        self._status_label.pack(side=tk.LEFT)
        self._count_var = tk.StringVar()
        ttk.Label(
            status_row, textvariable=self._count_var, style="Status.TLabel"
        ).pack(side=tk.RIGHT)

        self._results_view = ShowResultsView(outer)
        self._results_view.pack(fill=tk.BOTH, expand=True)

    def _on_enter_pressed(self, _event: tk.Event) -> str:
        """Start a search when Enter is pressed from any search control."""
        self._start_search()
        return "break"

    def _start_search(self) -> None:
        """Validate current controls and launch a non-blocking API search."""
        if self._search_in_progress:
            return
        try:
            rating_text = self._rating_var.get()
            criteria = self._search_service.create_criteria(
                self._source_var.get(),
                self._selected_media_type(),
                self._search_var.get(),
                None if rating_text == "Any rating" else rating_text.removesuffix("+"),
            )
            self._prepare_imdb_source()
        except ValidationError as error:
            self._set_status(str(error), ERROR)
            self._search_entry.focus_set()
            return

        self._logger.info(
            "User search",
            extra={"search_term": criteria.term, "source": criteria.source},
        )
        self._search_in_progress = True
        self._search_button.configure(state=tk.DISABLED, text="Searching...")
        self._set_status(
            f"Searching {criteria.source}... This usually takes just a moment."
        )
        self._count_var.set("")
        self._show_loading_state()
        self._worker_thread = threading.Thread(
            target=self._search_worker,
            args=(criteria, None),
            name="media-search",
            daemon=True,
        )
        self._worker_thread.start()
        self._root.after(100, self._poll_search_result)

    def _start_top_movies(self) -> None:
        """Load a provider's top-rated movie list without blocking the GUI."""
        if self._search_in_progress:
            return
        source = self._source_var.get()
        if source not in {"TMDB", "IMDb"}:
            self._set_status(
                "Top 100 lists are available from TMDB and IMDb.", ERROR
            )
            return
        try:
            self._prepare_imdb_source()
        except ValidationError as error:
            self._set_status(str(error), ERROR)
            return
        self._search_in_progress = True
        self._search_button.configure(state=tk.DISABLED)
        self._top_movies_button.configure(state=tk.DISABLED)
        self._set_status(f"Loading {source}'s top movies...")
        self._count_var.set("")
        self._results_view.show_empty_state(
            "Loading top movies...",
            "Getting the latest rankings from the selected source.",
        )
        self._worker_thread = threading.Thread(
            target=self._search_worker,
            args=(None, source),
            name="top-movies-search",
            daemon=True,
        )
        self._worker_thread.start()
        self._root.after(100, self._poll_search_result)

    def _search_worker(
        self, criteria: MediaSearchCriteria | None, source: str | None
    ) -> None:
        """Perform network I/O off the UI thread and enqueue its result."""
        try:
            if criteria is None and source is not None:
                items = self._search_service.top_movies(source)
            elif criteria is not None:
                items = self._search_service.search_criteria(criteria)
            else:
                raise RuntimeError("Search worker received no operation.")
            self._search_results.put((items, None))
        except ApplicationError as error:
            self._logger.exception("Search failed")
            self._search_results.put((None, str(error)))
        except Exception:
            self._logger.exception("Unexpected error during GUI search")
            self._search_results.put(
                (None, "Something went wrong while searching. Please try again.")
            )

    def _poll_search_result(self) -> None:
        """Update widgets on the UI thread after the worker finishes."""
        try:
            items, error_message = self._search_results.get_nowait()
        except queue.Empty:
            self._root.after(100, self._poll_search_result)
            return

        self._search_in_progress = False
        self._search_button.configure(state=tk.NORMAL, text="Search")
        self._top_movies_button.configure(state=tk.NORMAL)
        if error_message:
            self._set_status(error_message, ERROR)
            self._count_var.set("")
            self._results_view.show_empty_state(
                "We couldn't complete that search",
                "Check your connection and try again in a moment.",
            )
            return

        assert items is not None
        count = len(items)
        self._count_var.set(f"{count} " + ("result" if count == 1 else "results"))
        if not items:
            self._set_status("Search complete", MUTED)
            self._results_view.show_empty_state(
                "No matching titles found",
                "Try another search, source, or minimum rating.",
            )
            return

        self._set_status("Search complete", SUCCESS)
        self._results_view.render(items)

    def _show_loading_state(self) -> None:
        """Replace old results with a friendly loading hint."""
        self._results_view.show_empty_state(
            "Finding matching titles...",
            "We’re searching the selected catalog.",
        )

    def _selected_media_type(self) -> MediaType:
        """Translate the user-facing media label to its provider value."""
        return {
            "Movies": "movie",
            "Episodes": "episode",
            "TV Shows": "show",
        }[self._media_type_var.get()]

    def _prepare_imdb_source(self) -> None:
        """Request the local folder containing IMDb's official dataset files."""
        if self._source_var.get() != "IMDb" or os.environ.get(
            "IMDB_DATASET_DIRECTORY"
        ):
            return
        directory = filedialog.askdirectory(
            parent=self._root,
            title="Select the folder containing IMDb dataset files",
        )
        if not directory:
            raise ValidationError("Select the folder containing the IMDb datasets.")
        os.environ["IMDB_DATASET_DIRECTORY"] = directory

    def _set_status(self, message: str, color: str = MUTED) -> None:
        """Update the concise feedback line above the results."""
        self._status_var.set(message)
        self._status_label.configure(foreground=color)

def launch_show_finder(
    config: ApplicationConfig,
    logger: logging.Logger,
    search_service: MediaDiscoveryService,
) -> None:
    """Create and display the multi-source desktop application window."""
    _configure_tk_runtime()
    root = tk.Tk()
    ShowFinderWindow(
        root=root,
        config=config,
        logger=logger,
        search_service=search_service,
    ).run()


def _configure_tk_runtime() -> None:
    """Locate Tcl/Tk script libraries bundled alongside standard Python."""
    install_tcl_directory = Path(sys.base_prefix) / "tcl"
    runtime_libraries = (
        ("TCL_LIBRARY", "init.tcl", "tcl8.*"),
        ("TK_LIBRARY", "tk.tcl", "tk8.*"),
    )
    for environment_key, required_script, directory_pattern in runtime_libraries:
        configured_path = os.environ.get(environment_key)
        if configured_path and (Path(configured_path) / required_script).is_file():
            continue

        library_path = next(
            (
                candidate
                for candidate in sorted(install_tcl_directory.glob(directory_pattern))
                if (candidate / required_script).is_file()
            ),
            None,
        )
        if library_path is not None:
            os.environ[environment_key] = str(library_path)
