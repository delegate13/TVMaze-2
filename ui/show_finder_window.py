"""Friendly desktop interface for searching TVMaze."""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk

from models.show import Show
from services.configuration_service import ApplicationConfig
from services.show_filter_service import ShowFilterService
from services.tvmaze_service import TVMazeService
from utils.exceptions import ApplicationError, ValidationError
from utils.json_explainer import clean_summary
from utils.validators import validate_rating_threshold, validate_search_term

BACKGROUND = "#F3F5F9"
SURFACE = "#FFFFFF"
INK = "#17233B"
MUTED = "#69758B"
ACCENT = "#5865E8"
ACCENT_HOVER = "#4855D4"
SUCCESS = "#16866A"
ERROR = "#B84045"
CARD_BORDER = "#E6EAF1"

SearchResult = tuple[list[Show] | None, str | None]


class ShowFinderWindow:
    """Build and manage the Tkinter show search experience."""

    def __init__(
        self,
        root: tk.Tk,
        config: ApplicationConfig,
        logger: logging.Logger,
        service_factory: Callable[
            [ApplicationConfig, logging.Logger], TVMazeService
        ] = TVMazeService,
    ) -> None:
        """Create the interface and inject its service dependencies."""
        self._root = root
        self._config = config
        self._logger = logger
        self._service = service_factory(config, logger)
        self._filter_service = ShowFilterService()
        self._results: queue.Queue[SearchResult] = queue.Queue()
        self._search_in_progress = False
        self._summary_labels: list[ttk.Label] = []

        self._root.title("TVMaze | Show Finder")
        self._root.geometry("980x760")
        self._root.minsize(680, 580)
        self._root.resizable(True, True)
        self._root.configure(background=BACKGROUND)
        self._configure_styles()
        self._build_menu_bar()
        self._build_layout()
        self._root.bind("<Return>", self._on_enter_pressed)
        self._root.bind_all("<Control-n>", self._on_new_search_shortcut)
        self._root.bind_all("<Control-f>", self._on_focus_search_shortcut)
        self._root.bind_all("<Control-l>", self._on_clear_results_shortcut)
        self._root.bind_all("<Control-a>", self._on_select_all_shortcut)

    def run(self) -> None:
        """Start the desktop application's event loop."""
        self._root.mainloop()

    def _build_menu_bar(self) -> None:
        """Create standard application menus and their keyboard accelerators."""
        self._menu_bar = tk.Menu(self._root, tearoff=False)
        self._root.configure(menu=self._menu_bar)

        file_menu = tk.Menu(self._menu_bar, tearoff=False)
        file_menu.add_command(
            label="New Search",
            accelerator="Ctrl+N",
            command=self._new_search,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self._root.destroy)
        self._menu_bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(self._menu_bar, tearoff=False)
        edit_menu.add_command(
            label="Cut",
            accelerator="Ctrl+X",
            command=lambda: self._edit_search_entry("<<Cut>>"),
        )
        edit_menu.add_command(
            label="Copy",
            accelerator="Ctrl+C",
            command=lambda: self._edit_search_entry("<<Copy>>"),
        )
        edit_menu.add_command(
            label="Paste",
            accelerator="Ctrl+V",
            command=lambda: self._edit_search_entry("<<Paste>>"),
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Select All",
            accelerator="Ctrl+A",
            command=self._select_all_search_text,
        )
        self._menu_bar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(self._menu_bar, tearoff=False)
        view_menu.add_command(
            label="Clear Results",
            accelerator="Ctrl+L",
            command=self._clear_results_view,
        )
        view_menu.add_command(
            label="Scroll to Top",
            accelerator="Home",
            command=lambda: self._canvas.yview_moveto(0),
        )
        view_menu.add_command(
            label="Scroll to Bottom",
            accelerator="End",
            command=lambda: self._canvas.yview_moveto(1),
        )
        self._menu_bar.add_cascade(label="View", menu=view_menu)

        navigate_menu = tk.Menu(self._menu_bar, tearoff=False)
        navigate_menu.add_command(
            label="Focus Search",
            accelerator="Ctrl+F",
            command=self._focus_search,
        )
        navigate_menu.add_command(
            label="Search Shows",
            accelerator="Enter",
            command=self._start_search,
        )
        navigate_menu.add_command(
            label="Previous Page",
            accelerator="Page Up",
            command=lambda: self._canvas.yview_scroll(-1, "pages"),
        )
        navigate_menu.add_command(
            label="Next Page",
            accelerator="Page Down",
            command=lambda: self._canvas.yview_scroll(1, "pages"),
        )
        self._menu_bar.add_cascade(label="Navigate", menu=navigate_menu)

        help_menu = tk.Menu(self._menu_bar, tearoff=False)
        help_menu.add_command(
            label="TVMaze Website",
            command=lambda: webbrowser.open(self._config.api_base_url),
        )
        help_menu.add_command(label="About TVMaze Show Finder", command=self._show_about)
        self._menu_bar.add_cascade(label="Help", menu=help_menu)

    def _edit_search_entry(self, virtual_event: str) -> None:
        """Apply a standard clipboard operation to the search field."""
        self._search_entry.focus_set()
        self._search_entry.event_generate(virtual_event)

    def _select_all_search_text(self) -> None:
        """Select all text in the search field and focus it."""
        self._search_entry.focus_set()
        self._search_entry.selection_range(0, tk.END)
        self._search_entry.icursor(tk.END)

    def _focus_search(self) -> None:
        """Move keyboard focus to the show search field."""
        self._search_entry.focus_set()

    def _new_search(self) -> None:
        """Reset the search controls and clear previously displayed shows."""
        self._search_var.set("")
        self._rating_var.set("Any rating")
        self._clear_results_view()
        self._set_status("Ready when you are.", MUTED)
        self._focus_search()

    def _clear_results_view(self) -> None:
        """Clear displayed results without changing the current search text."""
        self._clear_results()
        self._count_var.set("")
        self._show_empty_state(
            "Start with a search",
            "Type a show title or a couple of keywords above to get started.",
        )

    def _show_about(self) -> None:
        """Display application information in a native dialog."""
        messagebox.showinfo(
            "About TVMaze Show Finder",
            "TVMaze Show Finder\n"
            "Discover television shows with ratings, genres, and summaries.\n\n"
            "Show information is provided by TVMaze.",
            parent=self._root,
        )

    def _on_new_search_shortcut(self, _event: tk.Event) -> str:
        """Handle Ctrl+N to reset the search form."""
        self._new_search()
        return "break"

    def _on_focus_search_shortcut(self, _event: tk.Event) -> str:
        """Handle Ctrl+F to focus the search field."""
        self._focus_search()
        return "break"

    def _on_clear_results_shortcut(self, _event: tk.Event) -> str:
        """Handle Ctrl+L to clear displayed results."""
        self._clear_results_view()
        return "break"

    def _on_select_all_shortcut(self, _event: tk.Event) -> str:
        """Handle Ctrl+A by selecting the search text."""
        self._select_all_search_text()
        return "break"

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

        ttk.Label(outer, text="TVMAZE  /  DISCOVER", foreground=ACCENT).pack(
            anchor=tk.W, pady=(0, 12)
        )
        ttk.Label(outer, text="Find your next favorite show", style="Title.TLabel").pack(
            anchor=tk.W
        )
        ttk.Label(
            outer,
            text="Search thousands of shows, then narrow the list by rating.",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, pady=(5, 23))

        search_panel = ttk.Frame(outer, style="Card.TFrame", padding=(18, 17))
        search_panel.pack(fill=tk.X)
        ttk.Label(search_panel, text="SHOW OR KEYWORD", style="CardMeta.TLabel").grid(
            row=0, column=0, sticky=tk.W, pady=(0, 7)
        )
        ttk.Label(search_panel, text="MINIMUM RATING", style="CardMeta.TLabel").grid(
            row=0, column=1, sticky=tk.W, padx=(12, 0), pady=(0, 7)
        )

        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(search_panel, textvariable=self._search_var)
        self._search_entry.grid(row=1, column=0, sticky=tk.EW)
        self._search_entry.configure(
            font=("Segoe UI", 11),
        )
        self._search_entry.insert(0, "")

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
        rating_picker.grid(row=1, column=1, sticky=tk.EW, padx=(12, 0))

        self._search_button = ttk.Button(
            search_panel,
            text="Search shows",
            style="Accent.TButton",
            command=self._start_search,
        )
        self._search_button.grid(row=1, column=2, sticky=tk.EW, padx=(12, 0))
        search_panel.columnconfigure(0, weight=1)
        search_panel.columnconfigure(1, weight=0)

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

        results_shell = ttk.Frame(outer)
        results_shell.pack(fill=tk.BOTH, expand=True)
        self._canvas = tk.Canvas(
            results_shell,
            background=BACKGROUND,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            results_shell, orient=tk.VERTICAL, command=self._canvas.yview
        )
        self._results_frame = ttk.Frame(self._canvas)
        self._results_window = self._canvas.create_window(
            (0, 0), window=self._results_frame, anchor=tk.NW
        )
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._results_frame.bind("<Configure>", self._on_results_resized)
        self._canvas.bind("<Configure>", self._on_canvas_resized)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._show_empty_state(
            "Start with a search",
            "Type a show title or a couple of keywords above to get started.",
        )

    def _on_enter_pressed(self, _event: tk.Event) -> str:
        """Start a search when Enter is pressed from any search control."""
        self._start_search()
        return "break"

    def _start_search(self) -> None:
        """Validate current controls and launch a non-blocking API search."""
        if self._search_in_progress:
            return
        try:
            search_term = validate_search_term(
                self._search_var.get(),
                minimum_length=self._config.minimum_search_length,
            )
            rating_text = self._rating_var.get()
            minimum_rating = (
                None
                if rating_text == "Any rating"
                else validate_rating_threshold(
                    rating_text.removesuffix("+"),
                    minimum=self._config.rating_minimum,
                    maximum=self._config.rating_maximum,
                )
            )
        except ValidationError as error:
            self._set_status(str(error), ERROR)
            self._search_entry.focus_set()
            return

        self._logger.info("User search", extra={"search_term": search_term})
        self._search_in_progress = True
        self._search_button.configure(state=tk.DISABLED, text="Searching...")
        self._set_status("Searching TVMaze... This usually takes just a moment.")
        self._count_var.set("")
        self._show_loading_state()
        self._worker_thread = threading.Thread(
            target=self._search_worker,
            args=(search_term, minimum_rating),
            name="tvmaze-search",
            daemon=True,
        )
        self._worker_thread.start()
        self._root.after(100, self._poll_search_result)

    def _search_worker(self, search_term: str, minimum_rating: float | None) -> None:
        """Perform network I/O off the UI thread and enqueue its result."""
        try:
            shows = self._service.search_shows(search_term)
            if minimum_rating is not None:
                shows = self._filter_service.filter_by_minimum_rating(
                    shows, minimum_rating
                )
            self._results.put((shows, None))
        except ApplicationError as error:
            self._logger.exception("Search failed")
            self._results.put((None, str(error)))
        except Exception:
            self._logger.exception("Unexpected error during GUI search")
            self._results.put(
                (None, "Something went wrong while searching. Please try again.")
            )

    def _poll_search_result(self) -> None:
        """Update widgets on the UI thread after the worker finishes."""
        try:
            shows, error_message = self._results.get_nowait()
        except queue.Empty:
            self._root.after(100, self._poll_search_result)
            return

        self._search_in_progress = False
        self._search_button.configure(state=tk.NORMAL, text="Search shows")
        if error_message:
            self._set_status(error_message, ERROR)
            self._count_var.set("")
            self._show_empty_state(
                "We couldn't complete that search",
                "Check your connection and try again in a moment.",
            )
            return

        assert shows is not None
        count = len(shows)
        self._count_var.set(f"{count} " + ("show" if count == 1 else "shows"))
        if not shows:
            self._set_status("Search complete", MUTED)
            self._show_empty_state(
                "No shows found",
                "Try a different title or choose a lower minimum rating.",
            )
            return

        self._set_status("Search complete", SUCCESS)
        self._render_results(shows)

    def _render_results(self, shows: list[Show]) -> None:
        """Render show cards into the scrollable results area."""
        self._clear_results()
        for show in shows:
            card = ttk.Frame(
                self._results_frame,
                style="Card.TFrame",
                padding=(18, 15),
            )
            card.pack(fill=tk.X, pady=(0, 10))
            top_row = ttk.Frame(card, style="Card.TFrame")
            top_row.pack(fill=tk.X)
            ttk.Label(top_row, text=show.name, style="CardTitle.TLabel").pack(
                side=tk.LEFT, anchor=tk.W
            )
            rating_text = (
                f"★  {show.rating:g} / 10"
                if show.rating is not None
                else "Not rated"
            )
            rating_color = SUCCESS if show.rating is not None else MUTED
            rating_label = ttk.Label(
                top_row,
                text=rating_text,
                style="CardMeta.TLabel",
                foreground=rating_color,
            )
            rating_label.pack(side=tk.RIGHT, anchor=tk.E)

            genre_text = "  ·  ".join(show.genres) if show.genres else "No genres listed"
            ttk.Label(
                card,
                text=genre_text,
                style="CardMeta.TLabel",
            ).pack(anchor=tk.W, pady=(5, 0))
            summary = clean_summary(show.summary) if show.summary else ""
            if summary:
                summary_text = summary if len(summary) <= 400 else summary[:397] + "..."
                summary_label = ttk.Label(
                    card,
                    text=summary_text,
                    style="CardMeta.TLabel",
                    wraplength=max(300, self._canvas.winfo_width() - 70),
                    justify=tk.LEFT,
                )
                summary_label.pack(anchor=tk.W, fill=tk.X, pady=(10, 0))
                self._summary_labels.append(summary_label)
            if show.url and show.url.startswith(("https://", "http://")):
                ttk.Button(
                    card,
                    text="View on TVMaze  ↗",
                    style="Link.TButton",
                    command=lambda url=show.url: webbrowser.open(url),
                ).pack(anchor=tk.W, pady=(7, 0))

    def _show_loading_state(self) -> None:
        """Replace old results with a friendly loading hint."""
        self._show_empty_state(
            "Finding your shows...",
            "We’re checking TVMaze for matching titles.",
        )

    def _show_empty_state(self, title: str, message: str) -> None:
        """Display an informative placeholder in the results pane."""
        self._clear_results()
        empty_panel = ttk.Frame(
            self._results_frame,
            style="Card.TFrame",
            padding=(24, 28),
        )
        empty_panel.pack(fill=tk.X)
        ttk.Label(
            empty_panel,
            text=title,
            style="CardTitle.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            empty_panel,
            text=message,
            style="CardMeta.TLabel",
        ).pack(anchor=tk.W, pady=(7, 0))

    def _clear_results(self) -> None:
        """Remove previous cards and placeholders."""
        for child in self._results_frame.winfo_children():
            child.destroy()
        self._summary_labels.clear()

    def _set_status(self, message: str, color: str = MUTED) -> None:
        """Update the concise feedback line above the results."""
        self._status_var.set(message)
        self._status_label.configure(foreground=color)

    def _on_results_resized(self, _event: tk.Event) -> None:
        """Keep the scrollable content region sized to its children."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resized(self, event: tk.Event) -> None:
        """Keep result cards aligned to the available window width."""
        self._canvas.itemconfigure(self._results_window, width=event.width)
        wraplength = max(300, event.width - 70)
        for label in self._summary_labels:
            label.configure(wraplength=wraplength)


def launch_show_finder(config: ApplicationConfig, logger: logging.Logger) -> None:
    """Create and display the desktop application window."""
    _configure_tk_runtime()
    root = tk.Tk()
    ShowFinderWindow(root=root, config=config, logger=logger).run()


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
