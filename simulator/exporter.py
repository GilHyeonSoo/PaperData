from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import ROOT_DIR
from .simulation import SimulationResult


def export_results(
    results: list[SimulationResult],
    output_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_dir = Path(output_dir) if output_dir else ROOT_DIR / "outputs"
    raw_dir = base_dir / "raw"
    processed_dir = base_dir / "processed"
    summary_dir = base_dir / "summary"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)

    summary_df = pd.DataFrame([result.summary for result in results])
    raw_df = pd.DataFrame(row for result in results for row in result.raw_rows)

    raw_path = raw_dir / "simulation_log.csv"
    summary_path = processed_dir / "summary_results.csv"
    comparison_path = summary_dir / "model_comparison.csv"

    raw_df.to_csv(raw_path, index=False)
    summary_df.to_csv(summary_path, index=False)

    comparison = (
        summary_df[summary_df["sweep"] == "model_comparison"]
        .sort_values(["model"])
        .reset_index(drop=True)
    )
    comparison.to_csv(comparison_path, index=False)

    _export_flight_results(results, processed_dir / "flight_results.csv")
    _export_pad_usage(results, processed_dir / "vertiport_pad_usage.csv")
    return summary_df, raw_df


def _export_flight_results(results: list[SimulationResult], path: Path) -> None:
    rows = []
    for result in results:
        exp = result.experiment
        for trajectory in result.trajectories:
            rows.append(
                {
                    "scenario_id": exp.scenario_id,
                    "sweep": exp.sweep,
                    "model": exp.model,
                    "flight_id": trajectory.mission.id,
                    "aircraft_id": trajectory.mission.vehicle_id
                    if trajectory.mission.vehicle_id is not None
                    else trajectory.mission.id,
                    "planned_start_time": trajectory.mission.planned_start_time,
                    "start_time": trajectory.start_time,
                    "cruise_arrival_time": trajectory.cruise_arrival_time,
                    "descent_start_time": trajectory.descent_start_time,
                    "end_time": trajectory.end_time,
                    "delay_s": trajectory.delay_s,
                    "takeoff_pad_delay_s": trajectory.takeoff_pad_delay_s,
                    "landing_pad_delay_s": trajectory.landing_pad_delay_s,
                    "pad_delay_s": trajectory.pad_delay_s,
                    "takeoff_pad_start_s": trajectory.takeoff_pad_start_s,
                    "takeoff_pad_end_s": trajectory.takeoff_pad_end_s,
                    "landing_pad_start_s": trajectory.landing_pad_start_s,
                    "landing_pad_end_s": trajectory.landing_pad_end_s,
                    "cruise_altitude": trajectory.cruise_altitude,
                    "distance_m": trajectory.distance_m,
                    "detour_distance_m": trajectory.detour_distance_m,
                    "building_risks": trajectory.building_risks,
                    "building_collisions": trajectory.building_collisions,
                    "path_changes": trajectory.path_changes,
                    "altitude_changes": trajectory.altitude_changes,
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)


def _export_pad_usage(results: list[SimulationResult], path: Path) -> None:
    rows = []
    columns = [
        "scenario_id",
        "sweep",
        "model",
        "vertiport_id",
        "flight_id",
        "aircraft_id",
        "operation",
        "start_s",
        "end_s",
        "duration_s",
        "pad_delay_s",
    ]
    for result in results:
        exp = result.experiment
        for trajectory in result.trajectories:
            aircraft_id = (
                trajectory.mission.vehicle_id
                if trajectory.mission.vehicle_id is not None
                else trajectory.mission.id
            )
            takeoff_duration = trajectory.takeoff_pad_end_s - trajectory.takeoff_pad_start_s
            if takeoff_duration > 0:
                rows.append(
                    {
                        "scenario_id": exp.scenario_id,
                        "sweep": exp.sweep,
                        "model": exp.model,
                        "vertiport_id": trajectory.mission.origin_id,
                        "flight_id": trajectory.mission.id,
                        "aircraft_id": aircraft_id,
                        "operation": "takeoff",
                        "start_s": trajectory.takeoff_pad_start_s,
                        "end_s": trajectory.takeoff_pad_end_s,
                        "duration_s": takeoff_duration,
                        "pad_delay_s": trajectory.takeoff_pad_delay_s,
                    }
                )
            landing_duration = trajectory.landing_pad_end_s - trajectory.landing_pad_start_s
            if landing_duration > 0:
                rows.append(
                    {
                        "scenario_id": exp.scenario_id,
                        "sweep": exp.sweep,
                        "model": exp.model,
                        "vertiport_id": trajectory.mission.destination_id,
                        "flight_id": trajectory.mission.id,
                        "aircraft_id": aircraft_id,
                        "operation": "landing",
                        "start_s": trajectory.landing_pad_start_s,
                        "end_s": trajectory.landing_pad_end_s,
                        "duration_s": landing_duration,
                        "pad_delay_s": trajectory.landing_pad_delay_s,
                    }
                )
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
