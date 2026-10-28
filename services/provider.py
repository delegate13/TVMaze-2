"""Contracts implemented by show search API providers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from models.show import Show


@runtime_checkable
class ShowSearchProvider(Protocol):
    """Describe the provider operation required by the search use case."""

    def search_shows(self, search_term: str) -> list[Show]:
        """Return normalized shows matching a search phrase."""
