"""Build the desktop application's menus independently of the main window."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import messagebox, ttk

from version import __version__


@dataclass(frozen=True, slots=True)
class MenuActions:
    """Callbacks needed to connect menus to application behavior."""

    new_search: Callable[[], None]
    clear_results: Callable[[], None]
    focus_search: Callable[[], None]
    search: Callable[[], None]
    scroll_top: Callable[[], None]
    scroll_bottom: Callable[[], None]
    previous_page: Callable[[], None]
    next_page: Callable[[], None]


class ShowFinderMenu:
    """Create standard menus for the show finder window."""

    def __init__(
        self,
        root: tk.Tk,
        search_entry: ttk.Entry,
        actions: MenuActions,
    ) -> None:
        """Attach menus and keyboard shortcuts to the provided window."""
        self._root = root
        self._search_entry = search_entry
        self._actions = actions
        self.menu_bar = self._build()

    def _build(self) -> tk.Menu:
        """Construct File, Edit, View, Navigate, and Help menus."""
        menu_bar = tk.Menu(self._root, tearoff=False)
        self._root.configure(menu=menu_bar)

        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(
            label="New Search",
            accelerator="Ctrl+N",
            command=self._actions.new_search,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Exit",
            accelerator="Alt+F4",
            command=self._root.destroy,
        )
        menu_bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu_bar, tearoff=False)
        for label, accelerator, virtual_event in (
            ("Cut", "Ctrl+X", "<<Cut>>"),
            ("Copy", "Ctrl+C", "<<Copy>>"),
            ("Paste", "Ctrl+V", "<<Paste>>"),
        ):
            edit_menu.add_command(
                label=label,
                accelerator=accelerator,
                command=lambda event=virtual_event: self._edit_search_entry(event),
            )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Select All",
            accelerator="Ctrl+A",
            command=self._select_all_search_text,
        )
        menu_bar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(menu_bar, tearoff=False)
        view_menu.add_command(
            label="Clear Results",
            accelerator="Ctrl+L",
            command=self._actions.clear_results,
        )
        view_menu.add_command(
            label="Scroll to Top",
            accelerator="Home",
            command=self._actions.scroll_top,
        )
        view_menu.add_command(
            label="Scroll to Bottom",
            accelerator="End",
            command=self._actions.scroll_bottom,
        )
        menu_bar.add_cascade(label="View", menu=view_menu)

        navigate_menu = tk.Menu(menu_bar, tearoff=False)
        navigate_menu.add_command(
            label="Focus Search",
            accelerator="Ctrl+F",
            command=self._actions.focus_search,
        )
        navigate_menu.add_command(
            label="Search Catalog",
            accelerator="Enter",
            command=self._actions.search,
        )
        navigate_menu.add_command(
            label="Previous Page",
            accelerator="Page Up",
            command=self._actions.previous_page,
        )
        navigate_menu.add_command(
            label="Next Page",
            accelerator="Page Down",
            command=self._actions.next_page,
        )
        menu_bar.add_cascade(label="Navigate", menu=navigate_menu)

        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label="About Media Finder", command=self._show_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self._root.bind_all("<Control-n>", self._on_new_search_shortcut)
        self._root.bind_all("<Control-f>", self._on_focus_search_shortcut)
        self._root.bind_all("<Control-l>", self._on_clear_results_shortcut)
        self._root.bind_all("<Control-a>", self._on_select_all_shortcut)
        return menu_bar

    def _edit_search_entry(self, virtual_event: str) -> None:
        """Apply a standard clipboard operation to the search field."""
        self._search_entry.focus_set()
        self._search_entry.event_generate(virtual_event)

    def _select_all_search_text(self) -> None:
        """Select all text in the search field and focus it."""
        self._search_entry.focus_set()
        self._search_entry.selection_range(0, tk.END)
        self._search_entry.icursor(tk.END)

    def _show_about(self) -> None:
        """Display application information in a native dialog."""
        messagebox.showinfo(
            "About Media Finder",
            "Media Finder\n"
            f"Version {__version__}\n"
            "Discover movies, television shows, and episodes across supported catalogs.\n\n"
            "Catalog data is provided by the selected source.",
            parent=self._root,
        )

    def _on_new_search_shortcut(self, _event: tk.Event) -> str:
        """Handle Ctrl+N to reset the search form."""
        self._actions.new_search()
        return "break"

    def _on_focus_search_shortcut(self, _event: tk.Event) -> str:
        """Handle Ctrl+F to focus the search field."""
        self._actions.focus_search()
        return "break"

    def _on_clear_results_shortcut(self, _event: tk.Event) -> str:
        """Handle Ctrl+L to clear displayed results."""
        self._actions.clear_results()
        return "break"

    def _on_select_all_shortcut(self, _event: tk.Event) -> str:
        """Handle Ctrl+A by selecting the search text."""
        self._select_all_search_text()
        return "break"
