"""Agent contract and integration episode tests."""

from __future__ import annotations

from ev_charging_grid_env.agents.coordinator_agent import HeuristicCoordinatorAgent, RandomCoordinatorAgent
from ev_charging_grid_env.agents.station_agent import HeuristicStationAgent, RandomStationAgent
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.simulation.episode_runner import run_episode


def test_agent_output_ranges() -> None:
    env = MultiAgentEVChargingGridEnv(config={"episode_length": 5, "num_stations": 10})
    obs, _ = env.reset(seed=5)
    coord = HeuristicCoordinatorAgent()
    station = HeuristicStationAgent()
    ca = coord.act(obs)
    assert len(ca["price_deltas"]) == env.num_stations
    assert 0 <= int(ca["emergency_target_station"]) <= env.num_stations
    sa = station.act(0, obs, ca)
    assert sa in {0, 1, 2, 3}


def test_full_episode_run_with_heuristics() -> None:
    env = MultiAgentEVChargingGridEnv(config={"episode_length": 20, "num_stations": 10})
    metrics = run_episode(
        env,
        HeuristicCoordinatorAgent(),
        [HeuristicStationAgent() for _ in range(env.num_stations)],
        render=False,
    )
    assert "total_reward" in metrics
    assert metrics["steps"] > 0


def test_full_episode_run_with_random_agents() -> None:
    env = MultiAgentEVChargingGridEnv(config={"episode_length": 15, "num_stations": 10})
    metrics = run_episode(
        env,
        RandomCoordinatorAgent(num_stations=env.num_stations),
        [RandomStationAgent() for _ in range(env.num_stations)],
        render=False,
    )
    assert metrics["steps"] > 0
