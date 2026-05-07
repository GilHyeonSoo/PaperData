from __future__ import annotations

from dataclasses import dataclass

from .avoidance import choose_detour_point
from .building import Building
from .map_generator import CityMap
from .utils import Point2D, distance_2d, point_in_rect, segment_intersects_rect


@dataclass
class PlannedPath:
    waypoints: list[Point2D]
    building_risks: int
    building_collisions: int
    path_changes: int
    horizontal_distance_m: float
    straight_distance_m: float

    @property
    def detour_distance_m(self) -> float:
        return max(0.0, self.horizontal_distance_m - self.straight_distance_m)


def plan_path(
    city_map: CityMap,
    origin: Point2D,
    destination: Point2D,
    cruise_altitude: float,
    config: dict,
    building_avoidance: bool,
) -> PlannedPath:
    altitude_cfg = config["altitude"]
    avoid_cfg = config["avoidance"]
    horizontal_margin = float(altitude_cfg["building_horizontal_margin"])
    vertical_margin = float(altitude_cfg["building_vertical_margin"])
    detour_margin = float(avoid_cfg["detour_margin"])

    direct_risks = count_building_collisions(
        [origin, destination],
        city_map.buildings,
        cruise_altitude,
        horizontal_margin,
        vertical_margin,
    )

    if not building_avoidance:
        distance = path_distance([origin, destination])
        return PlannedPath(
            waypoints=[origin, destination],
            building_risks=direct_risks,
            building_collisions=direct_risks,
            path_changes=0,
            horizontal_distance_m=distance,
            straight_distance_m=distance,
        )

    waypoints = [origin]
    current = origin
    visited: set[tuple[int, int]] = set()
    max_detours = int(avoid_cfg["max_detours"])

    for _ in range(max_detours):
        blockers = blocking_buildings(
            current,
            destination,
            city_map.buildings,
            cruise_altitude,
            horizontal_margin,
            vertical_margin,
        )
        if not blockers:
            break
        blocker = min(blockers, key=lambda b: distance_2d(current, b.center))
        detour = choose_detour_point(
            current,
            destination,
            blocker,
            city_map.buildings,
            detour_margin,
            city_map.width,
            city_map.height,
        )
        if detour is None:
            break
        key = (round(detour.x), round(detour.y))
        if key in visited:
            break
        visited.add(key)
        waypoints.append(detour)
        current = detour

    waypoints.append(destination)
    remaining = count_building_collisions(
        waypoints,
        city_map.buildings,
        cruise_altitude,
        horizontal_margin,
        vertical_margin,
    )
    return PlannedPath(
        waypoints=waypoints,
        building_risks=direct_risks,
        building_collisions=remaining,
        path_changes=max(0, len(waypoints) - 2),
        horizontal_distance_m=path_distance(waypoints),
        straight_distance_m=distance_2d(origin, destination),
    )


def blocking_buildings(
    start: Point2D,
    end: Point2D,
    buildings: list[Building],
    cruise_altitude: float,
    horizontal_margin: float,
    vertical_margin: float,
) -> list[Building]:
    blockers: list[Building] = []
    for building in buildings:
        if point_in_rect(start, building.rect) or point_in_rect(end, building.rect):
            continue
        if building.height + vertical_margin < cruise_altitude:
            continue
        if segment_intersects_rect(start, end, building.expanded_rect(horizontal_margin)):
            blockers.append(building)
    return blockers


def count_building_collisions(
    waypoints: list[Point2D],
    buildings: list[Building],
    cruise_altitude: float,
    horizontal_margin: float,
    vertical_margin: float,
) -> int:
    hits: set[int] = set()
    for start, end in zip(waypoints, waypoints[1:]):
        for building in blocking_buildings(
            start, end, buildings, cruise_altitude, horizontal_margin, vertical_margin
        ):
            hits.add(building.id)
    return len(hits)


def path_distance(points: list[Point2D]) -> float:
    return sum(distance_2d(a, b) for a, b in zip(points, points[1:]))
