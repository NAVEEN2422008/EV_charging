"""Centralized Gym/OpenEnv wrapper backed by shared simulation core."""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np

from ev_charging_grid_env.envs.dynamics import (
    apply_coordinator_action,
    apply_station_actions,
    enqueue_arrivals,
    generate_arrivals,
    initialize_episode,
    progress_step,
    sample_weather,
)
from ev_charging_grid_env.envs.reward_functions import compute_step_reward
from ev_charging_grid_env.envs.spaces import build_action_space, build_observation_space
from ev_charging_grid_env.envs.task_generator import TaskConfig, generate_task

WEATHER_TO_INDEX = {"sunny": 0, "cloudy": 1, "rainy": 2}


class MultiAgentEVChargingGridEnv(gym.Env[dict[str, Any], dict[str, Any]]):
    """Centralized joint-action environment for multi-agent coordination."""

    metadata = {"render_modes": ["human"], "render_fps": 4}

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.config = config or {}
        self.task: TaskConfig = generate_task(self.config)
        self.num_stations = len(self.task.station_configs)
        self.episode_state = initialize_episode(self.task)
        self.last_arrivals = []
        self.episode_stats: dict[str, float] = {}
        self.np_random = np.random.default_rng()
        self.observation_space = build_observation_space(self.num_stations)
        self.action_space = build_action_space(self.num_stations)

    @property
    def task_id(self) -> str:
        return self.task.scenario_name

    @property
    def current_step(self) -> int:
        return int(self.episode_state.time_step)

    def state(self) -> dict[str, Any]:
        return self._build_observation()

    def _metrics_snapshot(self) -> dict[str, Any]:
        return {
            "task_id": self.task.scenario_name,
            "current_step": int(self.episode_state.time_step),
            "vehicles_served": float(self.episode_stats.get("vehicles_seen", 0.0)),
        }

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        super().reset(seed=seed)
        if seed is not None:
            self.np_random = np.random.default_rng(seed)
            # Explicitly seed action space for deterministic sampling
            self.action_space.seed(seed)
        if options:
            self.config = {**self.config, **options}
            self.task = generate_task(self.config)
            self.num_stations = len(self.task.station_configs)
            self.observation_space = build_observation_space(self.num_stations)
            self.action_space = build_action_space(self.num_stations)
            # Re-seed action space after recreation
            if seed is not None:
                self.action_space.seed(seed)
        self.episode_state = initialize_episode(self.task)
        self.episode_state.weather = sample_weather(self.task, self.np_random)
        self.last_arrivals = []
        self.episode_stats = {
            "vehicles_seen": 0.0,
            "total_wait_time": 0.0,
            "solar_energy_kwh": 0.0,
            "total_energy_kwh": 0.0,
            "emergency_served": 0.0,
            "emergency_missed": 0.0,
            "total_reward": 0.0,
            "travel_distance_km": 0.0,
            "grid_overload_events": 0.0,
        }
        return self._build_observation(), {"env_name": "MultiAgentEVChargingGridEnv-v0"}

    def step(self, action: dict[str, Any]) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        # Comprehensive action validation
        if not isinstance(action, dict):
            raise TypeError(f"action must be dict, got {type(action)}")
        
        if "coordinator_action" not in action or "station_actions" not in action:
            raise ValueError(
                "action must include 'coordinator_action' and 'station_actions', "
                f"got keys: {list(action.keys())}"
            )
        
        coordinator_action = action["coordinator_action"]
        if not isinstance(coordinator_action, dict):
            raise TypeError(f"coordinator_action must be dict, got {type(coordinator_action)}")
        
        if "price_deltas" not in coordinator_action or "emergency_target_station" not in coordinator_action:
            raise ValueError(
                "coordinator_action must include 'price_deltas' and 'emergency_target_station', "
                f"got keys: {list(coordinator_action.keys())}"
            )
        
        # Validate price_deltas shape
        price_deltas = np.asarray(coordinator_action["price_deltas"], dtype=np.int64)
        if price_deltas.ndim != 1 or price_deltas.shape[0] != self.num_stations:
            raise ValueError(
                f"price_deltas must be 1D array of length {self.num_stations}, "
                f"got shape {price_deltas.shape}"
            )
        
        # Validate emergency_target_station
        emergency_target = int(coordinator_action["emergency_target_station"])
        if not (0 <= emergency_target <= self.num_stations):
            raise ValueError(
                f"emergency_target_station must be in [0, {self.num_stations}], "
                f"got {emergency_target}"
            )
        
        # Validate station_actions shape
        station_actions = np.asarray(action["station_actions"], dtype=np.int64)
        if station_actions.ndim != 1 or station_actions.shape[0] != self.num_stations:
            raise ValueError(
                f"station_actions must be 1D array of length {self.num_stations}, "
                f"got shape {station_actions.shape}"
            )
        self.episode_state.weather = sample_weather(self.task, self.np_random)
        routing_hint = apply_coordinator_action(
            self.episode_state,
            coordinator_action,
            float(self.config.get("price_step", 0.02)),
            float(self.config.get("min_price_per_kwh", 0.1)),
            float(self.config.get("max_price_per_kwh", 1.0)),
        )
        arrivals = generate_arrivals(self.episode_state, self.task, self.np_random, routing_hint)
        self.last_arrivals = arrivals
        self.episode_stats["vehicles_seen"] += float(len(arrivals))
        self.episode_stats["travel_distance_km"] += enqueue_arrivals(
            self.episode_state, arrivals, self.task.station_distance_km
        )
        apply_station_actions(self.episode_state, station_actions, routing_hint)
        events = progress_step(
            self.episode_state,
            self.task,
            float(self.config.get("sim_minutes_per_step", 1.0)),
            float(self.config.get("fast_charge_kw", 120.0)),
            float(self.config.get("slow_charge_kw", 45.0)),
            self.np_random,
        )
        reward_state = {
            "mean_wait_time": self._mean_wait(),
            "total_grid_kw_used": self.episode_state.grid.total_grid_kw_used,
            "grid_limit_kw": self.episode_state.grid.global_limit_kw,
        }
        events["travel_distance_km"] = self.episode_stats["travel_distance_km"] / max(1.0, self.episode_stats["vehicles_seen"])
        reward = compute_step_reward(reward_state, events, self.config)
        self.episode_stats["total_reward"] += reward
        self.episode_stats["solar_energy_kwh"] += events["solar_kwh_used"]
        self.episode_stats["total_energy_kwh"] += events["solar_kwh_used"] + events["grid_kwh_used"]
        self.episode_stats["emergency_served"] += events["emergency_served"]
        self.episode_stats["emergency_missed"] += events["emergency_missed"]
        self.episode_stats["grid_overload_events"] = float(self.episode_state.grid.overload_events)
        self.episode_stats["total_wait_time"] += self._total_wait()
        terminated = False
        truncated = self.episode_state.time_step >= self.episode_state.episode_length
        info = {"events": events, "reward_components": reward_state, "episode_stats": self.episode_stats.copy()}
        
        # ──────────────────────────────────────────────────────────────────────────────
        # NUMERICAL STABILITY CHECKS (SAFETY LAYER)
        # ──────────────────────────────────────────────────────────────────────────────
        
        # Validate reward is finite
        if np.isnan(reward) or np.isinf(reward):
            reward = 0.0  # Clamp invalid rewards to 0
            info["reward_clipped"] = True
        else:
            reward = float(np.clip(reward, -1e6, 1e6))  # Hard clip to reasonable bounds
        
        # Validate observation values don't contain NaN/Inf
        obs = self._build_observation()
        for key, val in obs.items():
            if isinstance(val, np.ndarray):
                if np.any(np.isnan(val)) or np.any(np.isinf(val)):
                    obs[key] = np.nan_to_num(val, nan=0.0, posinf=1e6, neginf=-1e6)
                    info[f"{key}_cleaned"] = True
        
        return obs, float(reward), terminated, truncated, info

    def _mean_wait(self) -> float:
        waits = [v.wait_time for station in self.episode_state.stations for v in station.queue]
        return float(np.mean(waits)) if waits else 0.0

    def _total_wait(self) -> float:
        return float(sum(v.wait_time for station in self.episode_state.stations for v in station.queue))

    def _build_observation(self) -> dict[str, Any]:
        rows: list[list[float]] = []
        for station in self.episode_state.stations:
            rows.append(
                [
                    float(len(station.queue)),
                    float(len(station.charging_vehicles)),
                    float(np.mean([v.wait_time for v in station.queue]) if station.queue else 0.0),
                    1.0 if station.has_solar else 0.0,
                    float(station.solar_actual_kw),
                    float(max(0.0, station.grid_capacity_kw - station.grid_kw_used)),
                    float(station.dynamic_price),
                ]
            )
        n_normal = sum(1 for v in self.last_arrivals if not v.is_emergency)
        n_emergency = sum(1 for v in self.last_arrivals if v.is_emergency)
        required = sum(v.required_kwh for v in self.last_arrivals)
        angle = (2.0 * np.pi * (self.episode_state.time_step % 1440)) / 1440.0
        return {
            "station_features": np.asarray(rows, dtype=np.float32),
            "arrivals_summary": np.asarray([float(n_normal), float(n_emergency), float(required)], dtype=np.float32),
            "time_context": np.asarray([np.sin(angle), np.cos(angle)], dtype=np.float32),
            "weather": int(WEATHER_TO_INDEX.get(self.episode_state.weather, 0)),
            "queue_lengths": np.asarray([len(station.queue) for station in self.episode_state.stations], dtype=np.int64),
        }
