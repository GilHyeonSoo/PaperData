from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from .config import ROOT_DIR
from .map_generator import CityMap
from .simulation import SimulationResult


def plot_city_map(city_map: CityMap, path: Path | None = None, output_dir: str | Path | None = None) -> None:
    if path is None:
        base_dir = Path(output_dir) if output_dir else ROOT_DIR
        path = base_dir / "figures" / "maps" / "city_map.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8))
    _draw_map(ax, city_map)
    ax.set_title("Generated Grid City Map")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_trajectories(
    result: SimulationResult,
    path: Path | None = None,
    max_aircraft: int = 30,
    output_dir: str | Path | None = None,
) -> None:
    if path is None:
        base_dir = Path(output_dir) if output_dir else ROOT_DIR
        path = base_dir / "figures" / "trajectories" / "trajectory_map.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8))
    _draw_map(ax, result.city_map)
    for trajectory in result.trajectories[:max_aircraft]:
        xs = [sample.x for sample in trajectory.samples if sample.phase == "cruise"]
        ys = [sample.y for sample in trajectory.samples if sample.phase == "cruise"]
        if xs and ys:
            ax.plot(xs, ys, linewidth=1.1, alpha=0.75)
    ax.set_title(f"Trajectories ({result.experiment.model}, {result.experiment.scenario_id})")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_summary_graphs(summary_df: pd.DataFrame, output_dir: str | Path | None = None) -> None:
    base_dir = Path(output_dir) if output_dir else ROOT_DIR
    _plot_metric_by_x(
        summary_df[summary_df["sweep"] == "aircraft_count"],
        "aircraft_count",
        "collision_risk_count",
        base_dir / "figures" / "collision_graphs" / "collision_by_aircraft_count.png",
        "Collision Risks by Aircraft Count",
        "Aircraft count",
    )
    _plot_metric_by_x(
        summary_df[summary_df["sweep"] == "speed"],
        "speed_kmh",
        "collision_risk_count",
        base_dir / "figures" / "collision_graphs" / "collision_by_speed.png",
        "Collision Risks by Speed",
        "Speed (km/h)",
    )
    _plot_metric_by_x(
        summary_df[summary_df["sweep"] == "building_density"],
        "building_density",
        "collision_risk_count",
        base_dir / "figures" / "collision_graphs" / "collision_by_density.png",
        "Collision Risks by Building Density",
        "Building density",
    )
    _plot_metric_by_x(
        summary_df[summary_df["sweep"] == "vertiport_count"],
        "vertiport_count",
        "collision_risk_count",
        base_dir / "figures" / "comparison_graphs" / "collision_by_vertiport_count.png",
        "Collision Risks by Vertiport Count",
        "Vertiport count",
    )
    _plot_metric_by_x(
        summary_df[summary_df["sweep"] == "vertiport_count"],
        "vertiport_count",
        "avg_pad_delay_s",
        base_dir / "figures" / "comparison_graphs" / "pad_delay_by_vertiport_count.png",
        "Average Pad Delay by Vertiport Count",
        "Vertiport count",
    )
    _plot_model_comparison(summary_df, base_dir)
    _plot_safety_sensitivity(summary_df, base_dir)


def _draw_map(ax: plt.Axes, city_map: CityMap) -> None:
    for building in city_map.buildings:
        rect = plt.Rectangle(
            (building.x, building.y),
            building.width,
            building.depth,
            facecolor=plt.cm.Greys(min(0.9, 0.25 + building.height / 400.0)),
            edgecolor="black",
            linewidth=0.2,
            alpha=0.75,
        )
        ax.add_patch(rect)
    for vertiport in city_map.vertiports:
        ax.scatter(vertiport.x, vertiport.y, s=45, c="#d62728", marker="^", edgecolors="white")
    ax.set_xlim(0, city_map.width)
    ax.set_ylim(0, city_map.height)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(color="#dddddd", linewidth=0.4)


def _plot_metric_by_x(
    df: pd.DataFrame,
    x_col: str,
    metric_col: str,
    path: Path,
    title: str,
    xlabel: str,
) -> None:
    if df.empty:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    for model, model_df in df.groupby("model"):
        grouped = model_df.groupby(x_col, as_index=False)[metric_col].mean().sort_values(x_col)
        ax.plot(grouped[x_col], grouped[metric_col], marker="o", label=f"Model {model}")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Collision risk count")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_model_comparison(summary_df: pd.DataFrame, base_dir: Path) -> None:
    df = summary_df[summary_df["sweep"] == "model_comparison"].copy()
    if df.empty:
        return
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    metrics = [
        ("collision_risk_count", "Collision risks"),
        ("avg_flight_time_s", "Avg flight time (s)"),
        ("avg_flight_distance_m", "Avg distance (m)"),
    ]
    for ax, (metric, title) in zip(axes, metrics):
        ax.bar(df["model"], df[metric], color="#4c78a8")
        ax.set_title(title)
        ax.set_xlabel("Model")
        ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = base_dir / "figures" / "comparison_graphs" / "model_comparison.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_safety_sensitivity(summary_df: pd.DataFrame, base_dir: Path) -> None:
    df = summary_df[summary_df["sweep"] == "safety_distance"].copy()
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    for model, model_df in df.groupby("model"):
        grouped = model_df.groupby("safety_label", as_index=False)["collision_risk_count"].mean()
        ax.plot(grouped["safety_label"], grouped["collision_risk_count"], marker="o", label=f"Model {model}")
    ax.set_title("Safety Distance Sensitivity")
    ax.set_xlabel("Safety distance")
    ax.set_ylabel("Collision risk count")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = base_dir / "figures" / "comparison_graphs" / "safety_distance_sensitivity.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
