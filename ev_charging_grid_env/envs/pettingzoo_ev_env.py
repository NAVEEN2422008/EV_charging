"""PettingZoo AEC-compatible wrapper for EV charging grid simulation."""

from __future__ import annotations

from typing import Any

import numpy as np
from gymnasium import spaces
from pettingzoo import AECEnv

from ev_charging_grid_env.envs.communication import coordinator_broadcast
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.envs.spaces import (
    build_coordinator_observation_space,
    build_station_action_space,
    build_station_observation_space,
)


class AgentSelector:
    """Simple agent selector for maintaining turn order in AEC environments.
    
    Mimics the old pettingzoo.utils.agent_selector.AgentSelector API for
    compatibility with pettingzoo 1.24.3+.
    """

    def __init__(self, agents: list[str]) -> None:
        """Initialize agent selector with a list of agents.
        
        Args:
            agents: List of agent names in order.
        """
        self.agents = agents
        self.agent_index = 0

    def reset(self) -> str:
        """Reset to the first agent.
        
        Returns:
            The first agent name.
        """
        self.agent_index = 0
        return self.agents[0] if self.agents else None

    def next(self) -> str:
        """Move to the next agent in the turn order.
        
        Returns:
            The next agent name, wrapping around if needed.
        """
        if not self.agents:
            return None
        self.agent_index = (self.agent_index + 1) % len(self.agents)
        return self.agents[self.agent_index]

    def is_last(self) -> bool:
        """Check if the current agent is the last in the turn order.
        
        Returns:
            True if current agent is the last, False otherwise.
        """
        return self.agent_index == len(self.agents) - 1

    def is_first(self) -> bool:
        """Check if the current agent is the first in the turn order.
        
        Returns:
            True if current agent is the first, False otherwise.
        """
        return self.agent_index == 0


class PettingZooEVChargingEnv(AECEnv):
    """AEC interface with one coordinator and 10 station agents."""

    metadata = {"name": "MultiAgentEVChargingGridEnv-v0-pz"}

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.gym_env = MultiAgentEVChargingGridEnv(config=config)
        self.possible_agents = ["coordinator"] + [f"station_{i}" for i in range(self.gym_env.num_stations)]
        self.agent_name_mapping = {name: idx for idx, name in enumerate(self.possible_agents)}
        self._agent_selector = AgentSelector(self.possible_agents)
        self.agents = self.possible_agents[:]
        self.rewards = {agent: 0.0 for agent in self.agents}
        self._cumulative_rewards = {agent: 0.0 for agent in self.agents}
        self.terminations = {agent: False for agent in self.agents}
        self.truncations = {agent: False for agent in self.agents}
        self.infos = {agent: {} for agent in self.agents}
        self._actions: dict[str, Any] = {}
        self._last_obs: dict[str, Any] | None = None
        self.agent_selection = self._agent_selector.reset()
        self._coordinator_obs_space = build_coordinator_observation_space(self.gym_env.num_stations)
        self._station_obs_space = build_station_observation_space(self.gym_env.num_stations)
        self._station_action_space = build_station_action_space()

    def observation_space(self, agent: str) -> spaces.Space:
        return self._coordinator_obs_space if agent == "coordinator" else self._station_obs_space

    def action_space(self, agent: str) -> spaces.Space:
        if agent == "coordinator":
            return self.gym_env.action_space["coordinator_action"]
        return self._station_action_space

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> dict[str, Any]:
        obs, _ = self.gym_env.reset(seed=seed, options=options)
        self._last_obs = obs
        self.agents = self.possible_agents[:]
        self.rewards = {agent: 0.0 for agent in self.agents}
        self._cumulative_rewards = {agent: 0.0 for agent in self.agents}
        self.terminations = {agent: False for agent in self.agents}
        self.truncations = {agent: False for agent in self.agents}
        self.infos = {agent: {} for agent in self.agents}
        self._actions = {}
        self._agent_selector = AgentSelector(self.agents)
        self.agent_selection = self._agent_selector.reset()
        
        # Return observations for all agents (required by AEC standard)
        return {agent: self.observe(agent) for agent in self.agents}

    def observe(self, agent: str) -> dict[str, Any]:
        assert self._last_obs is not None
        if agent == "coordinator":
            return {
                **self._last_obs,
                "action_mask": np.ones(self.action_space("coordinator")["emergency_target_station"].n, dtype=np.int8),
            }
        idx = int(agent.split("_")[1])
        station_features = np.asarray(self._last_obs["station_features"], dtype=np.float32)
        local = np.concatenate(
            [station_features[idx], np.array([float(self._last_obs["weather"])], dtype=np.float32)], axis=0
        )
        time_context = np.asarray(self._last_obs["time_context"], dtype=np.float32)
        arrivals = np.asarray(self._last_obs["arrivals_summary"], dtype=np.float32)
        return {
            "local_features": local.astype(np.float32),
            "neighbor_queue_lengths": np.asarray(self._last_obs["queue_lengths"], dtype=np.int64),
            "global_context": np.asarray([time_context[0], time_context[1], arrivals[1]], dtype=np.float32),
            "action_mask": self._station_action_mask(idx),
        }

    def step(self, action: Any) -> None:
        agent = self.agent_selection
        if self.terminations.get(agent, False) or self.truncations.get(agent, False):
            self._was_dead_step(action)
            return
        for ag in self.agents:
            self.rewards[ag] = 0.0
        self._actions[agent] = action
        if self._agent_selector.is_last():
            # Get coordinator action or provide default
            coord = self._actions.get("coordinator")
            if coord is None:
                coord = {
                    "price_deltas": np.ones(self.gym_env.num_stations, dtype=np.int64),
                    "emergency_target_station": 0,
                }

            # Ensure coordinator action is properly formatted
            if not isinstance(coord, dict) or "price_deltas" not in coord or "emergency_target_station" not in coord:
                raise ValueError(f"Coordinator action must be dict with 'price_deltas' and 'emergency_target_station', got {coord}")
            
            station_actions = [
                int(self._actions.get(f"station_{i}", 0)) for i in range(self.gym_env.num_stations)
            ]
            next_obs, reward, terminated, truncated, info = self.gym_env.step(
                {"coordinator_action": coord, "station_actions": station_actions}
            )
            self._last_obs = next_obs
            broadcast = coordinator_broadcast(next_obs, int(coord.get("emergency_target_station", self.gym_env.num_stations)))
            for ag in self.agents:
                self.rewards[ag] = float(reward / max(1, len(self.agents)))
                self._cumulative_rewards[ag] += self.rewards[ag]
                self.terminations[ag] = terminated
                self.truncations[ag] = truncated
                self.infos[ag] = {"shared_info": info, "broadcast": broadcast}
            self._actions = {}
        self.agent_selection = self._agent_selector.next()

    def _station_action_mask(self, station_idx: int) -> np.ndarray:
        """Legal station action mask: [hold, accept_fifo, accept_emergency, redirect]."""
        station = self.gym_env.episode_state.stations[station_idx]
        has_queue = 1 if len(station.queue) > 0 else 0
        has_emergency = 1 if any(vehicle.is_emergency for vehicle in station.queue) else 0
        has_capacity = 1 if len(station.charging_vehicles) < station.max_slots and station.outage_time_left <= 0 else 0
        return np.asarray(
            [
                1,
                1 if (has_queue and has_capacity) else 0,
                1 if (has_queue and has_capacity and has_emergency) else 0,
                1 if has_queue else 0,
            ],
            dtype=np.int8,
        )

