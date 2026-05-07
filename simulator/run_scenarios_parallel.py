from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .config import DEFAULT_CONFIG_PATH, ROOT_DIR, load_config
from .continuous_simulation import run_continuous_scenario
from .exporter import export_results
from .visualizer import plot_city_map, plot_trajectories


SCENARIO_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "scenarios.yaml"


def main() -> None:
    args = _parse_args()
    base_config = load_config(DEFAULT_CONFIG_PATH)
    scenario_file = _load_scenario_file(args.config)
    runner_cfg = scenario_file.get("scenario_runner", {})
    scenarios = scenario_file["scenarios"]
    selected = _select_scenarios(scenarios, args.only)
    output_root = _resolve_output_root(args.output_root, runner_cfg, args.quick_test)
    max_workers = args.max_workers or int(runner_cfg.get("max_workers", 5))
    max_workers = max(1, min(max_workers, len(selected)))

    print(f"Running scenarios in parallel: {', '.join(selected.keys())}")
    print(f"max_workers={max_workers}")
    print(f"output_root={output_root}")

    summaries: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for name, scenario_cfg in selected.items():
            worker_cfg = _quickened_config(scenario_cfg) if args.quick_test else scenario_cfg
            futures[
                executor.submit(
                    _run_and_export_scenario,
                    name,
                    base_config,
                    worker_cfg,
                    str(output_root),
                )
            ] = name
            print(f"[{name}] submitted")

        for future in as_completed(futures):
            name = futures[future]
            try:
                summary = future.result()
            except Exception as exc:
                print(f"[{name}] failed: {exc}")
                raise
            summaries.append(summary)
            print(
                f"[{name}] completed: generated={summary['generated_missions']} "
                f"collision_risks={summary['collision_risk_count']} "
                f"avg_pad_delay={summary['avg_pad_delay_s']:.2f}s"
            )

    summary_df = pd.DataFrame(summaries).sort_values("scenario_name").reset_index(drop=True)
    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "all_scenarios_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"All scenarios completed. Summary saved to {summary_path}")


def _run_and_export_scenario(
    name: str,
    base_config: dict[str, Any],
    scenario_config: dict[str, Any],
    output_root: str,
) -> dict[str, Any]:
    scenario_output_dir = Path(output_root) / name
    scenario_output_dir.mkdir(parents=True, exist_ok=True)
    continuous_result = run_continuous_scenario(name, base_config, scenario_config)
    result = continuous_result.result
    export_results([result], output_dir=scenario_output_dir)
    plot_city_map(result.city_map, output_dir=scenario_output_dir)
    plot_trajectories(result, output_dir=scenario_output_dir, max_aircraft=40)
    _write_vehicle_reuse(continuous_result.vehicle_mission_counts, scenario_output_dir)
    _write_effective_config(scenario_config, scenario_output_dir)
    return result.summary


def _write_vehicle_reuse(vehicle_counts: dict[int, int], output_dir: Path) -> None:
    rows = [
        {"aircraft_id": vehicle_id, "mission_count": count}
        for vehicle_id, count in sorted(vehicle_counts.items())
    ]
    processed_dir = output_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(processed_dir / "vehicle_reuse.csv", index=False)


def _write_effective_config(scenario_config: dict[str, Any], output_dir: Path) -> None:
    with (output_dir / "scenario_config.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(scenario_config, f, allow_unicode=True, sort_keys=False)


def _load_scenario_file(path: str | None) -> dict[str, Any]:
    config_path = Path(path) if path else SCENARIO_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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


def _resolve_output_root(
    arg_output_root: str | None,
    runner_cfg: dict[str, Any],
    quick_test: bool,
) -> Path:
    if arg_output_root:
        return ROOT_DIR / arg_output_root if not Path(arg_output_root).is_absolute() else Path(arg_output_root)
    if quick_test:
        return ROOT_DIR / "outputs" / "scenarios_quick"
    configured = Path(runner_cfg.get("output_root", "outputs/scenarios"))
    return ROOT_DIR / configured if not configured.is_absolute() else configured


def _quickened_config(config: dict[str, Any]) -> dict[str, Any]:
    quick = deepcopy(config)
    quick.setdefault("simulation", {})
    quick.setdefault("aircraft", {})
    quick["simulation"]["duration"] = min(int(quick["simulation"].get("duration", 300)), 300)
    quick["simulation"]["mission_interval"] = max(int(quick["simulation"].get("mission_interval", 60)), 60)
    quick["simulation"]["time_step"] = max(int(quick["simulation"].get("time_step", 10)), 10)
    quick["simulation"]["conflict_time_step"] = max(int(quick["simulation"].get("conflict_time_step", 20)), 20)
    quick["simulation"]["max_departure_delay"] = min(int(quick["simulation"].get("max_departure_delay", 120)), 120)
    quick["simulation"]["delay_step"] = max(int(quick["simulation"].get("delay_step", 60)), 60)
    quick["aircraft"]["fleet_size"] = min(int(quick["aircraft"].get("fleet_size", 20)), 20)
    return quick


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run S1-S5 long-duration scenarios in parallel.")
    parser.add_argument("--config", help="Path to scenarios.yaml. Defaults to simulator/config/scenarios.yaml")
    parser.add_argument("--only", help="Comma-separated scenario names, e.g. S1,S3")
    parser.add_argument("--max-workers", type=int, help="Number of parallel worker processes")
    parser.add_argument("--output-root", help="Output root directory. Relative paths are under project root")
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="Run shortened scenario(s) for smoke testing and write to outputs/scenarios_quick by default",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
