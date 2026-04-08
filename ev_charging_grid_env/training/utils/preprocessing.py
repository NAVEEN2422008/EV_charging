"""Observation preprocessing and normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


def flatten_observation(observation: dict[str, Any]) -> np.ndarray:
    """Flatten dict observation to a single float32 vector."""
    station_features = np.asarray(observation["station_features"], dtype=np.float32).reshape(-1)
    arrivals = np.asarray(observation["arrivals_summary"], dtype=np.float32).reshape(-1)
    time_context = np.asarray(observation["time_context"], dtype=np.float32).reshape(-1)
    weather = np.asarray([float(observation["weather"])], dtype=np.float32)
    queues = np.asarray(observation["queue_lengths"], dtype=np.float32).reshape(-1)
    return np.concatenate([station_features, arrivals, time_context, weather, queues], axis=0).astype(np.float32)


@dataclass
class RunningNorm:
    """Welford online normalizer for stable feature scaling."""

    epsilon: float = 1e-6

    def __post_init__(self) -> None:
        self.count: float = self.epsilon
        self.mean: np.ndarray | None = None
        self.var: np.ndarray | None = None

    def update(self, x: np.ndarray) -> None:
        x = x.astype(np.float32)
        if self.mean is None or self.var is None:
            self.mean = np.zeros_like(x, dtype=np.float32)
            self.var = np.ones_like(x, dtype=np.float32)
        self.count += 1.0
        delta = x - self.mean
        self.mean += delta / self.count
        delta2 = x - self.mean
        self.var += delta * delta2

    def normalize(self, x: np.ndarray) -> np.ndarray:
        if self.mean is None or self.var is None:
            return x
        std = np.sqrt(np.maximum(self.var / max(1.0, self.count - 1.0), self.epsilon))
        return (x - self.mean) / std
