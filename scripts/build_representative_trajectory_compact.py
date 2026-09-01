from __future__ import annotations

import argparse
import math
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
FIGURE_SURROUNDING_VERTIPORT_COUNT = 2
FIGURE_MISSION_COUNT = 3
FIGURE_MISSION_COLORS = ["#d62728", "#2ca02c", "#9467bd"]
FIGURE_PATH_VERTIPORT_CLEARANCE_M = 120.0
FIGURE_VERTIPORT_SIZE = 78
EXCLUDED_FLIGHT_IDS_FOR_FIGURE = {10}


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
    flight_ids = resolve_display_flight_ids(
        parse_flight_ids(args.flight_ids),
        choose_flights(flight_df, raw_df, count=args.count),
    )
    plot_trajectories(city_map, raw_df, flight_ids, output_path)
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


def resolve_display_flight_ids(explicit_ids: list[int], chosen_ids: list[int]) -> list[int]:
    if explicit_ids:
        return explicit_ids[:FIGURE_MISSION_COUNT]
    if len(chosen_ids) > FIGURE_MISSION_COUNT:
        return chosen_ids[1 : FIGURE_MISSION_COUNT + 1]
    return chosen_ids[:FIGURE_MISSION_COUNT]


def flight_path_signature(raw_df: pd.DataFrame, flight_id: int) -> tuple[tuple[float, float], ...]:
    samples = (
        raw_df[raw_df["flight_id"] == flight_id]
        .sort_values("time_s")
        .drop_duplicates(["x", "y"])
    )
    if samples.empty:
        return ()
    return tuple(zip(samples["x"].round(2), samples["y"].round(2)))


