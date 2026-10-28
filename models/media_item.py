"""Normalized movie, series, and episode data."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from utils.exceptions import ValidationError

MediaType = Literal["movie", "show", "episode"]


@dataclass(frozen=True, slots=True)
class MediaItem:
    """A provider-independent item displayed by the discovery interface."""

    id: str
    title: str
    media_type: MediaType
    source: str
    rating: float | None = None
    year: int | None = None
    overview: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        """Reject invalid normalized provider data."""
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValidationError("Media item id cannot be blank.")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValidationError("Media item title cannot be blank.")
        if self.media_type not in {"movie", "show", "episode"}:
            raise ValidationError("Media type must be movie, show, or episode.")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValidationError("Media item source cannot be blank.")
        if self.rating is not None and (
            isinstance(self.rating, bool)
            or not isinstance(self.rating, (int, float))
            or not math.isfinite(self.rating)
            or not 0 <= self.rating <= 10
        ):
            raise ValidationError("Media item rating must be between 0 and 10.")
        if self.year is not None and (
            isinstance(self.year, bool) or not isinstance(self.year, int)
        ):
            raise ValidationError("Media item year must be an integer or null.")
        if self.overview is not None and not isinstance(self.overview, str):
            raise ValidationError("Media item overview must be text or null.")
        if self.url is not None and not isinstance(self.url, str):
            raise ValidationError("Media item URL must be text or null.")
