from __future__ import annotations

import argparse
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .config import DEFAULT_CONFIG_PATH, ROOT_DIR, load_config
from .continuous_simulation import run_continuous_scenario
from .exporter import export_results
from .run_scenarios_parallel import SCENARIO_CONFIG_PATH
from .visualizer import plot_city_map, plot_trajectories


SAVE_RUN_DETAIL_CHOICES = {"all", "first", "none"}


def main() -> None:
    args = _parse_args()
    base_config = load_config(DEFAULT_CONFIG_PATH)
    scenario_file = _load_yaml(args.config)
    wall_cfg = scenario_file.get("wallclock_runner", {})
    scenarios = _select_scenarios(scenario_file["scenarios"], args.only)

    target_seconds = args.target_seconds or int(wall_cfg.get("target_seconds", 3600))
    max_workers = args.max_workers or int(wall_cfg.get("max_workers", 5))
    max_workers = max(1, min(max_workers, len(scenarios)))
    output_root = _resolve_output_root(args.output_root, wall_cfg)
    save_run_details = args.save_run_details or str(wall_cfg.get("save_run_details", "all"))
    _validate_save_run_details(save_run_details)

    if args.quick_test:
        target_seconds = 20
        output_root = _resolve_output_root(args.output_root, {"output_root": "outputs/scenarios_wallclock_quick"})
        save_run_details = "first"

    if args.overwrite and output_root.exists():
        shutil.rmtree(output_root)

    print(f"Wall-clock target: {target_seconds}s", flush=True)
    print(f"Running scenarios in parallel: {', '.join(scenarios.keys())}", flush=True)
    print(f"max_workers={max_workers}", flush=True)
    print(f"output_root={output_root}", flush=True)
    print(f"resume={args.resume}", flush=True)
    print(f"save_run_details={save_run_details}", flush=True)

    output_root.mkdir(parents=True, exist_ok=True)
    scenario_summaries: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for name, scenario_cfg in scenarios.items():
            futures[
                executor.submit(
                    _run_wallclock_scenario,
                    name,
                    base_config,
                    scenario_cfg,
                    wall_cfg,
                    target_seconds,
                    args.quick_test,
                    str(output_root),
                    args.resume,
                    save_run_details,
                )
            ] = name
            print(f"[{name}] submitted", flush=True)

        for future in as_completed(futures):
            name = futures[future]
            summary = future.result()
            scenario_summaries.append(summary)
            print(
                f"[{name}] completed: runs={summary['run_count']} "
                f"missions={summary['generated_missions_total']} "
                f"wall_time={summary['wall_time_s']:.1f}s",
                flush=True,
            )

    if scenario_summaries:
        scenario_df = pd.DataFrame(scenario_summaries).sort_values("scenario_name")
        scenario_df.to_csv(output_root / "all_scenarios_summary.csv", index=False)
    _write_all_runs_summary(output_root)
    print(f"All wall-clock scenario workers completed. Summary saved to {output_root}", flush=True)


