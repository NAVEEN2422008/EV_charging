"""PettingZoo API smoke tests."""

from __future__ import annotations

import numpy as np

from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv


def test_pettingzoo_reset_and_agent_iter() -> None:
    env = PettingZooEVChargingEnv(config={"episode_length": 4, "num_stations": 10})
    env.reset(seed=123)
    count = 0
    for agent in env.agent_iter(max_iter=50):
        obs = env.observe(agent)
        action = env.action_space(agent).sample()
        env.step(action)
        assert obs is not None
        count += 1
        if all(env.truncations.values()) or all(env.terminations.values()):
            break
    assert count > 0


def test_station_observation_has_action_mask() -> None:
    env = PettingZooEVChargingEnv(config={"episode_length": 3, "num_stations": 10})
    env.reset(seed=99)
    obs = env.observe("station_0")
    assert "action_mask" in obs
    assert obs["action_mask"].shape[0] == 4


def test_observations_match_spaces() -> None:
    env = PettingZooEVChargingEnv(config={"episode_length": 3, "num_stations": 10})
    env.reset(seed=11)
    coord_obs = env.observe("coordinator")
    stn_obs = env.observe("station_0")
    assert env.observation_space("coordinator").contains(coord_obs)
    assert env.observation_space("station_0").contains(stn_obs)


def test_station_observation_space_accepts_negative_time_context() -> None:
    env = PettingZooEVChargingEnv(config={"episode_length": 3, "num_stations": 10})
    env.reset(seed=11)
    negative_obs = {
        "local_features": np.zeros(8, dtype=np.float32),
        "neighbor_queue_lengths": np.zeros(env.gym_env.num_stations, dtype=np.int64),
        "global_context": np.asarray([-0.5, 0.3, 0.0], dtype=np.float32),
        "action_mask": np.ones(4, dtype=np.int8),
    }
    assert env.observation_space("station_0").contains(negative_obs)
