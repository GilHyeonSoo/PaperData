from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class Point3D:
    x: float
    y: float
    z: float


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def distance_2d(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def distance_3d(a: Point3D, b: Point3D) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def point_in_rect(p: Point2D, rect: tuple[float, float, float, float]) -> bool:
    min_x, min_y, max_x, max_y = rect
    return min_x <= p.x <= max_x and min_y <= p.y <= max_y


def orientation(a: Point2D, b: Point2D, c: Point2D) -> float:
    return (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y)


def on_segment(a: Point2D, b: Point2D, c: Point2D) -> bool:
    return (
        min(a.x, c.x) <= b.x <= max(a.x, c.x)
        and min(a.y, c.y) <= b.y <= max(a.y, c.y)
    )


def segments_intersect(a: Point2D, b: Point2D, c: Point2D, d: Point2D) -> bool:
    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)

    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    if abs(o1) < 1e-9 and on_segment(a, c, b):
        return True
    if abs(o2) < 1e-9 and on_segment(a, d, b):
        return True
    if abs(o3) < 1e-9 and on_segment(c, a, d):
        return True
    if abs(o4) < 1e-9 and on_segment(c, b, d):
        return True
    return False


def segment_intersects_rect(a: Point2D, b: Point2D, rect: tuple[float, float, float, float]) -> bool:
    if point_in_rect(a, rect) or point_in_rect(b, rect):
        return True
    min_x, min_y, max_x, max_y = rect
    corners = [
        Point2D(min_x, min_y),
        Point2D(max_x, min_y),
        Point2D(max_x, max_y),
        Point2D(min_x, max_y),
    ]
    edges = list(zip(corners, corners[1:] + corners[:1]))
    return any(segments_intersect(a, b, c, d) for c, d in edges)


def interpolate_3d(a: Point3D, b: Point3D, ratio: float) -> Point3D:
    return Point3D(
        a.x + (b.x - a.x) * ratio,
        a.y + (b.y - a.y) * ratio,
        a.z + (b.z - a.z) * ratio,
    )

