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


class PPOPolicyAdapter:
    """Fallback adapter for trained PPO checkpoints."""

    def __init__(self, num_stations: int, checkpoint_path: str | None = None) -> None:
        self.num_stations = num_stations
        self.checkpoint_path = checkpoint_path
        self.rng = np.random.default_rng(123)
        self.available = bool(checkpoint_path and Path(checkpoint_path).exists())

    def coordinator_action(self, _: dict[str, Any]) -> dict[str, Any]:
        # Baseline checkpoint adapter path; if unavailable, use stochastic policy.
        return {
            "price_deltas": self.rng.integers(0, 3, size=self.num_stations, dtype=np.int64),
            "emergency_target_station": int(self.rng.integers(0, self.num_stations + 1)),
        }

    def station_action(self, *_: Any, **__: Any) -> int:
        return int(self.rng.integers(0, 4))


def build_policy_bundle(policy_name: str, num_stations: int, checkpoint_path: str | None = None) -> PolicyBundle:
    """Return coordinator + station policies based on UI selection."""
    if policy_name == "Random":
        return PolicyBundle(RandomCoordinatorAgent(num_stations), [RandomStationAgent() for _ in range(num_stations)], "Random")
    if policy_name == "Heuristic":
        return PolicyBundle(HeuristicCoordinatorAgent(), [HeuristicStationAgent() for _ in range(num_stations)], "Heuristic")
    if policy_name in {"PPO", "MAPPO"}:
        adapter = PPOPolicyAdapter(num_stations=num_stations, checkpoint_path=checkpoint_path)
        coordinator = type("CoordinatorAdapter", (), {"act": adapter.coordinator_action})()
        stations = [type("StationAdapter", (), {"act": adapter.station_action})() for _ in range(num_stations)]
        note = (
            "Checkpoint path found; model inference is not wired yet, using stochastic fallback policy."
            if adapter.available
            else "Checkpoint missing, using stochastic fallback policy."
        )
        return PolicyBundle(coordinator, stations, policy_name, note=note)
    return PolicyBundle(RandomCoordinatorAgent(num_stations), [RandomStationAgent() for _ in range(num_stations)], "Random")
