"""Location model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Location:
    """A Hotspot Shield virtual location."""

    code: str
    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", self.code.strip())
        object.__setattr__(self, "name", self.name.strip())
        if not self.code:
            raise ValueError("location code must not be empty")

    @property
    def display(self) -> str:
        if self.name:
            return f"{self.code} — {self.name}"
        return self.code

    def matches_query(self, query: str) -> bool:
        q = query.strip().casefold()
        if not q:
            return True
        haystack = f"{self.code} {self.name}".casefold()
        return q in haystack
