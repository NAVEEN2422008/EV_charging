"""OpenEnv-compatible multi-agent EV charging grid environment."""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from ev_charging_grid_env.config import TaskProfile, get_task_profile
from ev_charging_grid_env.envs.models import Station, Vehicle
from ev_charging_grid_env.graders import grade_episode

WEATHER_INDEX = {"sunny": 0, "cloudy": 1, "rainy": 2}
WEATHER_LABELS = ("sunny", "cloudy", "rainy")
WEATHER_SOLAR_MULTIPLIER = {"sunny": 1.0, "cloudy": 0.6, "rainy": 0.28}


class MultiAgentEVChargingGridEnv(gym.Env[dict[str, Any], dict[str, Any]]):
    """Centralized grid controller for EV charging and energy balancing."""

    metadata = {"render_modes": ["human"], "render_fps": 4}

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        config = config or {}
        self.config = dict(config)
        self.task_id = str(self.config.get("task_id", "medium"))
        self.task: TaskProfile = get_task_profile(self.task_id)
        self.num_stations = int(self.config.get("num_stations", 10))
        self.chargers_per_station = int(self.config.get("chargers_per_station", 4))
        self.step_minutes = float(self.config.get("step_minutes", 15.0))
        self.charger_power_kw = float(self.config.get("charger_power_kw", 30.0))
        self.base_solar_kw = float(self.config.get("base_solar_kw", 80.0))
        self.max_redirects_per_step = int(self.config.get("max_redirects_per_step", 3))
        self.max_arrivals_per_step = int(self.config.get("max_arrivals_per_step", 24))
        self.arrival_lambda_override = self.config.get("arrival_lambda")
        self.emergency_probability_override = self.config.get("emergency_probability")
        self.solar_multiplier_override = self.config.get("solar_multiplier")
        self.grid_capacity_kw_override = self.config.get("grid_capacity_kw")
        self.weather_mode = self.config.get("weather_mode")
        self.np_random = np.random.default_rng()

        self._build_spaces()
        self._init_state()

    def _build_spaces(self) -> None:
        self.action_space = spaces.Dict(
            {
                "coordinator_action": spaces.Dict(
                    {
                        "price_deltas": spaces.Box(
                            low=-3,
                            high=3,
                            shape=(self.num_stations,),
                            dtype=np.int64,
                        ),
                        "emergency_target_station": spaces.Discrete(self.num_stations),
                    }
                ),
                "station_actions": spaces.MultiDiscrete(np.full(self.num_stations, 4, dtype=np.int64)),
            }
        )
        self.observation_space = spaces.Dict(
            {
                "station_features": spaces.Box(
                    low=0.0,
                    high=500.0,
                    shape=(self.num_stations, 7),
                    dtype=np.float32,
                ),
                "queue_lengths": spaces.Box(
                    low=0,
                    high=500,
                    shape=(self.num_stations,),
                    dtype=np.int64,
                ),
                "time_context": spaces.Box(
                    low=-1.0,
                    high=1.0,
                    shape=(3,),
                    dtype=np.float32,
                ),
                "arrivals_summary": spaces.Box(
                    low=0.0,
                    high=1000.0,
                    shape=(3,),
                    dtype=np.float32,
                ),
                "weather": spaces.Discrete(3),
            }
        )

    def _init_state(self) -> None:
        self.stations = [
            Station(station_id=index, charger_count=self.chargers_per_station)
            for index in range(self.num_stations)
        ]
        self.current_step = 0
        self.last_weather = "sunny"
        self.last_arrivals_summary = np.zeros(3, dtype=np.float32)
        self.last_reward = 0.0
        self.last_observation: dict[str, Any] | None = None
        self.vehicle_sequence = 0
        self.metrics = {
            "vehicles_seen": 0.0,
            "vehicles_served": 0.0,
            "emergency_seen": 0.0,
            "emergency_served": 0.0,
            "solar_kwh_used": 0.0,
            "grid_kwh_used": 0.0,
            "grid_overload": 0.0,
            "grid_overload_events": 0.0,
            "queue_wait_accumulator": 0.0,
            "queue_observations": 0.0,
            "wait_timeout_departures": 0.0,
        }

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        super().reset(seed=seed)
        if seed is not None:
            self.np_random = np.random.default_rng(seed)

        options = options or {}
        merged = {**self.config, **options}
        self.task_id = str(merged.get("task_id", self.task_id))
        self.task = get_task_profile(self.task_id)
        self.num_stations = int(merged.get("num_stations", self.num_stations))
        self.chargers_per_station = int(merged.get("chargers_per_station", self.chargers_per_station))
        self.step_minutes = float(merged.get("step_minutes", self.step_minutes))
        self.charger_power_kw = float(merged.get("charger_power_kw", self.charger_power_kw))
        self.base_solar_kw = float(merged.get("base_solar_kw", self.base_solar_kw))
        self.max_redirects_per_step = int(merged.get("max_redirects_per_step", self.max_redirects_per_step))
        self.max_arrivals_per_step = int(merged.get("max_arrivals_per_step", self.max_arrivals_per_step))
        self.arrival_lambda_override = merged.get("arrival_lambda", self.arrival_lambda_override)
        self.emergency_probability_override = merged.get(
            "emergency_probability",
            self.emergency_probability_override,
        )
        self.solar_multiplier_override = merged.get("solar_multiplier", self.solar_multiplier_override)
        self.grid_capacity_kw_override = merged.get("grid_capacity_kw", self.grid_capacity_kw_override)
        self.weather_mode = merged.get("weather_mode", self.weather_mode)
        self._build_spaces()
        if seed is not None:
            self.action_space.seed(seed)

        self._init_state()
        self.last_weather = self._sample_weather()
        self._update_solar_generation()
        observation = self._build_observation()
        return observation, {
            "env_name": "MultiAgentEVChargingGridEnv",
            "task_id": self.task.id,
            "stations": self.num_stations,
            "episode_length": self.task.episode_length,
        }

    def step(
        self,
        action: dict[str, Any],
    ) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        coordinator_action, station_actions = self._validate_action(action)
        self.last_weather = self._sample_weather()
        self._update_solar_generation()
        self._apply_coordinator_action(coordinator_action)
        arrivals = self._generate_arrivals(coordinator_action)
        self._age_queues()
        self._apply_station_actions(station_actions)
        events = self._progress_charging()
        events["arrivals"] = float(len(arrivals))
        events["avg_wait_time"] = self._queue_wait_average()
        events["queue_length"] = float(sum(len(station.queue) for station in self.stations))
        reward = self._compute_reward(events)
        self.last_reward = reward
        self.current_step += 1

        observation = self._build_observation()
        truncated = self.current_step >= self.task.episode_length
        metrics = self._metrics_snapshot()
        info = {
            "events": events,
            "reward_components": {
                "vehicles_served": events["vehicles_served"],
                "solar_kwh_used": events["solar_kwh_used"],
                "emergency_served": events["emergency_served"],
                "avg_wait_time": events["avg_wait_time"],
                "queue_length": events["queue_length"],
                "grid_overload": events["grid_overload"],
            },
            "episode_metrics": metrics,
            "episode_stats": metrics,
            "score": grade_episode(metrics),
            "weather": self.last_weather,
            "task_id": self.task.id,
        }
        return observation, reward, False, truncated, info

    def state(self) -> dict[str, Any]:
        """Return the latest observation snapshot."""

        if self.last_observation is None:
            self.last_observation = self._build_observation()
        return self.last_observation

    def render(self) -> str:
        """Return a concise textual snapshot for debugging."""

        queue_total = int(sum(len(station.queue) for station in self.stations))
        return (
            f"step={self.current_step} task={self.task.id} weather={self.last_weather} "
            f"queue={queue_total} served={int(self.metrics['vehicles_served'])}"
        )

    def close(self) -> None:
        """Close the environment."""

        return None

    def _arrival_lambda(self) -> float:
        return float(
            self.arrival_lambda_override
            if self.arrival_lambda_override is not None
            else self.task.arrival_lambda
        )

    def _emergency_probability(self) -> float:
        return float(
            self.emergency_probability_override
            if self.emergency_probability_override is not None
            else self.task.emergency_probability
        )

    def _solar_multiplier(self) -> float:
        return float(
            self.solar_multiplier_override
            if self.solar_multiplier_override is not None
            else self.task.solar_multiplier
        )

    def _grid_capacity_kw(self) -> float:
        return float(
            self.grid_capacity_kw_override
            if self.grid_capacity_kw_override is not None
            else self.task.grid_capacity_kw
        )

    def _validate_action(self, action: dict[str, Any]) -> tuple[dict[str, Any], np.ndarray]:
        if not isinstance(action, dict):
            raise TypeError(f"action must be dict, got {type(action)}")
        if "coordinator_action" not in action or "station_actions" not in action:
            raise ValueError("action must contain coordinator_action and station_actions")

        coordinator_action = action["coordinator_action"]
        if not isinstance(coordinator_action, dict):
            raise TypeError("coordinator_action must be a dict")
        if "price_deltas" not in coordinator_action or "emergency_target_station" not in coordinator_action:
            raise ValueError("coordinator_action must contain price_deltas and emergency_target_station")

        price_deltas = np.asarray(coordinator_action["price_deltas"], dtype=np.int64)
        if price_deltas.shape != (self.num_stations,):
            raise ValueError(f"price_deltas must have shape ({self.num_stations},)")

        emergency_target = int(coordinator_action["emergency_target_station"])
        if not 0 <= emergency_target < self.num_stations:
            raise ValueError(f"emergency_target_station must be in [0, {self.num_stations - 1}]")

        station_actions = np.asarray(action["station_actions"], dtype=np.int64)
        if station_actions.shape != (self.num_stations,):
            raise ValueError(f"station_actions must have shape ({self.num_stations},)")
        if np.any((station_actions < 0) | (station_actions > 3)):
            raise ValueError("station_actions values must be in [0, 3]")

        return {
            "price_deltas": price_deltas.tolist(),
            "emergency_target_station": emergency_target,
        }, station_actions

    def _sample_weather(self) -> str:
        if self.weather_mode in WEATHER_LABELS:
            return str(self.weather_mode)
        weather_index = int(
            self.np_random.choice(
                np.arange(3),
                p=np.asarray(self.task.weather_weights, dtype=np.float64),
            )
        )
        return WEATHER_LABELS[weather_index]

    def _update_solar_generation(self) -> None:
        daylight_angle = np.pi * ((self.current_step % 96) / 96.0)
        daylight_factor = max(0.1, float(np.sin(daylight_angle)))
        weather_factor = WEATHER_SOLAR_MULTIPLIER[self.last_weather]
        for station in self.stations:
            local_noise = float(self.np_random.uniform(0.85, 1.15))
            station.solar_kw = (
                self.base_solar_kw
                * self._solar_multiplier()
                * daylight_factor
                * weather_factor
                * local_noise
            )
            station.grid_kw = 0.0
            station.served_this_step = 0
            station.emergency_served_this_step = 0
            station.redirected_this_step = 0

    def _apply_coordinator_action(self, coordinator_action: dict[str, Any]) -> None:
        for station, delta in zip(self.stations, coordinator_action["price_deltas"]):
            station.price_multiplier = float(np.clip(1.0 + (0.08 * int(delta)), 0.75, 1.35))

    def _generate_arrivals(self, coordinator_action: dict[str, Any]) -> list[Vehicle]:
        arrival_count = int(self.np_random.poisson(self._arrival_lambda()))
        arrival_count = max(0, min(self.max_arrivals_per_step, arrival_count))
        arrivals: list[Vehicle] = []
        emergency_target = int(coordinator_action["emergency_target_station"])

        for _ in range(arrival_count):
            emergency = bool(self.np_random.random() < self._emergency_probability())
            required_kwh = float(self.np_random.uniform(12.0, 60.0))
            battery_level = float(self.np_random.uniform(0.1, 0.8))
            max_wait_steps = int(self.np_random.integers(4, 14))
            green_preference = float(self.np_random.uniform(0.0, 1.0))

            if emergency:
                station_index = emergency_target
            else:
                scores = []
                for station in self.stations:
                    queue_pressure = len(station.queue) + len(station.charging)
                    solar_discount = station.solar_kw / max(1.0, self.base_solar_kw)
                    score = queue_pressure + station.price_multiplier - green_preference * solar_discount
                    scores.append(score)
                station_index = int(np.argmin(scores))

            vehicle = Vehicle(
                vehicle_id=f"veh-{self.vehicle_sequence}",
                arrival_step=self.current_step,
                required_kwh=required_kwh,
                remaining_kwh=required_kwh,
                battery_level=battery_level,
                max_wait_steps=max_wait_steps,
                green_preference=green_preference,
                emergency=emergency,
                assigned_station=station_index,
            )
            self.vehicle_sequence += 1
            self.stations[station_index].queue.append(vehicle)
            arrivals.append(vehicle)

        emergency_arrivals = sum(1 for vehicle in arrivals if vehicle.emergency)
        mean_energy = float(np.mean([vehicle.required_kwh for vehicle in arrivals])) if arrivals else 0.0
        self.last_arrivals_summary = np.asarray(
            [float(arrival_count), float(emergency_arrivals), mean_energy],
            dtype=np.float32,
        )
        self.metrics["vehicles_seen"] += float(arrival_count)
        self.metrics["emergency_seen"] += float(emergency_arrivals)
        return arrivals

    def _age_queues(self) -> None:
        for station in self.stations:
            retained: list[Vehicle] = []
            for vehicle in station.queue:
                vehicle.wait_steps += 1
                if vehicle.wait_steps > vehicle.max_wait_steps:
                    self.metrics["wait_timeout_departures"] += 1.0
                    continue
                retained.append(vehicle)
            station.queue = retained

    def _apply_station_actions(self, station_actions: np.ndarray) -> None:
        for station, action_code in zip(self.stations, station_actions.tolist()):
            if int(action_code) == 3:
                self._redirect_overflow(station)

        for station, action_code in zip(self.stations, station_actions.tolist()):
            if int(action_code) == 0:
                continue
            available_slots = max(0, station.charger_count - len(station.charging))
            if available_slots == 0 or not station.queue:
                continue

            if int(action_code) == 2:
                station.queue.sort(key=lambda vehicle: (not vehicle.emergency, -vehicle.wait_steps))
            else:
                station.queue.sort(key=lambda vehicle: (-vehicle.wait_steps, not vehicle.emergency))

            for _ in range(available_slots):
                if not station.queue:
                    break
                station.charging.append(station.queue.pop(0))

    def _redirect_overflow(self, station: Station) -> None:
        if len(station.queue) < station.charger_count + 2:
            return
        redirect_count = min(self.max_redirects_per_step, max(0, len(station.queue) - station.charger_count))
        for _ in range(redirect_count):
            if not station.queue:
                break
            vehicle = station.queue.pop()
            target = min(
                [item for item in self.stations if item.station_id != station.station_id],
                key=lambda item: len(item.queue) + len(item.charging),
            )
            vehicle.assigned_station = target.station_id
            target.queue.append(vehicle)
            station.redirected_this_step += 1

    def _progress_charging(self) -> dict[str, float]:
        step_hours = self.step_minutes / 60.0
        max_grid_kwh = self._grid_capacity_kw() * step_hours

        requested_per_station: list[float] = []
        solar_per_station: list[float] = []
        grid_request_per_station: list[float] = []

        for station in self.stations:
            requested_kwh = sum(
                min(vehicle.remaining_kwh, self.charger_power_kw * step_hours)
                for vehicle in station.charging
            )
            solar_available = station.solar_kw * step_hours
            solar_kwh = min(requested_kwh, solar_available)
            grid_kwh = max(0.0, requested_kwh - solar_kwh)
            requested_per_station.append(requested_kwh)
            solar_per_station.append(solar_kwh)
            grid_request_per_station.append(grid_kwh)

        total_grid_request = float(sum(grid_request_per_station))
        grid_scale = 1.0 if total_grid_request <= max_grid_kwh else max_grid_kwh / total_grid_request
        overload_kwh = max(0.0, total_grid_request - max_grid_kwh)

        vehicles_served = 0.0
        emergency_served = 0.0
        solar_used = 0.0
        grid_used = 0.0

        for station, requested_kwh, solar_kwh, grid_kwh in zip(
            self.stations,
            requested_per_station,
            solar_per_station,
            grid_request_per_station,
        ):
            actual_grid_kwh = grid_kwh * grid_scale
            station.grid_kw = actual_grid_kwh / step_hours if step_hours > 0 else 0.0
            actual_energy = solar_kwh + actual_grid_kwh
            solar_used += solar_kwh
            grid_used += actual_grid_kwh

            remaining_charging: list[Vehicle] = []
            for vehicle in station.charging:
                requested = min(vehicle.remaining_kwh, self.charger_power_kw * step_hours)
                share = requested / requested_kwh if requested_kwh > 0 else 0.0
                delivered = actual_energy * share
                vehicle.remaining_kwh = max(0.0, vehicle.remaining_kwh - delivered)
                if vehicle.remaining_kwh <= 0.05:
                    vehicles_served += 1.0
                    station.served_this_step += 1
                    if vehicle.emergency:
                        emergency_served += 1.0
                        station.emergency_served_this_step += 1
                else:
                    remaining_charging.append(vehicle)
            station.charging = remaining_charging

        self.metrics["vehicles_served"] += vehicles_served
        self.metrics["emergency_served"] += emergency_served
        self.metrics["solar_kwh_used"] += solar_used
        self.metrics["grid_kwh_used"] += grid_used
        self.metrics["grid_overload"] += overload_kwh
        if overload_kwh > 0.0:
            self.metrics["grid_overload_events"] += 1.0

        return {
            "vehicles_served": vehicles_served,
            "solar_kwh_used": solar_used,
            "emergency_served": emergency_served,
            "grid_overload": overload_kwh,
            "grid_kwh_used": grid_used,
        }

    def _compute_reward(self, events: dict[str, float]) -> float:
        """Compute normalized reward in [0, 1] range.

        Combines:
        - Vehicle service rate (0.4 weight)
        - Solar utilization (0.3 weight)
        - Wait time efficiency (0.3 weight)
        """
        # Normalize individual components
        vehicles_served_norm = float(np.clip(events["vehicles_served"] / max(1.0, events["arrivals"]), 0.0, 1.0)) if events.get("arrivals", 0) > 0 else 0.0

        # Solar usage: ratio of solar to total energy
        total_energy = events["solar_kwh_used"] + events["grid_kwh_used"] + 1e-6
        solar_ratio = float(np.clip(events["solar_kwh_used"] / total_energy, 0.0, 1.0))

        # Wait time efficiency: 1 - normalized_wait_time
        normalized_wait = min(1.0, events["avg_wait_time"] / max(1.0, self.task.wait_normalizer))
        wait_efficiency = float(1.0 - normalized_wait)

        # Weighted combination
        reward = (
            0.4 * vehicles_served_norm
            + 0.3 * solar_ratio
            + 0.3 * wait_efficiency
        )

        return float(np.clip(reward, 0.0, 1.0))

    def _queue_wait_average(self) -> float:
        waits = [vehicle.wait_steps for station in self.stations for vehicle in station.queue]
        if not waits:
            return 0.0
        mean_wait = float(np.mean(waits))
        self.metrics["queue_wait_accumulator"] += float(sum(waits))
        self.metrics["queue_observations"] += float(len(waits))
        return mean_wait

    def _metrics_snapshot(self) -> dict[str, float]:
        total_arrivals = max(1.0, self.metrics["vehicles_seen"])
        total_energy = self.metrics["solar_kwh_used"] + self.metrics["grid_kwh_used"]
        average_wait = (
            self.metrics["queue_wait_accumulator"] / self.metrics["queue_observations"]
            if self.metrics["queue_observations"] > 0
            else 0.0
        )
        normalized_wait = min(1.0, average_wait / max(1.0, self.task.wait_normalizer))
        solar_usage_ratio = float(self.metrics["solar_kwh_used"] / total_energy) if total_energy > 0 else 0.0
        emergency_seen = max(0.0, self.metrics["emergency_seen"])
        emergency_missed = max(0.0, emergency_seen - self.metrics["emergency_served"])
        return {
            "task_id": self.task.id,
            "vehicles_seen": self.metrics["vehicles_seen"],
            "vehicles_served": self.metrics["vehicles_served"],
            "vehicles_completed": self.metrics["vehicles_served"],
            "served_ratio": float(self.metrics["vehicles_served"] / total_arrivals),
            "throughput_ratio": float(self.metrics["vehicles_served"] / total_arrivals),
            "solar_usage_ratio": solar_usage_ratio,
            "solar_utilization_pct": solar_usage_ratio * 100.0,
            "normalized_wait_time": normalized_wait,
            "average_wait_time": average_wait,
            "solar_kwh_used": self.metrics["solar_kwh_used"],
            "grid_kwh_used": self.metrics["grid_kwh_used"],
            "emergency_seen": emergency_seen,
            "emergency_served": self.metrics["emergency_served"],
            "emergency_missed": emergency_missed,
            "grid_overload": self.metrics["grid_overload"],
            "grid_overload_events": self.metrics["grid_overload_events"],
            "wait_timeout_departures": self.metrics["wait_timeout_departures"],
        }

    def _build_observation(self) -> dict[str, Any]:
        rows: list[list[float]] = []
        queue_lengths: list[int] = []
        for station in self.stations:
            queue_len = len(station.queue)
            emergency_queue = sum(1 for vehicle in station.queue if vehicle.emergency)
            free_chargers = max(0, station.charger_count - len(station.charging))
            rows.append(
                [
                    float(queue_len),
                    float(len(station.charging)),
                    float(station.solar_kw),
                    float(station.grid_kw),
                    float(station.price_multiplier),
                    float(emergency_queue),
                    float(free_chargers),
                ]
            )
            queue_lengths.append(queue_len)

        day_fraction = float((self.current_step % 96) / 96.0)
        angle = 2.0 * np.pi * day_fraction
        observation = {
            "station_features": np.asarray(rows, dtype=np.float32),
            "queue_lengths": np.asarray(queue_lengths, dtype=np.int64),
            "time_context": np.asarray(
                [day_fraction, float(np.sin(angle)), float(np.cos(angle))],
                dtype=np.float32,
            ),
            "arrivals_summary": self.last_arrivals_summary.astype(np.float32),
            "weather": int(WEATHER_INDEX[self.last_weather]),
        }
        self.last_observation = observation
        return observation
