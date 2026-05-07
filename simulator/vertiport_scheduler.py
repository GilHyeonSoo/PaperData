from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PadOccupancyManager:
    pad_count_per_vertiport: int
    enabled: bool = True
    intervals: dict[int, list[tuple[float, float]]] = field(default_factory=dict)

    def earliest_start(self, vertiport_id: int, desired_start: float, duration: float) -> float:
        if not self.enabled or duration <= 0:
            return desired_start

        start = desired_start
        booked = sorted(self.intervals.get(vertiport_id, []))
        while True:
            end = start + duration
            overlaps = [
                (slot_start, slot_end)
                for slot_start, slot_end in booked
                if slot_start < end and start < slot_end
            ]
            if len(overlaps) < self.pad_count_per_vertiport:
                return start
            start = min(slot_end for _, slot_end in overlaps)

    def reserve(self, vertiport_id: int, start: float, end: float) -> None:
        if not self.enabled or end <= start:
            return
        self.intervals.setdefault(vertiport_id, []).append((start, end))
        self.intervals[vertiport_id].sort()

    def utilization_rows(self, scenario_id: str) -> list[dict[str, float | int | str]]:
        rows = []
        for vertiport_id, intervals in sorted(self.intervals.items()):
            occupied = sum(end - start for start, end in intervals)
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "vertiport_id": vertiport_id,
                    "pad_count": self.pad_count_per_vertiport,
                    "operation_count": len(intervals),
                    "occupied_time_s": occupied,
                }
            )
        return rows


def make_pad_manager(config: dict) -> PadOccupancyManager:
    vertiport_cfg = config.get("vertiports", {})
    return PadOccupancyManager(
        pad_count_per_vertiport=max(1, int(vertiport_cfg.get("pad_count_per_vertiport", 1))),
        enabled=bool(vertiport_cfg.get("pad_occupancy_enabled", True)),
    )


def takeoff_occupancy_duration(config: dict) -> float:
    vertiport_cfg = config.get("vertiports", {})
    vertical_speed = float(config["aircraft"]["vertical_speed"])
    control_height = float(vertiport_cfg.get("vertical_control_height", 50))
    separation_time = float(vertiport_cfg.get("pad_separation_time", 30))
    return max(separation_time, control_height / vertical_speed)


def landing_occupancy_duration(config: dict) -> float:
    vertiport_cfg = config.get("vertiports", {})
    vertical_speed = float(config["aircraft"]["vertical_speed"])
    control_height = float(vertiport_cfg.get("vertical_control_height", 50))
    turnaround_time = float(vertiport_cfg.get("turnaround_time", 180))
    return control_height / vertical_speed + turnaround_time


def descent_to_control_zone_duration(config: dict, cruise_altitude: float, pad_altitude: float) -> float:
    vertiport_cfg = config.get("vertiports", {})
    vertical_speed = float(config["aircraft"]["vertical_speed"])
    control_height = float(vertiport_cfg.get("vertical_control_height", 50))
    descent_above_control_zone = max(0.0, cruise_altitude - pad_altitude - control_height)
    return descent_above_control_zone / vertical_speed
