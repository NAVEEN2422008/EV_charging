"""Rollout storage and GAE computation."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class RolloutBuffer:
    """Simple on-policy rollout buffer."""

    gamma: float
    gae_lambda: float
    observations: list[np.ndarray] = field(default_factory=list)
    actions: list[np.ndarray] = field(default_factory=list)
    log_probs: list[float] = field(default_factory=list)
    rewards: list[float] = field(default_factory=list)
    dones: list[bool] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    returns: list[float] = field(default_factory=list)
    advantages: list[float] = field(default_factory=list)

    def clear(self) -> None:
        self.observations.clear()
        self.actions.clear()
        self.log_probs.clear()
        self.rewards.clear()
        self.dones.clear()
        self.values.clear()
        self.returns.clear()
        self.advantages.clear()

    def compute_returns_and_advantages(self, last_value: float = 0.0) -> None:
        self.advantages = [0.0 for _ in self.rewards]
        gae = 0.0
        for t in reversed(range(len(self.rewards))):
            next_value = last_value if t == len(self.rewards) - 1 else self.values[t + 1]
            non_terminal = 0.0 if self.dones[t] else 1.0
            delta = self.rewards[t] + self.gamma * next_value * non_terminal - self.values[t]
            gae = delta + self.gamma * self.gae_lambda * non_terminal * gae
            self.advantages[t] = gae
        self.returns = [adv + val for adv, val in zip(self.advantages, self.values, strict=True)]

    def as_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        return (
            np.asarray(self.observations, dtype=np.float32),
            np.asarray(self.actions, dtype=np.int64),
            np.asarray(self.log_probs, dtype=np.float32),
            np.asarray(self.returns, dtype=np.float32),
            np.asarray(self.advantages, dtype=np.float32),
        )
