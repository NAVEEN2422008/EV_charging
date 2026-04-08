"""Determinism tests for fixed-seed rollouts."""

from __future__ import annotations

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv


def test_same_seed_same_first_step() -> None:
    env_a = MultiAgentEVChargingGridEnv(config={"episode_length": 6})
    env_b = MultiAgentEVChargingGridEnv(config={"episode_length": 6})
    obs_a, _ = env_a.reset(seed=42)
    obs_b, _ = env_b.reset(seed=42)
    assert obs_a["weather"] == obs_b["weather"]
    action = env_a.action_space.sample()
    nobs_a, rew_a, _, _, _ = env_a.step(action)
    nobs_b, rew_b, _, _, _ = env_b.step(action)
    assert rew_a == rew_b
    assert (nobs_a["queue_lengths"] == nobs_b["queue_lengths"]).all()
