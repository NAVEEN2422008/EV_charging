"""Evaluate random, heuristic, and optional trained agents."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from ev_charging_grid_env.agents.coordinator_agent import HeuristicCoordinatorAgent, RandomCoordinatorAgent
from ev_charging_grid_env.agents.station_agent import HeuristicStationAgent, RandomStationAgent
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.simulation.episode_runner import run_episode


def load_config() -> dict:
    path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def evaluate_baselines(episodes: int = 5) -> None:
    cfg = load_config()
    random_scores = []
    heuristic_scores = []
    for _ in range(episodes):
        env = MultiAgentEVChargingGridEnv(config=cfg)
        random_scores.append(
            run_episode(env, RandomCoordinatorAgent(num_stations=cfg["num_stations"]), [RandomStationAgent() for _ in range(cfg["num_stations"])])
        )
        env2 = MultiAgentEVChargingGridEnv(config=cfg)
        heuristic_scores.append(
            run_episode(env2, HeuristicCoordinatorAgent(), [HeuristicStationAgent() for _ in range(cfg["num_stations"])])
        )
    print("Random avg reward:", float(np.mean([x["total_reward"] for x in random_scores])))
    print("Heuristic avg reward:", float(np.mean([x["total_reward"] for x in heuristic_scores])))
    print("Heuristic avg wait:", float(np.mean([x["average_wait_time"] for x in heuristic_scores])))
    print("Heuristic solar %:", float(np.mean([x["solar_utilization_pct"] for x in heuristic_scores])))


if __name__ == "__main__":
    evaluate_baselines()
