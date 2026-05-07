from __future__ import annotations

import random
from dataclasses import dataclass

from .building import Building
from .vertiport import Vertiport


@dataclass
class CityMap:
    width: float
    height: float
    grid_size: float
    road_width: float
    buildings: list[Building]
    vertiports: list[Vertiport]


def generate_city_map(
    config: dict,
    rng: random.Random,
    building_density: float | None = None,
    vertiport_count: int | None = None,
) -> CityMap:
    map_cfg = config["map"]
    width = float(map_cfg["width"])
    height = float(map_cfg["height"])
    grid_size = float(map_cfg["grid_size"])
    road_width = float(map_cfg["road_width"])
    density = float(building_density if building_density is not None else map_cfg["building_density"])

    buildings: list[Building] = []
    building_id = 0
    cols = int(width // grid_size)
    rows = int(height // grid_size)
    road_half = road_width / 2.0

    for i in range(cols):
        for j in range(rows):
            if rng.random() > density:
                continue
            min_x = i * grid_size + road_half
            min_y = j * grid_size + road_half
            max_x = (i + 1) * grid_size - road_half
            max_y = (j + 1) * grid_size - road_half
            lot_w = max_x - min_x
            lot_d = max_y - min_y
            if lot_w <= 5 or lot_d <= 5:
                continue

            scale_min = float(map_cfg["min_building_scale"])
            scale_max = float(map_cfg["max_building_scale"])
            bw = lot_w * rng.uniform(scale_min, scale_max)
            bd = lot_d * rng.uniform(scale_min, scale_max)
            bx = rng.uniform(min_x, max_x - bw)
            by = rng.uniform(min_y, max_y - bd)
            bh = rng.uniform(float(map_cfg["min_building_height"]), float(map_cfg["max_building_height"]))
            buildings.append(Building(building_id, bx, by, bw, bd, bh))
            building_id += 1

    v_count = int(vertiport_count if vertiport_count is not None else config["vertiports"]["count"])
    vertiports = _place_vertiports(buildings, v_count, rng)
    return CityMap(width, height, grid_size, road_width, buildings, vertiports)


def _place_vertiports(buildings: list[Building], count: int, rng: random.Random) -> list[Vertiport]:
    if not buildings:
        return []
    selected = rng.sample(buildings, min(count, len(buildings)))
    vertiports: list[Vertiport] = []
    for idx, building in enumerate(selected):
        center = building.center
        vertiports.append(Vertiport(idx, center.x, center.y, building.height, building.id))
    return vertiports

