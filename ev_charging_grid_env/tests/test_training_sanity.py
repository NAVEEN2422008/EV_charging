"""Training loop sanity tests with tiny budgets."""

from __future__ import annotations

from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv
from ev_charging_grid_env.training.algorithms.mappo_trainer import MAPPOConfig, MAPPOTrainer
from ev_charging_grid_env.training.algorithms.ppo_trainer import PPOConfig, PPOTrainer


def test_ppo_tiny_training_run(tmp_path: Path) -> None:
    env = MultiAgentEVChargingGridEnv(config={"episode_length": 20, "num_stations": 10})
    cfg = PPOConfig(total_steps=32, rollout_steps=16, batch_size=8, epochs=1)
    trainer = PPOTrainer(env, cfg, run_dir=tmp_path)
    result = trainer.train()
    assert result["total_steps"] >= 32.0


def test_mappo_tiny_training_run(tmp_path: Path) -> None:
    env = PettingZooEVChargingEnv(config={"episode_length": 20, "num_stations": 10})
    cfg = MAPPOConfig(total_cycles=4, rollout_cycles=2, batch_size=4, epochs=1)
    trainer = MAPPOTrainer(env, cfg, run_dir=tmp_path)
    result = trainer.train()
    assert result["cycles"] >= 2.0