def _run_wallclock_scenario(
    name: str,
    base_config: dict[str, Any],
    scenario_config: dict[str, Any],
    wall_cfg: dict[str, Any],
    target_seconds: int,
    quick_test: bool,
    output_root: str,
    resume: bool,
    save_run_details: str,
) -> dict[str, Any]:
    scenario_dir = Path(output_root) / name
    runs_dir = scenario_dir / "runs"
    summary_dir = scenario_dir / "summary"
    runs_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)

    models = list(wall_cfg.get("models", ["A", "B", "C", "D"]))
    if quick_test:
        models = ["E"]

    runs_summary_path = summary_dir / "scenario_runs_summary.csv"
    if runs_summary_path.exists() and not resume:
        raise FileExistsError(
            f"{runs_summary_path} already exists. Use --resume to continue or --overwrite to start fresh."
        )

    run_rows, existing_run_ids, previous_wall_time_s = _load_resume_state(
        name,
        summary_dir,
        runs_summary_path,
        resume,
    )
    cycle = _starting_cycle(run_rows, models) if resume else 0
    started = time.monotonic() - previous_wall_time_s
    report_interval = float(wall_cfg.get("report_interval_seconds", 60))
    next_report_at = previous_wall_time_s + report_interval

    _write_yaml(
        {
            "scenario_name": name,
            "target_seconds": target_seconds,
            "resume": resume,
            "save_run_details": save_run_details,
            "models": models,
            "scenario_config": scenario_config,
            "wallclock_runner": wall_cfg,
        },
        summary_dir / "effective_wallclock_config.yaml",
    )

    print(
        f"[{name}] wall-clock worker started "
        f"(existing_runs={len(existing_run_ids)}, start_cycle={cycle}, "
        f"elapsed_before={previous_wall_time_s:.1f}s)",
        flush=True,
    )

    while time.monotonic() - started < target_seconds:
        completed_or_skipped_in_cycle = 0
        for model_index, model in enumerate(models):
            run_seed = int(wall_cfg.get("seed_start", 1000)) + cycle * 100 + model_index
            run_id = f"{name}_cycle{cycle:04d}_{model}_seed{run_seed}"
            if run_id in existing_run_ids:
                completed_or_skipped_in_cycle += 1
                continue

            run_started = time.monotonic()
            run_cfg = _prepare_run_config(scenario_config, wall_cfg, model, run_seed, quick_test)
            run_output_dir = runs_dir / run_id

            continuous_result = run_continuous_scenario(name, base_config, run_cfg)
            result = continuous_result.result
            run_wall_time_s = time.monotonic() - run_started
            worker_elapsed_s = time.monotonic() - started
            result.summary.update(
                {
                    "run_id": run_id,
                    "cycle": cycle,
                    "run_seed": run_seed,
                    "scenario_name": name,
                    "wallclock_model": model,
                    "run_wall_time_s": run_wall_time_s,
                    "worker_elapsed_s": worker_elapsed_s,
                }
            )

            if _should_export_run(save_run_details, len(run_rows)):
                export_results([result], output_dir=run_output_dir)
                _write_vehicle_reuse(
                    continuous_result.vehicle_mission_counts,
                    run_output_dir / "processed" / "vehicle_reuse.csv",
                )
                _write_yaml(run_cfg, run_output_dir / "scenario_config.yaml")

            _write_first_figures_if_needed(scenario_dir, result)

            run_rows.append(result.summary)
            existing_run_ids.add(run_id)
            completed_or_skipped_in_cycle += 1
            _write_runs_summary(runs_summary_path, run_rows)

            elapsed_s = time.monotonic() - started
            progress = _aggregate_scenario_runs(name, pd.DataFrame(run_rows), elapsed_s)
            _write_yaml(progress, summary_dir / "latest_progress.yaml")
            if elapsed_s >= next_report_at or elapsed_s >= target_seconds:
                print(
                    f"[{name}] progress: elapsed={elapsed_s:.1f}s "
                    f"runs={progress['run_count']} "
                    f"missions={progress['generated_missions_total']} "
                    f"risks={progress['collision_risk_count_total']}",
                    flush=True,
                )
                next_report_at = elapsed_s + report_interval

            if elapsed_s >= target_seconds:
                break

        cycle += 1
        if completed_or_skipped_in_cycle == 0:
            raise RuntimeError(f"{name}: no runs were completed or skipped in cycle {cycle - 1}.")

    runs_df = pd.DataFrame(run_rows)
    _write_runs_summary(runs_summary_path, run_rows)
    aggregate = _aggregate_scenario_runs(name, runs_df, time.monotonic() - started)
    pd.DataFrame([aggregate]).to_csv(summary_dir / "scenario_aggregate_summary.csv", index=False)
    _write_yaml(aggregate, summary_dir / "latest_progress.yaml")
    return aggregate


