"""Show filtering business rules."""

from __future__ import annotations

from collections.abc import Iterable

from models.show import Show


class ShowFilterService:
    """Apply rating-related filters to show collections."""

    def filter_by_minimum_rating(
        self, shows: Iterable[Show], minimum_rating: float
    ) -> list[Show]:
        """Keep rated shows whose rating meets the inclusive threshold."""
        return [
            show
            for show in shows
            if show.rating is not None and show.rating >= minimum_rating
        ]
