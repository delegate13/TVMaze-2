"""Validated television show data model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any

from utils.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class Show:
    """A normalized TVMaze show with only user-facing fields."""

    id: int
    name: str
    rating: float | None
    genres: tuple[str, ...]
    summary: str | None
    url: str | None

    @classmethod
    def from_api_payload(cls, payload: Any) -> Show:
        """Create a show from an API object after validating its structure."""
        if not isinstance(payload, dict):
            raise ValidationError("Show response must be an object.")
        rating_data = payload.get("rating")
        if not isinstance(rating_data, dict) or "average" not in rating_data:
            raise ValidationError("Show rating must contain an average value.")
        rating_value = rating_data["average"]
        if rating_value is not None and (
            isinstance(rating_value, bool) or not isinstance(rating_value, Real)
        ):
            raise ValidationError("Show rating average must be numeric or null.")
        genres = payload.get("genres")
        if not isinstance(genres, list):
            raise ValidationError("Show genres must be a list of strings.")
        try:
            rating = float(rating_value) if rating_value is not None else None
        except (OverflowError, ValueError) as error:
            raise ValidationError("Show rating average must be finite.") from error
        name = payload.get("name")
        return cls(
            id=payload.get("id"),
            name=name.strip() if isinstance(name, str) else name,
            rating=rating,
            genres=tuple(genres),
            summary=payload.get("summary"),
            url=payload.get("url"),
        )

    def __post_init__(self) -> None:
        """Enforce model invariants for direct construction as well."""
        if isinstance(self.id, bool) or not isinstance(self.id, int) or self.id < 0:
            raise ValidationError("Show id must be a non-negative integer.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("Show name cannot be blank.")
        if self.rating is not None and (
            isinstance(self.rating, bool)
            or not isinstance(self.rating, (int, float))
            or not math.isfinite(self.rating)
            or not 0 <= self.rating <= 10
        ):
            raise ValidationError("Show rating must be between 0 and 10.")
        if not isinstance(self.genres, tuple) or not all(
            isinstance(genre, str) for genre in self.genres
        ):
            raise ValidationError("Show genres must be a tuple of strings.")
        if self.summary is not None and not isinstance(self.summary, str):
            raise ValidationError("Show summary must be text or null.")
        if self.url is not None and not isinstance(self.url, str):
            raise ValidationError("Show URL must be text or null.")
