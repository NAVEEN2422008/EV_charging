"""Lightweight multi-agent communication primitives."""

from __future__ import annotations

from typing import Any

import numpy as np


def build_station_tokens(observation: dict[str, Any]) -> np.ndarray:
    """Compress station status into compact tokens for message passing."""
    features = np.asarray(observation["station_features"], dtype=np.float32)
    queue = features[:, 0]
    solar = features[:, 3]
    price = features[:, 6]
    token = np.stack([queue, solar, price], axis=1)
    return token.astype(np.float32)


def coordinator_broadcast(observation: dict[str, Any], emergency_target_station: int) -> dict[str, Any]:
    """Broadcast low-bandwidth hint vector to station agents."""
    queue_lengths = np.asarray(observation["queue_lengths"], dtype=np.int64)
    return {
        "emergency_target_station": int(emergency_target_station),
        "high_pressure_station": int(np.argmax(queue_lengths)),
    }
