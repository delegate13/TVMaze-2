"""Scrollable show-result cards, separate from search orchestration."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from collections.abc import Callable
from tkinter import ttk

from models.media_item import MediaItem
from models.show import Show
from utils.json_explainer import clean_summary

BACKGROUND = "#F3F5F9"
SURFACE = "#FFFFFF"
INK = "#17233B"
MUTED = "#69758B"
ACCENT = "#5865E8"
SUCCESS = "#16866A"


class ShowResultsView(ttk.Frame):
    """Render and navigate a scrollable list of normalized show cards."""

    def __init__(
        self,
        parent: tk.Misc,
        on_resize: Callable[[tk.Event], None] | None = None,
    ) -> None:
        """Create the canvas and scroll bar for result cards."""
        super().__init__(parent)
        self._on_resize = on_resize
        self._summary_labels: list[ttk.Label] = []
        self._canvas = tk.Canvas(
            self,
            background=BACKGROUND,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            self, orient=tk.VERTICAL, command=self._canvas.yview
        )
        self._content = ttk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._content, anchor=tk.NW
        )
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._content.bind("<Configure>", self._on_content_resized)
        self._canvas.bind("<Configure>", self._on_canvas_resized)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.show_empty_state(
            "Start with a search",
            "Type a show title or a couple of keywords above to get started.",
        )

    def render(self, items: list[MediaItem] | list[Show]) -> None:
        """Replace current content with cards for normalized media items."""
        self._clear()
        for item in items:
            if isinstance(item, Show):
                title = item.name
                rating = item.rating
                summary = item.summary
                url = item.url
                details = "TV show"
                source = "TVMaze"
            else:
                title = item.title
                rating = item.rating
                summary = item.overview
                url = item.url
                details = item.media_type.replace("_", " ").title()
                if item.year is not None:
                    details = f"{details} · {item.year}"
                source = item.source
            card = ttk.Frame(self._content, style="Card.TFrame", padding=(18, 15))
            card.pack(fill=tk.X, pady=(0, 10))
            top_row = ttk.Frame(card, style="Card.TFrame")
            top_row.pack(fill=tk.X)
            ttk.Label(top_row, text=title, style="CardTitle.TLabel").pack(
                side=tk.LEFT, anchor=tk.W
            )
            rating_text = (
                f"★  {rating:g} / 10"
                if rating is not None
                else "Not rated"
            )
            rating_color = SUCCESS if rating is not None else MUTED
            ttk.Label(
                top_row,
                text=rating_text,
                style="CardMeta.TLabel",
                foreground=rating_color,
            ).pack(side=tk.RIGHT, anchor=tk.E)

            ttk.Label(
                card,
                text=f"{details}  ·  {source}",
                style="CardMeta.TLabel",
            ).pack(
                anchor=tk.W, pady=(5, 0)
            )
            clean_text = clean_summary(summary) if summary else ""
            if clean_text:
                summary_text = (
                    clean_text if len(clean_text) <= 400 else clean_text[:397] + "..."
                )
                summary_label = ttk.Label(
                    card,
                    text=summary_text,
                    style="CardMeta.TLabel",
                    wraplength=max(300, self._canvas.winfo_width() - 70),
                    justify=tk.LEFT,
                )
                summary_label.pack(anchor=tk.W, fill=tk.X, pady=(10, 0))
                self._summary_labels.append(summary_label)
            if url and url.startswith(("https://", "http://")):
                ttk.Button(
                    card,
                    text=f"View on {source}  ↗",
                    style="Link.TButton",
                    command=lambda item_url=url: webbrowser.open(item_url),
                ).pack(anchor=tk.W, pady=(7, 0))

    def show_empty_state(self, title: str, message: str) -> None:
        """Replace cards with a clear title and explanatory placeholder."""
        self._clear()
        panel = ttk.Frame(self._content, style="Card.TFrame", padding=(24, 28))
        panel.pack(fill=tk.X)
        ttk.Label(panel, text=title, style="CardTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(panel, text=message, style="CardMeta.TLabel").pack(
            anchor=tk.W, pady=(7, 0)
        )

    def scroll_top(self) -> None:
        """Scroll to the first result card."""
        self._canvas.yview_moveto(0)

    def scroll_bottom(self) -> None:
        """Scroll to the final result card."""
        self._canvas.yview_moveto(1)

    def previous_page(self) -> None:
        """Scroll the results one page upward."""
        self._canvas.yview_scroll(-1, "pages")

    def next_page(self) -> None:
        """Scroll the results one page downward."""
        self._canvas.yview_scroll(1, "pages")

    def _clear(self) -> None:
        """Destroy existing result widgets before rendering new content."""
        for child in self._content.winfo_children():
            child.destroy()
        self._summary_labels.clear()

    def _on_content_resized(self, _event: tk.Event) -> None:
        """Update the scroll region as result cards change height."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resized(self, event: tk.Event) -> None:
        """Expand cards and summary text to the available window width."""
        self._canvas.itemconfigure(self._canvas_window, width=event.width)
        wraplength = max(300, event.width - 70)
        for label in self._summary_labels:
            label.configure(wraplength=wraplength)
        if self._on_resize is not None:
            self._on_resize(event)
