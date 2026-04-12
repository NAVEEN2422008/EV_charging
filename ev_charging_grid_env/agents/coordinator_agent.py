"""Simple coordinator baseline for inference and smoke tests."""

from __future__ import annotations

from typing import Any

import numpy as np


class CoordinatorAgent:
    """Balances queue pressure against solar availability."""

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        station_features = np.asarray(observation["station_features"], dtype=np.float32)
        queue_lengths = station_features[:, 0]
        solar_now = station_features[:, 2]
        mean_queue = float(np.mean(queue_lengths)) if len(queue_lengths) else 0.0

        price_deltas: list[int] = []
        for queue_len, solar_kw in zip(queue_lengths, solar_now):
            if queue_len > mean_queue + 2:
                price_deltas.append(2)
            elif solar_kw > float(np.mean(solar_now)) and queue_len <= mean_queue:
                price_deltas.append(-1)
            else:
                price_deltas.append(0)

        emergency_target = int(np.argmax(solar_now - queue_lengths))
        return {
            "price_deltas": price_deltas,
            "emergency_target_station": emergency_target,
        }

