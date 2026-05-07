from __future__ import annotations

from .aircraft import AircraftMission, AircraftTrajectory
from .collision_detector import (
    ConflictBuckets,
    add_trajectory_to_buckets,
    build_conflict_buckets,
    conflicts_with_buckets,
)
from .config import altitude_layers
from .map_generator import CityMap
from .mobility_model import build_trajectory
from .path_planner import plan_path
from .utils import Point2D
from dataclasses import dataclass

from .vertiport_scheduler import (
    PadOccupancyManager,
    descent_to_control_zone_duration,
    landing_occupancy_duration,
    make_pad_manager,
    takeoff_occupancy_duration,
)


@dataclass
class ScheduleState:
    accepted: list[AircraftTrajectory]
    accepted_buckets: ConflictBuckets
    pad_manager: PadOccupancyManager


def model_flags(model: str) -> tuple[bool, bool, bool]:
    if model == "A":
        return False, False, False
    if model == "B":
        return True, False, False
    if model == "C":
        return False, True, False
    if model == "D":
        return True, True, False
    if model == "E":
        return True, True, True
    raise ValueError(f"Unknown model: {model}")


def create_schedule_state(config: dict) -> ScheduleState:
    sim_cfg = config["simulation"]
    conflict_time_step = float(sim_cfg.get("conflict_time_step", sim_cfg["time_step"]))
    return ScheduleState(
        accepted=[],
        accepted_buckets=build_conflict_buckets([], conflict_time_step),
        pad_manager=make_pad_manager(config),
    )


def schedule_missions(
    city_map: CityMap,
    missions: list[AircraftMission],
    config: dict,
    model: str,
    speed_mps: float,
    safety_distance_m: float,
) -> list[AircraftTrajectory]:
    building_avoidance, aircraft_avoidance, _ = model_flags(model)
    sim_cfg = config["simulation"]
    aircraft_cfg = config["aircraft"]
    base_altitude = float(aircraft_cfg["base_cruise_altitude"])
    time_step = float(sim_cfg["time_step"])
    conflict_time_step = float(sim_cfg.get("conflict_time_step", time_step))
    vertical_speed = float(aircraft_cfg["vertical_speed"])
    vertical_separation = float(aircraft_cfg["vertical_separation_m"])
    state = create_schedule_state(config)
    sorted_missions = sorted(missions, key=lambda m: (m.planned_start_time, m.id))

    for mission in sorted_missions:
        schedule_single_mission(
            city_map=city_map,
            mission=mission,
            config=config,
            model=model,
            speed_mps=speed_mps,
            safety_distance_m=safety_distance_m,
            state=state,
        )

    return sorted(state.accepted, key=lambda t: t.mission.id)


