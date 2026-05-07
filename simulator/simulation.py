from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any

from .aircraft import AircraftMission, AircraftTrajectory
from .collision_detector import AircraftConflictReport, detect_aircraft_conflicts
from .config import kmh_to_mps
from .map_generator import CityMap, generate_city_map
from .scheduler import model_flags, schedule_missions
from .weather import describe_weather


@dataclass(frozen=True)
class Experiment:
    scenario_id: str
    sweep: str
    model: str
    aircraft_count: int
    speed_kmh: float
    building_density: float
    vertiport_count: int
    safety_distance_m: float
    safety_label: str

    def seed_key(self) -> str:
        return (
            f"{self.sweep}|{self.aircraft_count}|{self.speed_kmh}|"
            f"{self.building_density}|{self.vertiport_count}"
        )


@dataclass
class SimulationResult:
    experiment: Experiment
    city_map: CityMap
    trajectories: list[AircraftTrajectory]
    conflict_report: AircraftConflictReport
    summary: dict[str, Any]
    raw_rows: list[dict[str, Any]]


def build_experiments(config: dict) -> list[Experiment]:
    exp_cfg = config["experiments"]
    models = exp_cfg["models"]
    default_count = int(exp_cfg["default_aircraft_count"])
    default_speed = float(exp_cfg["default_speed_kmh"])
    default_density = float(exp_cfg["default_building_density"])
    default_vertiports = int(exp_cfg["default_vertiport_count"])
    primary_safety = float(exp_cfg["primary_safety_distances_m"][0])

    experiments: list[Experiment] = []
    idx = 1
    for model in models:
        rows: list[tuple[str, int, float, float, int, float, str]] = [
            ("model_comparison", default_count, default_speed, default_density, default_vertiports, primary_safety, "500ft"),
            *[
                ("aircraft_count", int(count), default_speed, default_density, default_vertiports, primary_safety, "500ft")
                for count in exp_cfg["aircraft_counts"]
            ],
            *[
                ("speed", default_count, float(speed), default_density, default_vertiports, primary_safety, "500ft")
                for speed in exp_cfg["speeds_kmh"]
            ],
            *[
                ("building_density", default_count, default_speed, float(density), default_vertiports, primary_safety, "500ft")
                for density in exp_cfg["building_densities"]
            ],
            *[
                ("vertiport_count", default_count, default_speed, default_density, int(vertiports), primary_safety, "500ft")
                for vertiports in exp_cfg["vertiport_counts"]
            ],
            *[
                (
                    "safety_distance",
                    default_count,
                    default_speed,
                    default_density,
                    default_vertiports,
                    float(safety),
                    "500ft" if abs(float(safety) - 152.4) < 1e-6 else "30m",
                )
                for safety in exp_cfg["sensitivity_safety_distances_m"]
            ],
        ]
        for sweep, count, speed, density, vertiports, safety, label in rows:
            experiments.append(
                Experiment(
                    scenario_id=f"S{idx:03d}",
                    sweep=sweep,
                    model=model,
                    aircraft_count=count,
                    speed_kmh=speed,
                    building_density=density,
                    vertiport_count=vertiports,
                    safety_distance_m=safety,
                    safety_label=label,
                )
            )
            idx += 1
    return experiments


def run_experiment(config: dict, experiment: Experiment) -> SimulationResult:
    seed = _stable_seed(config["simulation"]["random_seed"], experiment.seed_key())
    rng = random.Random(seed)
    city_map = generate_city_map(
        config,
        rng,
        building_density=experiment.building_density,
        vertiport_count=experiment.vertiport_count,
    )
    missions = generate_missions(city_map, experiment.aircraft_count, config, rng)
    speed_mps = kmh_to_mps(experiment.speed_kmh)
    trajectories = schedule_missions(
        city_map=city_map,
        missions=missions,
        config=config,
        model=experiment.model,
        speed_mps=speed_mps,
        safety_distance_m=experiment.safety_distance_m,
    )
    report = detect_aircraft_conflicts(
        trajectories,
        experiment.safety_distance_m,
        float(config["aircraft"]["vertical_separation_m"]),
        float(config["simulation"].get("conflict_time_step", config["simulation"]["time_step"])),
    )
    summary = summarize(config, experiment, city_map, trajectories, report)
    raw_rows = build_raw_rows(experiment, trajectories)
    return SimulationResult(experiment, city_map, trajectories, report, summary, raw_rows)


