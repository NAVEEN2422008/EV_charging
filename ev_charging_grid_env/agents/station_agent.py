"""Station baseline agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class HeuristicStationAgent:
    """Heuristic local policy for station-level queue actions."""

    short_queue_threshold: int = 6

    def act(
        self,
        station_index: int,
        observation: dict[str, Any],
        coordinator_action: dict[str, Any],
    ) -> int:
        station_features = np.asarray(observation["station_features"], dtype=np.float32)
        queue_len = int(station_features[station_index, 0])
        charging_count = int(station_features[station_index, 1])
        max_slots_approx = max(charging_count + 1, 4)
        has_capacity = charging_count < max_slots_approx

        emergency_arrivals = int(observation["arrivals_summary"][1])
        if emergency_arrivals > 0 and has_capacity:
            return 2  # emergency-first accept
        if queue_len <= self.short_queue_threshold and has_capacity:
            return 1  # accept

        suggested = int(coordinator_action.get("emergency_target_station", station_index))
        if suggested != station_index and queue_len > self.short_queue_threshold:
            return 3  # redirect
        return 0  # keep/defer


@dataclass
class RandomStationAgent:
    """Random station action policy baseline."""

    rng: np.random.Generator | None = None

    def __post_init__(self) -> None:
        if self.rng is None:
            self.rng = np.random.default_rng()

    def act(self, *_: Any, **__: Any) -> int:
        assert self.rng is not None
        return int(self.rng.integers(low=0, high=4))