def _prepare_run_config(
    scenario_config: dict[str, Any],
    wall_cfg: dict[str, Any],
    model: str,
    seed: int,
    quick_test: bool,
) -> dict[str, Any]:
    run_cfg = deepcopy(scenario_config)
    run_cfg["model"] = model
    run_cfg.setdefault("simulation", {})
    run_cfg["simulation"]["random_seed"] = seed
    run_cfg["simulation"]["duration"] = int(wall_cfg.get("duration", 10800))
    run_cfg["simulation"]["mission_interval"] = int(wall_cfg.get("mission_interval", 10))
    run_cfg["simulation"]["time_step"] = int(wall_cfg.get("time_step", 10))
    run_cfg["simulation"]["conflict_time_step"] = int(wall_cfg.get("conflict_time_step", 20))
    run_cfg["simulation"]["max_departure_delay"] = int(wall_cfg.get("max_departure_delay", 300))
    run_cfg["simulation"]["delay_step"] = int(wall_cfg.get("delay_step", 60))

    if quick_test:
        run_cfg["simulation"]["duration"] = 300
        run_cfg["simulation"]["mission_interval"] = 60
        run_cfg.setdefault("aircraft", {})
        run_cfg["aircraft"]["fleet_size"] = min(int(run_cfg["aircraft"].get("fleet_size", 20)), 20)
    return run_cfg


def _load_resume_state(
    name: str,
    summary_dir: Path,
    runs_summary_path: Path,
    resume: bool,
) -> tuple[list[dict[str, Any]], set[str], float]:
    if not resume or not runs_summary_path.exists():
        return [], set(), 0.0

    runs_df = pd.read_csv(runs_summary_path)
    run_rows = runs_df.to_dict("records")
    existing_run_ids = set(str(run_id) for run_id in runs_df.get("run_id", pd.Series(dtype=str)).dropna())
    previous_wall_time_s = _load_previous_wall_time(summary_dir, runs_df)
    print(
        f"[{name}] resume state loaded: runs={len(run_rows)}, previous_wall_time={previous_wall_time_s:.1f}s",
        flush=True,
    )
    return run_rows, existing_run_ids, previous_wall_time_s


def _load_previous_wall_time(summary_dir: Path, runs_df: pd.DataFrame) -> float:
    candidates: list[float] = []
    for filename in ["scenario_aggregate_summary.csv", "latest_progress.yaml"]:
        path = summary_dir / filename
        if not path.exists():
            continue
        try:
            if path.suffix == ".csv":
                df = pd.read_csv(path)
                if "wall_time_s" in df.columns and not df.empty:
                    candidates.append(float(df["wall_time_s"].max()))
            else:
                with path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if "wall_time_s" in data:
                    candidates.append(float(data["wall_time_s"]))
        except Exception:
            continue
    if "worker_elapsed_s" in runs_df.columns and not runs_df.empty:
        candidates.append(float(runs_df["worker_elapsed_s"].max()))
    return max(candidates, default=0.0)


def _starting_cycle(run_rows: list[dict[str, Any]], models: list[str]) -> int:
    if not run_rows:
        return 0
    runs_df = pd.DataFrame(run_rows)
    if "cycle" not in runs_df.columns or runs_df.empty:
        return 0
    max_cycle = int(runs_df["cycle"].max())
    cycle_rows = runs_df[runs_df["cycle"] == max_cycle]
    completed_models = {str(model) for model in cycle_rows.get("wallclock_model", [])}
    return max_cycle + 1 if set(models).issubset(completed_models) else max_cycle


def _should_export_run(save_run_details: str, completed_run_count: int) -> bool:
    if save_run_details == "all":
        return True
    if save_run_details == "first":
        return completed_run_count == 0
    return False


def _write_first_figures_if_needed(scenario_dir: Path, result) -> None:
    map_path = scenario_dir / "figures" / "maps" / "city_map_first_run.png"
    trajectory_path = scenario_dir / "figures" / "trajectories" / "trajectory_first_run.png"
    if not map_path.exists():
        plot_city_map(result.city_map, path=map_path)
    if not trajectory_path.exists():
        plot_trajectories(result, path=trajectory_path, max_aircraft=50)


