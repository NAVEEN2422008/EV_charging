"""API tests for environment compatibility and lifecycle."""

from __future__ import annotations

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv


def _make_env() -> MultiAgentEVChargingGridEnv:
    return MultiAgentEVChargingGridEnv(config={"episode_length": 8, "num_stations": 10})


def test_reset_matches_observation_space() -> None:
    env = _make_env()
    obs, info = env.reset(seed=123)
    assert env.observation_space.contains(obs)
    assert "env_name" in info


def test_step_advances_and_shapes() -> None:
    env = _make_env()
    obs, _ = env.reset(seed=123)
    action = env.action_space.sample()
    next_obs, reward, terminated, truncated, info = env.step(action)
    assert env.observation_space.contains(next_obs)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert "events" in info
    assert env.episode_state.time_step == 1
    assert obs["station_features"].shape == next_obs["station_features"].shape


def test_truncates_at_episode_length() -> None:
    env = _make_env()
    env.reset(seed=77)
    truncated = False
    for _ in range(20):
        _, _, _, truncated, _ = env.step(env.action_space.sample())
        if truncated:
            break
    assert truncated is True


def test_reset_options_rebuild_spaces() -> None:
    env = _make_env()
    obs, _ = env.reset(seed=1, options={"num_stations": 6})
    assert obs["station_features"].shape[0] == 6
    assert env.observation_space.contains(obs)
    action = env.action_space.sample()
    _, _, _, _, _ = env.step(action)
