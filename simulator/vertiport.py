from __future__ import annotations

from dataclasses import dataclass

from .utils import Point3D


@dataclass(frozen=True)
class Vertiport:
    id: int
    x: float
    y: float
    z: float
    building_id: int | None = None

    @property
    def point(self) -> Point3D:
        return Point3D(self.x, self.y, self.z)

