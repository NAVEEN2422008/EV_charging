"""Actor-critic networks for centralized and multi-agent training."""

from __future__ import annotations

import torch
from torch import nn


class MLP(nn.Module):
    """Small MLP utility block."""

    def __init__(self, in_dim: int, hidden_dim: int, out_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, out_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class CentralizedActorCritic(nn.Module):
    """Centralized actor critic with factorized action heads."""

    def __init__(self, obs_dim: int, num_stations: int, hidden_dim: int = 256) -> None:
        super().__init__()
        self.num_stations = num_stations
        self.backbone = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
        )
        self.price_head = nn.Linear(hidden_dim, num_stations * 3)
        self.emergency_head = nn.Linear(hidden_dim, num_stations + 1)
        self.station_head = nn.Linear(hidden_dim, num_stations * 4)
        self.value_head = nn.Linear(hidden_dim, 1)

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        h = self.backbone(obs)
        price_logits = self.price_head(h).view(-1, self.num_stations, 3)
        emergency_logits = self.emergency_head(h)
        station_logits = self.station_head(h).view(-1, self.num_stations, 4)
        value = self.value_head(h).squeeze(-1)
        return price_logits, emergency_logits, station_logits, value


class MAPPOStationPolicy(nn.Module):
    """Shared station actor for MAPPO; critic can use centralized context."""

    def __init__(self, local_obs_dim: int, global_obs_dim: int, hidden_dim: int = 128) -> None:
        super().__init__()
        self.actor = MLP(local_obs_dim, hidden_dim, 4)
        self.critic = MLP(global_obs_dim, hidden_dim, 1)

    def act_logits(self, local_obs: torch.Tensor) -> torch.Tensor:
        return self.actor(local_obs)

    def value(self, global_obs: torch.Tensor) -> torch.Tensor:
        return self.critic(global_obs).squeeze(-1)
