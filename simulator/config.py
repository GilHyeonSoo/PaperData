from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "default.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def kmh_to_mps(speed_kmh: float) -> float:
    return speed_kmh * 1000.0 / 3600.0


def altitude_layers(config: dict[str, Any]) -> list[float]:
    alt = config["altitude"]
    start = int(alt["min_cruise_altitude"])
    stop = int(alt["max_cruise_altitude"])
    step = int(alt["layer_interval"])
    return [float(v) for v in range(start, stop + step, step)]


def ensure_output_dirs() -> None:
    for relative in [
        "outputs/raw",
        "outputs/processed",
        "outputs/summary",
        "figures/maps",
        "figures/trajectories",
        "figures/collision_graphs",
        "figures/comparison_graphs",
    ]:
        (ROOT_DIR / relative).mkdir(parents=True, exist_ok=True)

