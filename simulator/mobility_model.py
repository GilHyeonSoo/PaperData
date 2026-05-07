from __future__ import annotations

import math

from .aircraft import AircraftMission, AircraftTrajectory, TrajectorySample
from .path_planner import PlannedPath
from .utils import Point3D, distance_2d, interpolate_3d


def build_trajectory(
    mission: AircraftMission,
    planned_path: PlannedPath,
    model: str,
    cruise_altitude: float,
    start_time: float,
    speed_mps: float,
    vertical_speed_mps: float,
    time_step: float,
    base_altitude: float,
    landing_hold_s: float = 0.0,
    takeoff_pad_delay_s: float = 0.0,
    landing_pad_delay_s: float = 0.0,
    takeoff_pad_start_s: float | None = None,
    takeoff_pad_end_s: float | None = None,
    landing_pad_start_s: float | None = None,
    landing_pad_end_s: float | None = None,
) -> AircraftTrajectory:
    origin = mission.origin
    destination = mission.destination
    current_time = float(start_time)
    samples: list[TrajectorySample] = []
    total_distance = 0.0

    climb_end = Point3D(origin.x, origin.y, cruise_altitude)
    climb_duration = max(0.0, (cruise_altitude - origin.z) / vertical_speed_mps)
    total_distance += abs(cruise_altitude - origin.z)
    _append_segment(samples, mission.id, current_time, origin, climb_end, climb_duration, "climb", time_step)
    current_time += climb_duration

    cruise_points = [Point3D(p.x, p.y, cruise_altitude) for p in planned_path.waypoints]
    for start, end in zip(cruise_points, cruise_points[1:]):
        segment_distance = distance_2d(start, end)
        duration = segment_distance / speed_mps if speed_mps > 0 else 0.0
        total_distance += segment_distance
        _append_segment(samples, mission.id, current_time, start, end, duration, "cruise", time_step)
        current_time += duration

    cruise_arrival_time = current_time
    if landing_hold_s > 0:
        hold_start = Point3D(destination.x, destination.y, cruise_altitude)
        hold_end = Point3D(destination.x, destination.y, cruise_altitude)
        _append_segment(
            samples,
            mission.id,
            current_time,
            hold_start,
            hold_end,
            landing_hold_s,
            "landing_wait",
            time_step,
        )
        current_time += landing_hold_s

    descent_start_time = current_time
    descend_start = Point3D(destination.x, destination.y, cruise_altitude)
    descend_duration = max(0.0, (cruise_altitude - destination.z) / vertical_speed_mps)
    total_distance += abs(cruise_altitude - destination.z)
    _append_segment(
        samples,
        mission.id,
        current_time,
        descend_start,
        destination,
        descend_duration,
        "descend",
        time_step,
    )
    current_time += descend_duration

    return AircraftTrajectory(
        mission=mission,
        model=model,
        cruise_altitude=cruise_altitude,
        start_time=start_time,
        cruise_arrival_time=cruise_arrival_time,
        descent_start_time=descent_start_time,
        end_time=current_time,
        distance_m=total_distance,
        detour_distance_m=planned_path.detour_distance_m,
        delay_s=max(0.0, start_time - mission.planned_start_time),
        takeoff_pad_delay_s=takeoff_pad_delay_s,
        landing_pad_delay_s=landing_pad_delay_s,
        pad_delay_s=takeoff_pad_delay_s + landing_pad_delay_s,
        takeoff_pad_start_s=start_time if takeoff_pad_start_s is None else takeoff_pad_start_s,
        takeoff_pad_end_s=start_time if takeoff_pad_end_s is None else takeoff_pad_end_s,
        landing_pad_start_s=descent_start_time if landing_pad_start_s is None else landing_pad_start_s,
        landing_pad_end_s=descent_start_time if landing_pad_end_s is None else landing_pad_end_s,
        building_risks=planned_path.building_risks,
        building_collisions=planned_path.building_collisions,
        path_changes=planned_path.path_changes,
        altitude_changes=1 if abs(cruise_altitude - base_altitude) > 1e-6 else 0,
        samples=_dedupe_samples(samples),
    )


def _append_segment(
    samples: list[TrajectorySample],
    aircraft_id: int,
    start_time: float,
    start: Point3D,
    end: Point3D,
    duration: float,
    phase: str,
    time_step: float,
) -> None:
    if duration <= 0:
        samples.append(TrajectorySample(aircraft_id, start_time, end.x, end.y, end.z, phase))
        return
    steps = max(1, int(math.ceil(duration / time_step)))
    for idx in range(steps + 1):
        ratio = min(1.0, idx / steps)
        point = interpolate_3d(start, end, ratio)
        samples.append(
            TrajectorySample(
                aircraft_id=aircraft_id,
                time_s=start_time + duration * ratio,
                x=point.x,
                y=point.y,
                z=point.z,
                phase=phase,
            )
        )


def _dedupe_samples(samples: list[TrajectorySample]) -> list[TrajectorySample]:
    deduped: list[TrajectorySample] = []
    seen: set[tuple[float, str]] = set()
    for sample in samples:
        key = (round(sample.time_s, 3), sample.phase)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sample)
    return deduped
