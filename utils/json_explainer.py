"""Presentation helpers for normalized show data."""

from __future__ import annotations

import re
from html import unescape

from models.media_item import MediaItem
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


def explain_media_items(items: list[MediaItem]) -> str:
    """Format normalized cross-provider media results for the CLI."""
    formatted: list[str] = []
    for item in items:
        rating = f"{item.rating:g}/10" if item.rating is not None else "Not rated"
        category = item.media_type.replace("_", " ").title()
        details = [f"{item.source} {category}", f"Rating: {rating}"]
        if item.year is not None:
            details.append(f"Year: {item.year}")
        if item.overview:
            details.append(f"Summary: {clean_summary(item.overview)}")
        if item.url:
            details.append(f"URL: {item.url}")
        formatted.append(
            "\n".join([f"{item.title} (ID: {item.id})", *details])
        )
    return "\n\n".join(formatted)


def clean_summary(summary: str) -> str:
    """Remove HTML markup and decode entities in a provider summary."""
    return unescape(HTML_TAG_PATTERN.sub("", summary)).strip()
