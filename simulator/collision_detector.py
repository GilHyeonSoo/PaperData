from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .aircraft import AircraftTrajectory, TrajectorySample

ConflictBuckets = dict[int, dict[int, TrajectorySample]]


@dataclass
class AircraftConflictReport:
    pair_count: int
    sample_count: int
    pairs: set[tuple[int, int]]
    involved_aircraft: set[int]


def detect_aircraft_conflicts(
    trajectories: list[AircraftTrajectory],
    safety_distance_m: float,
    vertical_separation_m: float,
    time_step: float,
) -> AircraftConflictReport:
    buckets: dict[int, dict[int, TrajectorySample]] = defaultdict(dict)
    for trajectory in trajectories:
        for sample in trajectory.samples:
            bucket = int(round(sample.time_s / time_step))
            buckets[bucket][trajectory.mission.id] = sample

    pairs: set[tuple[int, int]] = set()
    involved: set[int] = set()
    sample_count = 0
    for samples_by_aircraft in buckets.values():
        samples = list(samples_by_aircraft.values())
        for i, left in enumerate(samples):
            for right in samples[i + 1 :]:
                horizontal = math.hypot(left.x - right.x, left.y - right.y)
                vertical = abs(left.z - right.z)
                if horizontal < safety_distance_m and vertical < vertical_separation_m:
                    pair = tuple(sorted((left.aircraft_id, right.aircraft_id)))
                    pairs.add(pair)
                    involved.update(pair)
                    sample_count += 1
    return AircraftConflictReport(len(pairs), sample_count, pairs, involved)


def conflicts_with_accepted(
    candidate: AircraftTrajectory,
    accepted: list[AircraftTrajectory],
    safety_distance_m: float,
    vertical_separation_m: float,
    time_step: float,
) -> AircraftConflictReport:
    buckets = build_conflict_buckets(accepted, time_step)
    return conflicts_with_buckets(
        candidate,
        buckets,
        safety_distance_m,
        vertical_separation_m,
        time_step,
    )


def build_conflict_buckets(
    trajectories: list[AircraftTrajectory],
    time_step: float,
) -> ConflictBuckets:
    buckets: ConflictBuckets = defaultdict(dict)
    for trajectory in trajectories:
        add_trajectory_to_buckets(buckets, trajectory, time_step)
    return buckets


def add_trajectory_to_buckets(
    buckets: ConflictBuckets,
    trajectory: AircraftTrajectory,
    time_step: float,
) -> None:
    for sample in trajectory.samples:
        bucket = int(round(sample.time_s / time_step))
        buckets[bucket].setdefault(trajectory.mission.id, sample)


def conflicts_with_buckets(
    candidate: AircraftTrajectory,
    buckets: ConflictBuckets,
    safety_distance_m: float,
    vertical_separation_m: float,
    time_step: float,
) -> AircraftConflictReport:
    pairs: set[tuple[int, int]] = set()
    involved: set[int] = set()
    sample_count = 0
    seen_candidate_buckets: set[int] = set()
    for sample in candidate.samples:
        bucket = int(round(sample.time_s / time_step))
        if bucket in seen_candidate_buckets:
            continue
        seen_candidate_buckets.add(bucket)
        for other in buckets.get(bucket, {}).values():
            horizontal = math.hypot(sample.x - other.x, sample.y - other.y)
            vertical = abs(sample.z - other.z)
            if horizontal < safety_distance_m and vertical < vertical_separation_m:
                pair = tuple(sorted((sample.aircraft_id, other.aircraft_id)))
                pairs.add(pair)
                involved.update(pair)
                sample_count += 1
    return AircraftConflictReport(len(pairs), sample_count, pairs, involved)
