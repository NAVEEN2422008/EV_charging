"""Policy factory for dashboard control panel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ev_charging_grid_env.agents.coordinator_agent import HeuristicCoordinatorAgent, RandomCoordinatorAgent
from ev_charging_grid_env.agents.station_agent import HeuristicStationAgent, RandomStationAgent


@dataclass
class PolicyBundle:
    coordinator: Any
    stations: list[Any]
    label: str
    note: str = ""


class PPOCoordinatorAdapter:
    """Adapter for PPO/MAPPO coordinator."""

    def __init__(self, num_stations: int, checkpoint_path: str | None = None) -> None:
        self.num_stations = num_stations
        self.checkpoint_path = checkpoint_path
        self.rng = np.random.default_rng(123)
        self.available = bool(checkpoint_path and Path(checkpoint_path).exists())

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        """Stochastic fallback policy for coordinator."""
        return {
            "price_deltas": self.rng.integers(0, 3, size=self.num_stations, dtype=np.int64),
            "emergency_target_station": int(self.rng.integers(0, self.num_stations + 1)),
        }


class PPOStationAdapter:
    """Adapter for PPO/MAPPO station."""

    def __init__(self, checkpoint_path: str | None = None) -> None:
        self.checkpoint_path = checkpoint_path
        self.rng = np.random.default_rng(456)
        self.available = bool(checkpoint_path and Path(checkpoint_path).exists())

    def act(self, station_index: int, observation: dict[str, Any], coordinator_action: dict[str, Any]) -> int:
        """Stochastic fallback policy for station."""
        return int(self.rng.integers(0, 4))


def build_policy_bundle(policy_name: str, num_stations: int, checkpoint_path: str | None = None) -> PolicyBundle:
    """Return coordinator + station policies based on UI selection."""
    if policy_name == "Random":
        return PolicyBundle(RandomCoordinatorAgent(num_stations), [RandomStationAgent() for _ in range(num_stations)], "Random")
    if policy_name == "Heuristic":
        return PolicyBundle(HeuristicCoordinatorAgent(), [HeuristicStationAgent() for _ in range(num_stations)], "Heuristic")
    if policy_name in {"PPO", "MAPPO"}:
        coordinator = PPOCoordinatorAdapter(num_stations=num_stations, checkpoint_path=checkpoint_path)
        stations = [PPOStationAdapter(checkpoint_path=checkpoint_path) for _ in range(num_stations)]
        note = (
            "Checkpoint path found; model inference is not wired yet, using stochastic fallback policy."
            if coordinator.available
            else "Checkpoint missing, using stochastic fallback policy."
        )
        return PolicyBundle(coordinator, stations, policy_name, note=note)
    return PolicyBundle(RandomCoordinatorAgent(num_stations), [RandomStationAgent() for _ in range(num_stations)], "Random")
