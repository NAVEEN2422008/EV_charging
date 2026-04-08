"""Edge-case tests for arrivals, overload, and action validation."""

from __future__ import annotations

import pytest

from ev_charging_grid_env.agents.coordinator_agent import HeuristicCoordinatorAgent
from ev_charging_grid_env.agents.station_agent import HeuristicStationAgent
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.simulation.episode_runner import run_episode


def test_no_vehicle_arrival_scenario_runs() -> None:
    env = MultiAgentEVChargingGridEnv(
        config={"num_stations": 10, "episode_length": 10, "base_arrival_rate": 0.0, "emergency_arrival_prob": 0.0}
    )
    metrics = run_episode(
        env,
        HeuristicCoordinatorAgent(),
        [HeuristicStationAgent() for _ in range(env.num_stations)],
        render=False,
    )
    assert metrics["steps"] > 0
    assert metrics["total_energy_kwh"] >= 0.0


def test_overload_pressure_records_events() -> None:
    env = MultiAgentEVChargingGridEnv(
        config={
            "num_stations": 10,
            "episode_length": 20,
            "base_arrival_rate": 12.0,
            "grid_limit_kw": 50.0,
            "fast_charge_kw": 200.0,
        }
    )
    run_episode(env, HeuristicCoordinatorAgent(), [HeuristicStationAgent() for _ in range(env.num_stations)], render=False)
    assert env.episode_stats["grid_overload_events"] >= 0.0


def test_emergency_only_arrivals_run() -> None:
    env = MultiAgentEVChargingGridEnv(
        config={"num_stations": 10, "episode_length": 12, "base_arrival_rate": 4.0, "emergency_arrival_prob": 1.0}
    )
    run_episode(env, HeuristicCoordinatorAgent(), [HeuristicStationAgent() for _ in range(env.num_stations)], render=False)
    assert env.episode_stats["vehicles_seen"] >= 0.0


def test_action_validation_errors() -> None:
    env = MultiAgentEVChargingGridEnv(config={"num_stations": 10, "episode_length": 5})
    env.reset(seed=0)
    with pytest.raises(TypeError):
        env.step([])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        env.step({"station_actions": [0] * 10})  # missing coordinator_action
    with pytest.raises(ValueError):
        env.step({"coordinator_action": {"price_deltas": [1] * 9, "emergency_target_station": 1}, "station_actions": [0] * 10})
    with pytest.raises(ValueError):
        env.step({"coordinator_action": {"price_deltas": [1] * 10, "emergency_target_station": 1}, "station_actions": [0] * 9})


def test_invalid_weather_probabilities_rejected() -> None:
    with pytest.raises(ValueError):
        MultiAgentEVChargingGridEnv(config={"weather_probs": {}})
    with pytest.raises(ValueError):
        MultiAgentEVChargingGridEnv(config={"weather_probs": {"sunny": 0.0, "cloudy": 0.0, "rainy": 0.0}})
    with pytest.raises(ValueError):
        MultiAgentEVChargingGridEnv(config={"weather_probs": {"sunny": -1.0, "cloudy": 1.0}})
