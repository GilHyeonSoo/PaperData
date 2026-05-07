from __future__ import annotations

from .building import Building
from .utils import Point2D, clamp, distance_2d, point_in_rect


def candidate_detour_points(
    building: Building,
    margin: float,
    map_width: float,
    map_height: float,
) -> list[Point2D]:
    min_x, min_y, max_x, max_y = building.expanded_rect(margin)
    candidates = [
        Point2D(min_x, min_y),
        Point2D(min_x, max_y),
        Point2D(max_x, min_y),
        Point2D(max_x, max_y),
        Point2D((min_x + max_x) / 2.0, min_y),
        Point2D((min_x + max_x) / 2.0, max_y),
        Point2D(min_x, (min_y + max_y) / 2.0),
        Point2D(max_x, (min_y + max_y) / 2.0),
    ]
    return [
        Point2D(clamp(p.x, 0.0, map_width), clamp(p.y, 0.0, map_height))
        for p in candidates
    ]


def point_inside_any_building(point: Point2D, buildings: list[Building], margin: float) -> bool:
    return any(point_in_rect(point, building.expanded_rect(margin)) for building in buildings)


def choose_detour_point(
    current: Point2D,
    destination: Point2D,
    building: Building,
    buildings: list[Building],
    margin: float,
    map_width: float,
    map_height: float,
) -> Point2D | None:
    candidates = candidate_detour_points(building, margin, map_width, map_height)
    valid = [
        point
        for point in candidates
        if not point_inside_any_building(point, buildings, margin / 2.0)
    ]
    if not valid:
        return None
    return min(valid, key=lambda p: distance_2d(current, p) + distance_2d(p, destination))