def _aggregate_scenario_runs(
    name: str,
    runs_df: pd.DataFrame,
    wall_time_s: float,
) -> dict[str, Any]:
    if runs_df.empty:
        return {
            "scenario_name": name,
            "run_count": 0,
            "wall_time_s": wall_time_s,
            "generated_missions_total": 0,
            "completed_within_duration_total": 0,
            "completed_after_duration_total": 0,
            "collision_risk_count_total": 0,
            "building_collision_count_total": 0,
            "aircraft_collision_count_total": 0,
            "avg_pad_delay_s_mean": 0.0,
            "max_pad_delay_s_max": 0.0,
            "avg_flight_time_s_mean": 0.0,
            "models": "",
        }
    return {
        "scenario_name": name,
        "run_count": len(runs_df),
        "wall_time_s": wall_time_s,
        "generated_missions_total": int(runs_df["generated_missions"].sum()),
        "completed_within_duration_total": int(runs_df["completed_within_duration"].sum()),
        "completed_after_duration_total": int(runs_df["completed_after_duration"].sum()),
        "collision_risk_count_total": int(runs_df["collision_risk_count"].sum()),
        "building_collision_count_total": int(runs_df["building_collision_count"].sum()),
        "aircraft_collision_count_total": int(runs_df["aircraft_collision_count"].sum()),
        "avg_pad_delay_s_mean": float(runs_df["avg_pad_delay_s"].mean()),
        "max_pad_delay_s_max": float(runs_df["max_pad_delay_s"].max()),
        "avg_flight_time_s_mean": float(runs_df["avg_flight_time_s"].mean()),
        "models": ",".join(sorted(runs_df["wallclock_model"].astype(str).unique())),
    }


def _write_runs_summary(path: Path, run_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    pd.DataFrame(run_rows).to_csv(tmp_path, index=False)
    tmp_path.replace(path)


def _write_all_runs_summary(output_root: Path) -> None:
    frames = []
    for path in sorted(output_root.glob("*/summary/scenario_runs_summary.csv")):
        frames.append(pd.read_csv(path))
    if not frames:
        return
    pd.concat(frames, ignore_index=True).to_csv(output_root / "all_runs_summary.csv", index=False)


def _write_vehicle_reuse(vehicle_counts: dict[int, int], path: Path) -> None:
    rows = [
        {"aircraft_id": vehicle_id, "mission_count": count}
        for vehicle_id, count in sorted(vehicle_counts.items())
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _load_yaml(path: str | None) -> dict[str, Any]:
    config_path = Path(path) if path else SCENARIO_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _write_yaml(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _select_scenarios(
    scenarios: dict[str, dict[str, Any]],
    only: str | None,
) -> dict[str, dict[str, Any]]:
    if not only:
        return scenarios
    names = [name.strip() for name in only.split(",") if name.strip()]
    missing = [name for name in names if name not in scenarios]
    if missing:
        raise ValueError(f"Unknown scenario(s): {', '.join(missing)}")
    return {name: scenarios[name] for name in names}


def _resolve_output_root(arg_output_root: str | None, cfg: dict[str, Any]) -> Path:
    root = Path(arg_output_root or cfg.get("output_root", "outputs/scenarios_wallclock"))
    return root if root.is_absolute() else ROOT_DIR / root


def _validate_save_run_details(value: str) -> None:
    if value not in SAVE_RUN_DETAIL_CHOICES:
        raise ValueError(f"--save-run-details must be one of {sorted(SAVE_RUN_DETAIL_CHOICES)}.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run configured scenarios in parallel until each scenario worker reaches a wall-clock target."
    )
    parser.add_argument("--config", help="Path to scenarios.yaml")
    parser.add_argument("--only", help="Comma-separated scenario names, e.g. S1,S3")
    parser.add_argument("--max-workers", type=int, help="Number of parallel scenario workers")
    parser.add_argument("--target-seconds", type=int, help="Wall-clock target seconds per scenario worker")
    parser.add_argument("--output-root", help="Output root directory")
    parser.add_argument("--quick-test", action="store_true", help="Short smoke test")
    parser.add_argument("--resume", action="store_true", help="Continue from existing scenario summary files")
    parser.add_argument("--overwrite", action="store_true", help="Delete output root before starting")
    parser.add_argument(
        "--save-run-details",
        choices=sorted(SAVE_RUN_DETAIL_CHOICES),
        help=(
            "Per-run detail export mode. 'all' stores raw/processed files for every run, "
            "'first' stores detail files only for the first completed run in each scenario, "
            "and 'none' stores scenario summaries only."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