def schedule_single_mission(
    city_map: CityMap,
    mission: AircraftMission,
    config: dict,
    model: str,
    speed_mps: float,
    safety_distance_m: float,
    state: ScheduleState,
) -> AircraftTrajectory:
    building_avoidance, aircraft_avoidance, pad_occupancy = model_flags(model)
    sim_cfg = config["simulation"]
    aircraft_cfg = config["aircraft"]
    base_altitude = float(aircraft_cfg["base_cruise_altitude"])
    time_step = float(sim_cfg["time_step"])
    conflict_time_step = float(sim_cfg.get("conflict_time_step", time_step))
    vertical_speed = float(aircraft_cfg["vertical_speed"])
    vertical_separation = float(aircraft_cfg["vertical_separation_m"])
    takeoff_pad_duration = takeoff_occupancy_duration(config) if pad_occupancy else 0.0
    landing_pad_duration = landing_occupancy_duration(config) if pad_occupancy else 0.0

    if aircraft_avoidance:
        delay_options = list(range(0, int(sim_cfg["max_departure_delay"]) + 1, int(sim_cfg["delay_step"])))
    else:
        delay_options = [0]

    if aircraft_avoidance or building_avoidance:
        altitude_options = altitude_layers(config)
    else:
        altitude_options = [base_altitude]

    best: tuple[int, int, float, float, AircraftTrajectory] | None = None
    for delay in delay_options:
        for altitude in altitude_options:
            requested_start = mission.planned_start_time + delay
            takeoff_pad_start = state.pad_manager.earliest_start(
                mission.origin_id,
                requested_start,
                takeoff_pad_duration,
            )
            takeoff_pad_end = takeoff_pad_start + takeoff_pad_duration
            takeoff_pad_delay = max(0.0, takeoff_pad_start - requested_start)

            preliminary = _build_candidate(
                city_map,
                mission,
                config,
                model,
                building_avoidance,
                altitude,
                takeoff_pad_start,
                speed_mps,
                vertical_speed,
                time_step,
                base_altitude,
                landing_hold_s=0.0,
                takeoff_pad_delay_s=takeoff_pad_delay,
                landing_pad_delay_s=0.0,
                takeoff_pad_start_s=takeoff_pad_start,
                takeoff_pad_end_s=takeoff_pad_end,
            )
            landing_entry_time = preliminary.cruise_arrival_time + descent_to_control_zone_duration(
                config,
                altitude,
                mission.destination.z,
            )
            landing_pad_start = state.pad_manager.earliest_start(
                mission.destination_id,
                landing_entry_time,
                landing_pad_duration,
            )
            landing_pad_end = landing_pad_start + landing_pad_duration
            landing_pad_delay = max(0.0, landing_pad_start - landing_entry_time)

            candidate = _build_candidate(
                city_map,
                mission,
                config,
                model,
                building_avoidance,
                altitude,
                takeoff_pad_start,
                speed_mps,
                vertical_speed,
                time_step,
                base_altitude,
                landing_hold_s=landing_pad_delay,
                takeoff_pad_delay_s=takeoff_pad_delay,
                landing_pad_delay_s=landing_pad_delay,
                takeoff_pad_start_s=takeoff_pad_start,
                takeoff_pad_end_s=takeoff_pad_end,
                landing_pad_start_s=landing_pad_start,
                landing_pad_end_s=landing_pad_end,
            )
            report = conflicts_with_buckets(
                candidate,
                state.accepted_buckets,
                safety_distance_m,
                vertical_separation,
                conflict_time_step,
            )
            conflict_score = report.pair_count if aircraft_avoidance else 0
            building_score = candidate.building_collisions if building_avoidance else 0
            score = (
                conflict_score,
                building_score,
                candidate.delay_s,
                abs(altitude - base_altitude),
                candidate,
            )
            if best is None or score[:4] < best[:4]:
                best = score
            if conflict_score == 0 and building_score == 0:
                break
        if best is not None and best[0] == 0 and best[1] == 0:
            break

    chosen = best[4]
    state.pad_manager.reserve(chosen.mission.origin_id, chosen.takeoff_pad_start_s, chosen.takeoff_pad_end_s)
    state.pad_manager.reserve(chosen.mission.destination_id, chosen.landing_pad_start_s, chosen.landing_pad_end_s)
    add_trajectory_to_buckets(state.accepted_buckets, chosen, conflict_time_step)
    state.accepted.append(chosen)
    return chosen


def _build_candidate(
    city_map: CityMap,
    mission: AircraftMission,
    config: dict,
    model: str,
    building_avoidance: bool,
    altitude: float,
    start_time: float,
    speed_mps: float,
    vertical_speed: float,
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
    planned_path = plan_path(
        city_map=city_map,
        origin=Point2D(mission.origin.x, mission.origin.y),
        destination=Point2D(mission.destination.x, mission.destination.y),
        cruise_altitude=altitude,
        config=config,
        building_avoidance=building_avoidance,
    )
    return build_trajectory(
        mission=mission,
        planned_path=planned_path,
        model=model,
        cruise_altitude=altitude,
        start_time=start_time,
        speed_mps=speed_mps,
        vertical_speed_mps=vertical_speed,
        time_step=time_step,
        base_altitude=base_altitude,
        landing_hold_s=landing_hold_s,
        takeoff_pad_delay_s=takeoff_pad_delay_s,
        landing_pad_delay_s=landing_pad_delay_s,
        takeoff_pad_start_s=takeoff_pad_start_s,
        takeoff_pad_end_s=takeoff_pad_end_s,
        landing_pad_start_s=landing_pad_start_s,
        landing_pad_end_s=landing_pad_end_s,
    )
