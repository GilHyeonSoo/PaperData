from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulator.config import DEFAULT_CONFIG_PATH, load_config
from simulator.continuous_simulation import merge_config
from simulator.map_generator import generate_city_map


DEFAULT_SCENARIO_CONFIG = ROOT / "simulator" / "config" / "scenarios_v2.yaml"
DEFAULT_OUTPUT = ROOT / "figures" / "scenario_maps_v2" / "s1_s6_city_maps_panel.png"


def main() -> None:
    args = parse_args()
    scenario_config = resolve_path(args.config, DEFAULT_SCENARIO_CONFIG)
    output_path = resolve_path(args.output, DEFAULT_OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base_config = load_config(DEFAULT_CONFIG_PATH)
    with scenario_config.open("r", encoding="utf-8") as f:
        scenario_file = yaml.safe_load(f)

    maps = []
    for name, scenario_cfg in scenario_file["scenarios"].items():
        config = merge_config(base_config, scenario_cfg)
        rng = random.Random(int(config["simulation"]["random_seed"]))
        city_map = generate_city_map(
            config,
            rng,
            building_density=float(config["map"]["building_density"]),
            vertiport_count=int(config["vertiports"]["count"]),
        )
        maps.append((name, config, city_map))

    fig, axes = plt.subplots(2, 3, figsize=(11.6, 7.9), dpi=220)
    axes = axes.flatten()
    for ax, (name, config, city_map) in zip(axes, maps):
        draw_map(ax, city_map)
        width = int(config["map"]["width"])
        height = int(config["map"]["height"])
        vcount = int(config["vertiports"]["count"])
        density = float(config["map"]["building_density"])
        ax.set_title(f"{name}: {width} x {height} m, V={vcount}, density={density:.2f}", fontsize=8, pad=4)
        ax.set_xlabel("x (m)", fontsize=7)
        ax.set_ylabel("y (m)", fontsize=7)
    fig.tight_layout(pad=1.0, w_pad=1.0, h_pad=1.2)
    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(output_path)


def draw_map(ax: plt.Axes, city_map) -> None:
    for building in city_map.buildings:
        shade = min(0.9, 0.25 + building.height / 400.0)
        rect = plt.Rectangle(
            (building.x, building.y),
            building.width,
            building.depth,
            facecolor=plt.cm.Greys(shade),
            edgecolor="#333333",
            linewidth=0.12,
            alpha=0.78,
        )
        ax.add_patch(rect)
    for vertiport in city_map.vertiports:
        ax.scatter(
            vertiport.x,
            vertiport.y,
            s=18,
            c="#d62728",
            marker="^",
            edgecolors="white",
            linewidths=0.45,
            zorder=5,
        )
    ax.set_xlim(0, city_map.width)
    ax.set_ylim(0, city_map.height)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(color="#e0e0e0", linewidth=0.25)
    ax.tick_params(labelsize=6, width=0.4, length=2)
    for spine in ax.spines.values():
        spine.set_linewidth(0.5)


def resolve_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build S1-S6 scenario map panel for v2 experiments.")
    parser.add_argument("--config", help="Scenario config path, default simulator/config/scenarios_v2.yaml")
    parser.add_argument("--output", help="Output PNG path, default figures/scenario_maps_v2/s1_s6_city_maps_panel.png")
    return parser.parse_args()


if __name__ == "__main__":
    main()
