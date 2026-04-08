"""Run heuristic coordinator + station baselines for quick evaluation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from ev_charging_grid_env.agents.coordinator_agent import HeuristicCoordinatorAgent
from ev_charging_grid_env.agents.station_agent import HeuristicStationAgent
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv
from ev_charging_grid_env.simulation.episode_runner import run_episode
from ev_charging_grid_env.simulation.curriculum import curriculum_stage_config


def load_config() -> dict:
    config_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def main(num_episodes: int = 5) -> None:
    config = load_config()
    totals: list[dict[str, float]] = []
    for episode in range(num_episodes):
        env = MultiAgentEVChargingGridEnv(config=curriculum_stage_config(min(2, episode // 2), config))
        coordinator = HeuristicCoordinatorAgent()
        stations = [HeuristicStationAgent() for _ in range(config["num_stations"])]
        totals.append(run_episode(env, coordinator, stations, render=False))

    metric_names = [
        "total_reward",
        "average_wait_time",
        "total_energy_kwh",
        "solar_utilization_pct",
        "emergency_served",
        "emergency_missed",
    ]
    print(f"Heuristic baseline over {num_episodes} episodes:")
    for metric in metric_names:
        values = [episode[metric] for episode in totals]
        print(f"{metric:>24}: {float(np.mean(values)):.3f}")
    pz_env = PettingZooEVChargingEnv(config=config)
    pz_env.reset(seed=7)
    print("PettingZoo env initialized with agents:", pz_env.possible_agents[:3], "...")


if __name__ == "__main__":
    main()
