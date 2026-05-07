from __future__ import annotations

from dataclasses import dataclass, field

from .utils import Point3D


@dataclass(frozen=True)
class AircraftMission:
    id: int
    origin_id: int
    destination_id: int
    origin: Point3D
    destination: Point3D
    planned_start_time: float
    vehicle_id: int | None = None


@dataclass
class TrajectorySample:
    aircraft_id: int
    time_s: float
    x: float
    y: float
    z: float
    phase: str


@dataclass
class AircraftTrajectory:
    mission: AircraftMission
    model: str
    cruise_altitude: float
    start_time: float
    cruise_arrival_time: float
    descent_start_time: float
    end_time: float
    distance_m: float
    detour_distance_m: float
    delay_s: float
    takeoff_pad_delay_s: float
    landing_pad_delay_s: float
    pad_delay_s: float
    takeoff_pad_start_s: float
    takeoff_pad_end_s: float
    landing_pad_start_s: float
    landing_pad_end_s: float
    building_risks: int
    building_collisions: int
    path_changes: int
    altitude_changes: int
    samples: list[TrajectorySample] = field(default_factory=list)
