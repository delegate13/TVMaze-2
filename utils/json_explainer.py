"""Presentation helpers for normalized show data."""

from __future__ import annotations

import re
from html import unescape

from models.show import Show

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def explain_shows(shows: list[Show]) -> str:
    """Format shows as readable terminal output."""
    return "\n\n".join(explain_show(show) for show in shows)


def explain_show(show: Show) -> str:
    """Render a single show without exposing raw API JSON."""
    rating = f"{show.rating:g}/10" if show.rating is not None else "Not rated"
    genres = ", ".join(show.genres) if show.genres else "Unknown"
    lines = [
        f"{show.name} (ID: {show.id})",
        f"Rating: {rating}",
        f"Genres: {genres}",
    ]
    if show.summary:
        summary = clean_summary(show.summary)
        if summary:
            lines.append(f"Summary: {summary}")
    if show.url:
        lines.append(f"URL: {show.url}")
    return "\n".join(lines)


def clean_summary(summary: str) -> str:
    """Remove HTML markup and decode entities in a TVMaze summary."""
    return unescape(HTML_TAG_PATTERN.sub("", summary)).strip()