def choose_flights(flight_df: pd.DataFrame, raw_df: pd.DataFrame, count: int) -> list[int]:
    chosen: list[int] = []
    signatures: set[tuple[tuple[float, float], ...]] = set()

    def try_add(flight_id: int) -> bool:
        if flight_id in EXCLUDED_FLIGHT_IDS_FOR_FIGURE:
            return False
        if flight_id in chosen:
            return False
        signature = flight_path_signature(raw_df, flight_id)
        if not signature or signature in signatures:
            return False
        chosen.append(flight_id)
        signatures.add(signature)
        return True

    preferred = flight_df[
        (flight_df["path_changes"] > 0)
        & (flight_df["building_collisions"] == 0)
    ].sort_values(["path_changes", "detour_distance_m"], ascending=[False, False])
    for flight_id in preferred["flight_id"].astype(int):
        try_add(flight_id)
        if len(chosen) >= max(1, count // 2):
            break

    remaining = flight_df.sort_values(["start_time", "flight_id"])
    for flight_id in remaining["flight_id"].astype(int):
        try_add(flight_id)
        if len(chosen) >= count:
            break
    return chosen[:count]


def surrounding_vertiport_locations(
    city_map,
    mission_paths: list[pd.DataFrame],
    endpoint_points: list[tuple[float, float]],
    target_count: int = FIGURE_SURROUNDING_VERTIPORT_COUNT,
) -> list[tuple[float, float]]:
    center_x = city_map.width / 2.0
    center_y = city_map.height / 2.0
    endpoint_keys = {(round(x, 1), round(y, 1)) for x, y in endpoint_points}
    candidates: list[tuple[float, float, float]] = []

    for building in city_map.buildings:
        point_x = building.center.x
        point_y = building.center.y
        key = (round(point_x, 1), round(point_y, 1))
        if key in endpoint_keys:
            continue
        if min_distance_to_mission_paths(point_x, point_y, mission_paths) < FIGURE_PATH_VERTIPORT_CLEARANCE_M:
            continue
        distance_to_center = math.hypot(point_x - center_x, point_y - center_y)
        candidates.append((point_x, point_y, distance_to_center))

    candidates.sort(key=lambda item: item[2])

    selected: list[tuple[float, float]] = []
    min_separation_m = 180.0
    for point_x, point_y, _ in candidates:
        if len(selected) >= target_count:
            break
        if any(math.hypot(point_x - sx, point_y - sy) < min_separation_m for sx, sy in selected):
            continue
        selected.append((point_x, point_y))
    return selected


def point_to_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy
    return math.hypot(px - nearest_x, py - nearest_y)


def min_distance_to_mission_paths(px: float, py: float, mission_paths: list[pd.DataFrame]) -> float:
    min_distance = float("inf")
    for samples in mission_paths:
        xs = samples["x"].to_numpy()
        ys = samples["y"].to_numpy()
        for x, y in zip(xs, ys):
            min_distance = min(min_distance, math.hypot(px - x, py - y))
        for index in range(len(xs) - 1):
            segment_distance = point_to_segment_distance(px, py, xs[index], ys[index], xs[index + 1], ys[index + 1])
            min_distance = min(min_distance, segment_distance)
    return min_distance


def filter_vertiports_near_paths(
    locations: list[tuple[float, float]],
    mission_paths: list[pd.DataFrame],
    endpoint_points: list[tuple[float, float]],
    clearance_m: float = FIGURE_PATH_VERTIPORT_CLEARANCE_M,
) -> list[tuple[float, float]]:
    endpoint_keys = {(round(x, 1), round(y, 1)) for x, y in endpoint_points}
    filtered: list[tuple[float, float]] = []
    for x, y in locations:
        key = (round(x, 1), round(y, 1))
        if key in endpoint_keys:
            continue
        if min_distance_to_mission_paths(x, y, mission_paths) >= clearance_m:
            filtered.append((x, y))
    return filtered


def collect_endpoint_points(mission_paths: list[pd.DataFrame]) -> list[tuple[float, float]]:
    endpoint_points: list[tuple[float, float]] = []
    for samples in mission_paths:
        endpoint_points.append((float(samples["x"].iloc[0]), float(samples["y"].iloc[0])))
        endpoint_points.append((float(samples["x"].iloc[-1]), float(samples["y"].iloc[-1])))
    return endpoint_points


def prepare_mission_paths(raw_df: pd.DataFrame, flight_ids: list[int]) -> list[pd.DataFrame]:
    mission_paths: list[pd.DataFrame] = []
    for flight_id in flight_ids:
        samples = mission_samples(raw_df, flight_id)
        if not samples.empty:
            mission_paths.append(samples)
    return mission_paths


def mission_samples(raw_df: pd.DataFrame, flight_id: int) -> pd.DataFrame:
    return (
        raw_df[raw_df["flight_id"] == flight_id]
        .sort_values("time_s")
        .drop_duplicates(["x", "y"])
    )


def plot_trajectories(city_map, raw_df: pd.DataFrame, flight_ids: list[int], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 5.0), dpi=300)
    draw_map(ax, city_map)

    mission_paths = prepare_mission_paths(raw_df, flight_ids)
    endpoint_points = collect_endpoint_points(mission_paths)
    draw_vertiports(ax, city_map, mission_paths, endpoint_points)

    plotted_flights: list[tuple[pd.DataFrame, str]] = []
    for mission_index, samples in enumerate(mission_paths):
        color = FIGURE_MISSION_COLORS[mission_index % len(FIGURE_MISSION_COLORS)]
        label = f"Mission {mission_index + 1}"
        ax.plot(samples["x"], samples["y"], color=color, linewidth=1.7, label=label, zorder=6)
        plotted_flights.append((samples, color))

    for samples, color in plotted_flights:
        ax.scatter(
            samples["x"].iloc[0],
            samples["y"].iloc[0],
            s=24,
            color=color,
            marker="o",
            edgecolor="white",
            linewidth=0.6,
            zorder=8,
        )
        ax.scatter(
            samples["x"].iloc[-1],
            samples["y"].iloc[-1],
            s=30,
            color=color,
            marker="X",
            edgecolor="white",
            linewidth=0.6,
            zorder=8,
        )

    ax.scatter([], [], s=34, color="#222222", marker="o", label="Start")
    ax.scatter([], [], s=38, color="#222222", marker="X", label="End")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.legend(loc="upper right", frameon=True, framealpha=0.92, borderpad=0.45)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def draw_vertiports(
    ax: plt.Axes,
    city_map,
    mission_paths: list[pd.DataFrame],
    endpoint_points: list[tuple[float, float]],
) -> None:
    surrounding_points = surrounding_vertiport_locations(
        city_map,
        mission_paths,
        endpoint_points,
    )[:FIGURE_SURROUNDING_VERTIPORT_COUNT]

    unique_points: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for point in surrounding_points + endpoint_points:
        key = (round(point[0], 1), round(point[1], 1))
        if key in seen:
            continue
        seen.add(key)
        unique_points.append(point)

    if not unique_points:
        return

    xs, ys = zip(*unique_points)
    ax.scatter(
        xs,
        ys,
        s=FIGURE_VERTIPORT_SIZE,
        c="#ffbf00",
        marker="^",
        edgecolors="#111111",
        linewidths=0.9,
        alpha=1.0,
        zorder=7,
        label="Vertiport",
    )


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
    parser.add_argument("--count", type=int, default=4, help="Number of trajectories to choose before display filtering")
    parser.add_argument("--config", default=str(DEFAULT_SCENARIO_CONFIG), help=argparse.SUPPRESS)
    return parser.parse_args()


if __name__ == "__main__":
    main()
