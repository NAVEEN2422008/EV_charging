"""Action encoding/decoding and masking utilities."""

from __future__ import annotations

from typing import Any

import numpy as np


def decode_joint_action(action_vec: np.ndarray, num_stations: int) -> dict[str, Any]:
    """Decode flat action vector into env joint action dict."""
    action_vec = np.asarray(action_vec, dtype=np.int64).reshape(-1)
    price_deltas = np.clip(action_vec[:num_stations], 0, 2)
    emergency_target = int(np.clip(action_vec[num_stations], 0, num_stations))
    station_actions = np.clip(action_vec[num_stations + 1 : num_stations + 1 + num_stations], 0, 3)
    return {
        "coordinator_action": {
            "price_deltas": price_deltas,
            "emergency_target_station": emergency_target,
        },
        "station_actions": station_actions,
    }


def build_station_action_mask(local_observation: dict[str, Any]) -> np.ndarray:
    """Build legal-action mask for station policy heads."""
    if "action_mask" in local_observation:
        return np.asarray(local_observation["action_mask"], dtype=np.float32)
    return np.ones(4, dtype=np.float32)
