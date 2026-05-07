from __future__ import annotations

from dataclasses import dataclass

from .utils import Point2D


@dataclass(frozen=True)
class Building:
    id: int
    x: float
    y: float
    width: float
    depth: float
    height: float

    @property
    def center(self) -> Point2D:
        return Point2D(self.x + self.width / 2.0, self.y + self.depth / 2.0)

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.width, self.y + self.depth)

    def expanded_rect(self, margin: float) -> tuple[float, float, float, float]:
        return (
            self.x - margin,
            self.y - margin,
            self.x + self.width + margin,
            self.y + self.depth + margin,
        )

