from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import yaml
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator.config import DEFAULT_CONFIG_PATH, load_config
from simulator.continuous_simulation import merge_config
from simulator.map_generator import generate_city_map


DEFAULT_RUN_DIR = ROOT / "outputs" / "scenarios_wallclock_v2" / "S1" / "runs" / "S1_cycle0000_D_seed1003"
DEFAULT_OUTPUT = ROOT / "figures" / "scenario_maps_v2" / "representative_trajectory_s1_model_d_compact.png"
DEFAULT_SCENARIO_CONFIG = ROOT / "simulator" / "config" / "scenarios_v2.yaml"


def configure_matplotlib() -> None:
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in ["AppleGothic", "NanumGothic", "Malgun Gothic", "Noto Sans CJK KR", "DejaVu Sans"]:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams.update(
        {
            "axes.titlesize": 7,
            "axes.labelsize": 15,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "axes.unicode_minus": False,
        }
    )


def main() -> None:
    configure_matplotlib()
    args = parse_args()
    run_dir = resolve_path(args.run_dir, DEFAULT_RUN_DIR)
    output_path = resolve_path(args.output, DEFAULT_OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_path = run_dir / "raw" / "simulation_log.csv"
    flight_path = run_dir / "processed" / "flight_results.csv"
    scenario_path = run_dir / "scenario_config.yaml"
    if not raw_path.exists() or not flight_path.exists() or not scenario_path.exists():
        raise FileNotFoundError(f"Missing run files under {run_dir}")

    city_map = rebuild_city_map(scenario_path)
    raw_df = pd.read_csv(raw_path)
    flight_df = pd.read_csv(flight_path)
    flight_ids = parse_flight_ids(args.flight_ids) or choose_flights(flight_df, count=args.count)
    plot_trajectories(city_map, raw_df, flight_df, flight_ids, output_path)
    print(output_path)


def rebuild_city_map(scenario_path: Path):
    base_config = load_config(DEFAULT_CONFIG_PATH)
    with scenario_path.open("r", encoding="utf-8") as f:
        scenario_config = yaml.safe_load(f)
    config = merge_config(base_config, scenario_config)
    rng = random.Random(int(config["simulation"]["random_seed"]))
    return generate_city_map(
        config,
        rng,
        building_density=float(config["map"]["building_density"]),
        vertiport_count=int(config["vertiports"]["count"]),
    )


def choose_flights(flight_df: pd.DataFrame, count: int) -> list[int]:
    chosen: list[int] = []
    preferred = flight_df[
        (flight_df["path_changes"] > 0)
        & (flight_df["building_collisions"] == 0)
    ].sort_values(["path_changes", "detour_distance_m"], ascending=[False, False])
    for flight_id in preferred["flight_id"].astype(int):
        if flight_id not in chosen:
            chosen.append(flight_id)
        if len(chosen) >= max(1, count // 2):
            break

    remaining = flight_df.sort_values(["start_time", "flight_id"])
    for flight_id in remaining["flight_id"].astype(int):
        if flight_id not in chosen:
            chosen.append(flight_id)
        if len(chosen) >= count:
            break
    return chosen[:count]


def plot_trajectories(city_map, raw_df: pd.DataFrame, flight_df: pd.DataFrame, flight_ids: list[int], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 5.0), dpi=300)
    draw_map(ax, city_map)

    colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#8c564b"]
    for index, flight_id in enumerate(flight_ids):
        samples = (
            raw_df[raw_df["flight_id"] == flight_id]
            .sort_values("time_s")
            .drop_duplicates(["x", "y"])
        )
        if samples.empty:
            continue
        color = colors[index % len(colors)]
        label = f"Mission {index + 1}"
        ax.plot(samples["x"], samples["y"], color=color, linewidth=1.7, label=label, zorder=6)
        ax.scatter(samples["x"].iloc[0], samples["y"].iloc[0], s=32, color=color, marker="o", edgecolor="white", linewidth=0.6, zorder=7)
        ax.scatter(samples["x"].iloc[-1], samples["y"].iloc[-1], s=38, color=color, marker="X", edgecolor="white", linewidth=0.6, zorder=7)

    ax.scatter([], [], s=34, color="#222222", marker="o", label="Start")
    ax.scatter([], [], s=38, color="#222222", marker="X", label="End")
    ax.set_xlabel("x coordinate (m)")
    ax.set_ylabel("y coordinate (m)")
    ax.legend(loc="upper right", frameon=True, framealpha=0.92, borderpad=0.45)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def draw_map(ax: plt.Axes, city_map) -> None:
    for building in city_map.buildings:
        shade = min(0.86, 0.22 + building.height / 430.0)
        rect = plt.Rectangle(
            (building.x, building.y),
            building.width,
            building.depth,
            facecolor=plt.cm.Greys(shade),
            edgecolor="#4a4a4a",
            linewidth=0.12,
            alpha=0.68,
        )
        ax.add_patch(rect)
    ax.scatter(
        [vertiport.x for vertiport in city_map.vertiports],
        [vertiport.y for vertiport in city_map.vertiports],
        s=32,
        c="#ffbf00",
        marker="^",
        edgecolors="#222222",
        linewidths=0.45,
        zorder=5,
        label="Vertiport",
    )
    ax.set_xlim(0, city_map.width)
    ax.set_ylim(0, city_map.height)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(color="#dddddd", linewidth=0.35)
    ax.tick_params(width=0.5, length=2.5)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)


def parse_flight_ids(value: str | None) -> list[int]:
    if not value:
        return []
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def resolve_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact representative trajectory figure for the paper.")
    parser.add_argument("--run-dir", help="Run directory containing raw/ and processed/ outputs")
    parser.add_argument("--output", help="Output PNG path")
    parser.add_argument("--flight-ids", help="Comma-separated flight ids to draw")
    parser.add_argument("--count", type=int, default=4, help="Number of trajectories to draw when ids are not specified")
    parser.add_argument("--config", default=str(DEFAULT_SCENARIO_CONFIG), help=argparse.SUPPRESS)
    return parser.parse_args()


if __name__ == "__main__":
    main()
