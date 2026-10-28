"""Contracts implemented by media catalog providers."""

from __future__ import annotations

from typing import Protocol

from models.media_item import MediaItem, MediaType


class MediaProvider(Protocol):
    """Describe provider operations used by the media discovery service."""

    name: str

    def search(self, term: str, media_type: MediaType) -> list[MediaItem]:
        """Search the provider catalog for the requested media type."""

    def top_movies(self, limit: int) -> list[MediaItem]:
        """Return the provider's highest-ranked movie results."""
