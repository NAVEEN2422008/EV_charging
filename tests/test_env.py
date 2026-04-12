"""Environment behavior tests."""

from __future__ import annotations

import numpy as np

from ev_charging_grid_env.envs import MultiAgentEVChargingGridEnv


def make_action(num_stations: int) -> dict[str, object]:
    return {
        "coordinator_action": {
            "price_deltas": [0] * num_stations,
            "emergency_target_station": 0,
        },
        "station_actions": [1] * num_stations,
    }


def test_reset_step_and_state_contract() -> None:
    env = MultiAgentEVChargingGridEnv()
    observation, info = env.reset(seed=42)
    assert isinstance(observation, dict)
    assert isinstance(info, dict)
    assert "station_features" in observation
    assert "queue_lengths" in observation
    assert "time_context" in observation

    observation, reward, terminated, truncated, info = env.step(make_action(env.num_stations))
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(info, dict)
    assert isinstance(env.state(), dict)


def test_reward_formula_shape() -> None:
    env = MultiAgentEVChargingGridEnv()
    env.reset(seed=42)
    reward = env._compute_reward(
        {
            "vehicles_served": 4.0,
            "solar_kwh_used": 20.0,
            "emergency_served": 1.0,
            "avg_wait_time": 3.0,
            "queue_length": 5.0,
            "grid_overload": 2.0,
        }
    )
    expected = (2.0 * 4.0 + 1.5 * 20.0 + 5.0 * 1.0 - 0.5 * 3.0 - 1.0 * 5.0 - 3.0 * 2.0) / 10.0
    assert reward == expected


def test_runs_100_steps_without_nan() -> None:
    env = MultiAgentEVChargingGridEnv()
    env.reset(seed=42)
    for _ in range(100):
        observation, reward, terminated, truncated, info = env.step(make_action(env.num_stations))
        assert not np.isnan(reward)
        assert not np.isinf(reward)
        if terminated or truncated:
            break
    assert env.current_step >= 100 or truncated


def test_dynamic_station_count_rebuilds_spaces() -> None:
    env = MultiAgentEVChargingGridEnv()
    observation, _ = env.reset(seed=42, options={"num_stations": 6})
    assert env.num_stations == 6
    assert observation["station_features"].shape[0] == 6
    assert env.action_space["station_actions"].shape == (6,)

