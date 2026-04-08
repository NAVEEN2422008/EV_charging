"""Constraint tests for queue/capacity and outage transitions."""

from __future__ import annotations

import numpy as np

from ev_charging_grid_env.envs.dynamics import initialize_episode, progress_step
from ev_charging_grid_env.envs.task_generator import generate_task


def test_station_capacity_never_exceeded() -> None:
    task = generate_task({"num_stations": 10, "episode_length": 5})
    state = initialize_episode(task)
    rng = np.random.default_rng(1)
    for _ in range(3):
        progress_step(state, task, 1.0, 120.0, 45.0, rng)
        for station in state.stations:
            assert len(station.charging_vehicles) <= station.max_slots


def test_outage_timer_non_negative() -> None:
    task = generate_task({"num_stations": 10, "episode_length": 5, "station_outage_probability": 1.0})
    state = initialize_episode(task)
    rng = np.random.default_rng(2)
    progress_step(state, task, 1.0, 120.0, 45.0, rng)
    for station in state.stations:
        assert station.outage_time_left >= 0
