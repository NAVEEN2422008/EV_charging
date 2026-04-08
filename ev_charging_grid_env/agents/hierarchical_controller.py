"""Hierarchical control scaffolding for multi-level coordination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class HighLevelIntent:
    """High-level objectives emitted by a top-level policy."""

    prioritize_emergency: bool
    green_mode: bool
    congestion_relief: bool


class HierarchicalCoordinator:
    """Maps high-level intent into coordinator action templates."""

    def plan_intent(self, observation: dict[str, Any]) -> HighLevelIntent:
        emergency_count = float(observation["arrivals_summary"][1])
        avg_queue = float(observation["queue_lengths"].mean())
        solar_flags = observation["station_features"][:, 3]
        return HighLevelIntent(
            prioritize_emergency=emergency_count > 0,
            green_mode=float(solar_flags.mean()) > 0.3,
            congestion_relief=avg_queue > 6.0,
        )

    def to_coordinator_action(self, intent: HighLevelIntent, num_stations: int) -> dict[str, Any]:
        # Baseline intent-to-action mapping; can be swapped with learned controller.
        deltas = [1] * num_stations
        if intent.congestion_relief:
            deltas = [2] * num_stations
        if intent.green_mode:
            deltas[0] = 0
        return {"price_deltas": deltas, "emergency_target_station": 0 if intent.prioritize_emergency else num_stations}