def generate_missions(
    city_map: CityMap,
    aircraft_count: int,
    config: dict,
    rng: random.Random,
) -> list[AircraftMission]:
    if len(city_map.vertiports) < 2:
        raise ValueError("At least two vertiports are required to generate missions.")
    window = int(config["simulation"]["departure_window"])
    missions: list[AircraftMission] = []
    for aircraft_id in range(aircraft_count):
        origin, destination = rng.sample(city_map.vertiports, 2)
        missions.append(
            AircraftMission(
                id=aircraft_id,
                origin_id=origin.id,
                destination_id=destination.id,
                origin=origin.point,
                destination=destination.point,
                planned_start_time=float(rng.randint(0, window)),
                vehicle_id=aircraft_id,
            )
        )
    return missions


def summarize(
    config: dict,
    experiment: Experiment,
    city_map: CityMap,
    trajectories: list[AircraftTrajectory],
    report: AircraftConflictReport,
) -> dict[str, Any]:
    total = len(trajectories)
    building_failed = {t.mission.id for t in trajectories if t.building_collisions > 0}
    failed_aircraft = building_failed | report.involved_aircraft
    speed_mps = kmh_to_mps(experiment.speed_kmh)
    flight_times = [t.end_time - t.start_time for t in trajectories]
    weather = describe_weather(config)
    _, _, pad_occupancy_enabled = model_flags(experiment.model)

    return {
        "scenario_id": experiment.scenario_id,
        "sweep": experiment.sweep,
        "model": experiment.model,
        "aircraft_count": experiment.aircraft_count,
        "speed_kmh": experiment.speed_kmh,
        "speed_mps": speed_mps,
        "building_density": experiment.building_density,
        "building_count": len(city_map.buildings),
        "vertiport_count": experiment.vertiport_count,
        "actual_vertiport_count": len(city_map.vertiports),
        "safety_distance_m": experiment.safety_distance_m,
        "safety_label": experiment.safety_label,
        "pad_occupancy_enabled": pad_occupancy_enabled,
        "weather": weather,
        "total_flights": total,
        "success_flights": total - len(failed_aircraft),
        "failed_flights": len(failed_aircraft),
        "building_risk_count": sum(t.building_risks for t in trajectories),
        "building_collision_count": sum(t.building_collisions for t in trajectories),
        "aircraft_collision_count": report.pair_count,
        "aircraft_conflict_sample_count": report.sample_count,
        "collision_risk_count": sum(t.building_collisions for t in trajectories) + report.pair_count,
        "avg_flight_distance_m": _avg([t.distance_m for t in trajectories]),
        "avg_flight_time_s": _avg(flight_times),
        "avg_delay_s": _avg([t.delay_s for t in trajectories]),
        "avg_takeoff_pad_delay_s": _avg([t.takeoff_pad_delay_s for t in trajectories]),
        "avg_landing_pad_delay_s": _avg([t.landing_pad_delay_s for t in trajectories]),
        "avg_pad_delay_s": _avg([t.pad_delay_s for t in trajectories]),
        "max_pad_delay_s": max((t.pad_delay_s for t in trajectories), default=0.0),
        "pad_wait_flight_count": sum(1 for t in trajectories if t.pad_delay_s > 0),
        "avg_detour_distance_m": _avg([t.detour_distance_m for t in trajectories]),
        "avg_altitude_changes": _avg([t.altitude_changes for t in trajectories]),
        "avg_path_changes": _avg([t.path_changes for t in trajectories]),
    }


def build_raw_rows(
    experiment: Experiment,
    trajectories: list[AircraftTrajectory],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trajectory in trajectories:
        for sample in trajectory.samples:
            rows.append(
                {
                    "scenario_id": experiment.scenario_id,
                    "sweep": experiment.sweep,
                    "model": experiment.model,
                    "flight_id": trajectory.mission.id,
                    "aircraft_id": trajectory.mission.vehicle_id
                    if trajectory.mission.vehicle_id is not None
                    else trajectory.mission.id,
                    "time_s": round(sample.time_s, 3),
                    "x": round(sample.x, 3),
                    "y": round(sample.y, 3),
                    "z": round(sample.z, 3),
                    "phase": sample.phase,
                    "cruise_altitude": trajectory.cruise_altitude,
                    "start_time": round(trajectory.start_time, 3),
                    "cruise_arrival_time": round(trajectory.cruise_arrival_time, 3),
                    "descent_start_time": round(trajectory.descent_start_time, 3),
                    "end_time": round(trajectory.end_time, 3),
                    "origin_id": trajectory.mission.origin_id,
                    "destination_id": trajectory.mission.destination_id,
                    "speed_kmh": experiment.speed_kmh,
                    "safety_distance_m": experiment.safety_distance_m,
                    "takeoff_pad_delay_s": round(trajectory.takeoff_pad_delay_s, 3),
                    "landing_pad_delay_s": round(trajectory.landing_pad_delay_s, 3),
                    "pad_delay_s": round(trajectory.pad_delay_s, 3),
                }
            )
    return rows


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stable_seed(base_seed: int, key: str) -> int:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(base_seed) + int(digest[:8], 16)
