"""Validated television show data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from utils.exceptions import ValidationError
from utils.validators import validate_show_payload


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
        validate_show_payload(payload)
        rating_value = payload["rating"]["average"]
        return cls(
            id=payload["id"],
            name=payload["name"].strip(),
            rating=float(rating_value) if rating_value is not None else None,
            genres=tuple(payload["genres"]),
            summary=payload["summary"],
            url=payload["url"],
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
            or not 0 <= self.rating <= 10
        ):
            raise ValidationError("Show rating must be between 0 and 10.")
        if not isinstance(self.genres, tuple) or not all(
            isinstance(genre, str) for genre in self.genres
        ):
            raise ValidationError("Show genres must be a tuple of strings.")
