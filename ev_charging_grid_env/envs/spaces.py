"""Observation and action space definitions."""

from __future__ import annotations

from typing import Any, Dict, List

from gymnasium import spaces
import numpy as np
from pydantic import BaseModel


class Observation(BaseModel):
    """Pydantic model for environment observation."""
    station_features: List[List[float]]
    arrivals_summary: List[float]
    time_context: List[float]
    weather: int
    queue_lengths: List[int]


class Action(BaseModel):
    """Pydantic model for environment action."""
    coordinator_action: Dict[str, Any]
    station_actions: List[int]


def build_observation_space(num_stations: int, max_queue_observed: int = 200) -> spaces.Dict:
    """Build a global observation space for the EV charging environment."""
    return spaces.Dict(
        {
            "station_features": spaces.Box(
                low=0.0,
                high=np.inf,
                shape=(num_stations, 7),
                dtype=np.float32,
            ),
            "arrivals_summary": spaces.Box(
                low=0.0,
                high=np.inf,
                shape=(3,),
                dtype=np.float32,
            ),
            "time_context": spaces.Box(
                low=-1.0,
                high=1.0,
                shape=(2,),
                dtype=np.float32,
            ),
            "weather": spaces.Discrete(3),
            "queue_lengths": spaces.MultiDiscrete([max_queue_observed + 1] * num_stations),
        }
    )


def build_action_space(num_stations: int) -> spaces.Dict:
    """Build a joint action space with coordinator + per-station actions."""
    return spaces.Dict(
        {
            "coordinator_action": spaces.Dict(
                {
                    "price_deltas": spaces.MultiDiscrete([3] * num_stations),
                    "emergency_target_station": spaces.Discrete(num_stations + 1),
                }
            ),
            "station_actions": spaces.MultiDiscrete([4] * num_stations),
        }
    )


def build_coordinator_observation_space(num_stations: int) -> spaces.Dict:
    """Observation space used by the coordinator in PettingZoo mode."""
    base = build_observation_space(num_stations)
    return spaces.Dict({**base.spaces, "action_mask": spaces.MultiBinary(num_stations + 1)})


def build_station_observation_space(num_stations: int) -> spaces.Dict:
    """Station-level partial observation space for decentralized training."""
    return spaces.Dict(
        {
            "local_features": spaces.Box(low=0.0, high=np.inf, shape=(8,), dtype=np.float32),
            "neighbor_queue_lengths": spaces.MultiDiscrete([201] * num_stations),
            "global_context": spaces.Box(
                low=np.asarray([-1.0, -1.0, 0.0], dtype=np.float32),
                high=np.asarray([1.0, 1.0, np.inf], dtype=np.float32),
                dtype=np.float32,
            ),
            "action_mask": spaces.MultiBinary(4),
        }
    )


def build_station_action_space() -> spaces.Discrete:
    """Station action space: hold, accept FIFO, accept emergency first, redirect."""
    return spaces.Discrete(4)
