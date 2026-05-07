from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .aircraft import AircraftMission
from .collision_detector import detect_aircraft_conflicts
from .config import kmh_to_mps
from .map_generator import generate_city_map
from .scheduler import create_schedule_state, schedule_single_mission
from .simulation import Experiment, SimulationResult, build_raw_rows, summarize


@dataclass
class ContinuousScenarioResult:
    name: str
    result: SimulationResult
    vehicle_mission_counts: dict[int, int]


def merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    _deep_update(merged, override)
    return merged


def run_continuous_scenario(
    scenario_name: str,
    base_config: dict[str, Any],
    scenario_config: dict[str, Any],
) -> ContinuousScenarioResult:
    config = merge_config(base_config, scenario_config)
    model = str(scenario_config.get("model", "D"))
    sim_cfg = config["simulation"]
    map_cfg = config["map"]
    aircraft_cfg = config["aircraft"]
    vertiport_cfg = config["vertiports"]

    rng = random.Random(int(sim_cfg["random_seed"]))
    city_map = generate_city_map(
        config,
        rng,
        building_density=float(map_cfg["building_density"]),
        vertiport_count=int(vertiport_cfg["count"]),
    )
    if len(city_map.vertiports) < 2:
        raise ValueError(f"{scenario_name}: at least two vertiports are required.")

    fleet_size = int(aircraft_cfg.get("fleet_size", aircraft_cfg.get("count", 50)))
    duration = int(sim_cfg["duration"])
    mission_interval = int(sim_cfg.get("mission_interval", 30))
    speed_kmh = float(aircraft_cfg.get("cruise_speed_kmh", 240))
    speed_mps = kmh_to_mps(speed_kmh)
    safety_distance_m = float(aircraft_cfg.get("primary_safety_distance_m", 152.4))
    safety_label = "500ft" if abs(safety_distance_m - 152.4) < 1e-6 else f"{safety_distance_m:g}m"

    state = create_schedule_state(config)
    vehicle_available_at = [0.0 for _ in range(fleet_size)]
    vehicle_mission_counts = {vehicle_id: 0 for vehicle_id in range(fleet_size)}
    generated_missions = 0

    for request_time in range(0, duration, mission_interval):
        vehicle_id = _select_vehicle(vehicle_available_at, request_time, rng)
        planned_start_time = max(float(request_time), vehicle_available_at[vehicle_id])
        origin, destination = rng.sample(city_map.vertiports, 2)
        mission = AircraftMission(
            id=generated_missions,
            origin_id=origin.id,
            destination_id=destination.id,
            origin=origin.point,
            destination=destination.point,
            planned_start_time=planned_start_time,
            vehicle_id=vehicle_id,
        )
        trajectory = schedule_single_mission(
            city_map=city_map,
            mission=mission,
            config=config,
            model=model,
            speed_mps=speed_mps,
            safety_distance_m=safety_distance_m,
            state=state,
        )
        vehicle_available_at[vehicle_id] = trajectory.end_time
        vehicle_mission_counts[vehicle_id] += 1
        generated_missions += 1

    experiment = Experiment(
        scenario_id=scenario_name,
        sweep="continuous",
        model=model,
        aircraft_count=fleet_size,
        speed_kmh=speed_kmh,
        building_density=float(map_cfg["building_density"]),
        vertiport_count=int(vertiport_cfg["count"]),
        safety_distance_m=safety_distance_m,
        safety_label=safety_label,
    )
    trajectories = sorted(state.accepted, key=lambda t: t.mission.id)
    report = detect_aircraft_conflicts(
        trajectories,
        safety_distance_m,
        float(aircraft_cfg["vertical_separation_m"]),
        float(sim_cfg.get("conflict_time_step", sim_cfg["time_step"])),
    )
    summary = summarize(config, experiment, city_map, trajectories, report)
    active_vehicle_counts = [count for count in vehicle_mission_counts.values() if count > 0]
    summary.update(
        {
            "scenario_name": scenario_name,
            "description": scenario_config.get("description", ""),
            "map_width": map_cfg["width"],
            "map_height": map_cfg["height"],
            "grid_size": map_cfg["grid_size"],
            "road_width": map_cfg["road_width"],
            "fleet_size": fleet_size,
            "duration_s": duration,
            "mission_interval_s": mission_interval,
            "generated_missions": generated_missions,
            "completed_within_duration": sum(1 for t in trajectories if t.end_time <= duration),
            "completed_after_duration": sum(1 for t in trajectories if t.end_time > duration),
            "active_vehicle_count": len(active_vehicle_counts),
            "avg_missions_per_active_vehicle": _avg(active_vehicle_counts),
            "max_missions_per_vehicle": max(active_vehicle_counts, default=0),
        }
    )
    raw_rows = build_raw_rows(experiment, trajectories)
    return ContinuousScenarioResult(
        name=scenario_name,
        result=SimulationResult(experiment, city_map, trajectories, report, summary, raw_rows),
        vehicle_mission_counts=vehicle_mission_counts,
    )


def _select_vehicle(vehicle_available_at: list[float], request_time: float, rng: random.Random) -> int:
    available = [
        vehicle_id
        for vehicle_id, available_time in enumerate(vehicle_available_at)
        if available_time <= request_time
    ]
    if available:
        return rng.choice(available)
    return min(range(len(vehicle_available_at)), key=lambda idx: vehicle_available_at[idx])


def _deep_update(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if key in {"description", "model"}:
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = deepcopy(value)


def _avg(values: list[int] | list[float]) -> float:
    return sum(values) / len(values) if values else 0.0

