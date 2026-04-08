"""Run random-action baseline for environment sanity checks."""

from __future__ import annotations

from pathlib import Path

import yaml

from ev_charging_grid_env.agents.coordinator_agent import RandomCoordinatorAgent
from ev_charging_grid_env.agents.station_agent import RandomStationAgent
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.simulation.episode_runner import run_episode
from ev_charging_grid_env.simulation.visualization import print_episode_table


def load_config() -> dict:
    config_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def main() -> None:
    config = load_config()
    env = MultiAgentEVChargingGridEnv(config=config)
    coordinator = RandomCoordinatorAgent(num_stations=config["num_stations"])
    station_agents = [RandomStationAgent() for _ in range(config["num_stations"])]
    metrics = run_episode(env, coordinator, station_agents, render=False)
    print("Random baseline episode metrics:")
    print_episode_table(metrics)


if __name__ == "__main__":
    main()
