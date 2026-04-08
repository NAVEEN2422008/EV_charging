"""Simulation integration layer for dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import yaml

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv


@dataclass
class SimulationState:
    env: MultiAgentEVChargingGridEnv
    observation: dict[str, Any]
    done: bool = False
    history: list[dict[str, float]] = field(default_factory=list)
    latest_info: dict[str, Any] = field(default_factory=dict)

    def step_with_policies(self, coordinator: Any, stations: list[Any]) -> None:
        if self.done:
            return
        coordinator_action = coordinator.act(self.observation)
        station_actions = [agent.act(i, self.observation, coordinator_action) for i, agent in enumerate(stations)]
        action = {"coordinator_action": coordinator_action, "station_actions": station_actions}
        next_obs, reward, terminated, truncated, info = self.env.step(action)
        self.done = bool(terminated or truncated)
        self.observation = next_obs
        self.latest_info = info
        stats = info.get("episode_stats", {})
        self.history.append(
            {
                "timestep": float(self.env.episode_state.time_step),
                "reward": float(reward),
                "total_reward": float(stats.get("total_reward", 0.0)),
                "avg_wait": float(stats.get("total_wait_time", 0.0) / max(1.0, stats.get("vehicles_seen", 1.0))),
                "solar_util_pct": 100.0
                * float(stats.get("solar_energy_kwh", 0.0))
                / max(1e-6, float(stats.get("total_energy_kwh", 0.0))),
                "grid_overload_events": float(stats.get("grid_overload_events", 0.0)),
                "emergency_served": float(stats.get("emergency_served", 0.0)),
                "emergency_missed": float(stats.get("emergency_missed", 0.0)),
                "travel_distance_km": float(stats.get("travel_distance_km", 0.0)),
                "grid_kw_used": float(self.env.episode_state.grid.total_grid_kw_used),
                "grid_kw_limit": float(self.env.episode_state.grid.global_limit_kw),
            }
        )

    def history_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.history)


def load_default_config(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_simulation(config: dict[str, Any], seed: int = 42) -> SimulationState:
    env = MultiAgentEVChargingGridEnv(config=config)
    obs, _ = env.reset(seed=seed)
    return SimulationState(env=env, observation=obs)
