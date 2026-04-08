"""Coordinator baseline agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class HeuristicCoordinatorAgent:
    """Rule-based coordinator that adjusts prices and emergency routing hints."""

    overload_queue_threshold: int = 8
    underutilized_queue_threshold: int = 3

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        station_features = np.asarray(observation["station_features"], dtype=np.float32)
        queue_lengths = station_features[:, 0]
        has_solar = station_features[:, 3]
        charging_counts = station_features[:, 1]

        price_deltas = np.ones(station_features.shape[0], dtype=np.int64)
        for idx in range(station_features.shape[0]):
            if queue_lengths[idx] >= self.overload_queue_threshold:
                price_deltas[idx] = 2  # +1 delta bucket
            elif queue_lengths[idx] <= self.underutilized_queue_threshold and has_solar[idx] > 0.5:
                price_deltas[idx] = 0  # -1 delta bucket

        # Route emergency to a station with free slots, high solar, and short queue.
        score = (has_solar * 3.0) - queue_lengths - (charging_counts * 0.3)
        emergency_target = int(np.argmax(score))
        return {
            "price_deltas": price_deltas,
            "emergency_target_station": emergency_target,
        }


@dataclass
class RandomCoordinatorAgent:
    """Random coordinator baseline for sanity checks."""

    num_stations: int
    rng: np.random.Generator | None = None

    def __post_init__(self) -> None:
        if self.rng is None:
            self.rng = np.random.default_rng()

    def act(self, _: dict[str, Any]) -> dict[str, Any]:
        assert self.rng is not None
        return {
            "price_deltas": self.rng.integers(low=0, high=3, size=self.num_stations, dtype=np.int64),
            "emergency_target_station": int(self.rng.integers(low=0, high=self.num_stations + 1)),
        }


class CoordinatorWithCommunication(HeuristicCoordinatorAgent):
    """Heuristic coordinator that also emits compact broadcast hints."""

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        action = super().act(observation)
        action["broadcast_priority"] = int(observation["arrivals_summary"][1] > 0)
        return action
