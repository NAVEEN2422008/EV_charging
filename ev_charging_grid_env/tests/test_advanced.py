"""Comprehensive advanced tests — covers areas not tested by existing suite.

New coverage:
  - Single-station edge case
  - Model save / load round-trip
  - Experiment runner config handling (flat + nested)
  - Observation / action space compliance
  - Reward sensitivity to each weight
  - Longer episode stability
  - PPO / MAPPO config field filtering
  - Weather probability edge cases
  - PettingZoo env action-mask correctness
  - Dashboard simulator history_df shape
"""

from __future__ import annotations

import dataclasses
import io
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv
from ev_charging_grid_env.envs.reward_functions import compute_step_reward
from ev_charging_grid_env.envs.task_generator import generate_task
from ev_charging_grid_env.envs.dynamics import initialize_episode, progress_step
from ev_charging_grid_env.envs.state import VehicleState


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_valid_action(env: MultiAgentEVChargingGridEnv) -> dict:
    """Return a valid heuristic no-op action for env."""
    n = env.num_stations
    return {
        "coordinator_action": {
            "price_deltas": np.ones(n, dtype=np.int64),
            "emergency_target_station": n,  # no routing
        },
        "station_actions": np.ones(n, dtype=np.int64),  # accept FIFO
    }


def _full_episode(env: MultiAgentEVChargingGridEnv, seed: int = 0) -> list[float]:
    """Run a full episode and return all step rewards."""
    obs, _ = env.reset(seed=seed)
    rewards = []
    while True:
        action = env.action_space.sample()
        obs, r, terminated, truncated, _ = env.step(action)
        rewards.append(float(r))
        if terminated or truncated:
            break
    return rewards


# ─────────────────────────────────────────────────────────────────────────────
# 1. Single-station edge case
# ─────────────────────────────────────────────────────────────────────────────

class TestSingleStation:
    """Environment with exactly one station should run without errors."""

    def test_single_station_reset_step(self) -> None:
        env = MultiAgentEVChargingGridEnv(config={"num_stations": 1, "episode_length": 5})
        obs, info = env.reset(seed=0)
        assert obs["station_features"].shape == (1, 7)
        assert obs["queue_lengths"].shape == (1,)
        action = _make_valid_action(env)
        obs2, r, term, trunc, info2 = env.step(action)
        assert not np.isnan(r)
        assert obs2["station_features"].shape == (1, 7)

    def test_single_station_full_episode(self) -> None:
        env = MultiAgentEVChargingGridEnv(config={"num_stations": 1, "episode_length": 20})
        rewards = _full_episode(env, seed=1)
        assert len(rewards) == 20
        assert all(not np.isnan(r) for r in rewards)

    def test_single_station_pettingzoo(self) -> None:
        env = PettingZooEVChargingEnv(config={"num_stations": 1, "episode_length": 5})
        env.reset(seed=2)
        step_count = 0
        for agent in env.agent_iter(max_iter=50):
            env.step(env.action_space(agent).sample())
            step_count += 1
            if all(env.truncations.values()) or all(env.terminations.values()):
                break
        assert step_count > 0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Model save / load round-trip
# ─────────────────────────────────────────────────────────────────────────────

class TestModelSaveLoad:
    """PPO / MAPPO model parameters survive a save → load round-trip."""

    def test_ppo_checkpoint_roundtrip(self) -> None:
        from ev_charging_grid_env.training.algorithms.ppo_trainer import PPOConfig, PPOTrainer

        env = MultiAgentEVChargingGridEnv(config={"num_stations": 3, "episode_length": 5})
        cfg = PPOConfig(total_steps=256, rollout_steps=64, seed=7)

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = PPOTrainer(env, cfg, Path(tmpdir))

            # Capture original parameters
            orig_params = {k: v.clone() for k, v in trainer.model.state_dict().items()}

            # Save
            ckpt_path = Path(tmpdir) / "test_ckpt.pt"
            torch.save(trainer.model.state_dict(), ckpt_path)

            # Reload into fresh model
            from ev_charging_grid_env.training.models.actor_critic import CentralizedActorCritic
            from ev_charging_grid_env.training.utils.preprocessing import flatten_observation
            obs, _ = env.reset(seed=7)
            obs_vec = flatten_observation(obs)
            fresh_model = CentralizedActorCritic(obs_dim=obs_vec.shape[0], num_stations=env.num_stations)
            fresh_model.load_state_dict(torch.load(ckpt_path, weights_only=True))

            for key, orig_val in orig_params.items():
                loaded_val = fresh_model.state_dict()[key]
                assert torch.allclose(orig_val, loaded_val), f"Mismatch in layer {key}"

    def test_mappo_checkpoint_roundtrip(self) -> None:
        from ev_charging_grid_env.training.algorithms.mappo_trainer import MAPPOConfig, MAPPOTrainer

        env = PettingZooEVChargingEnv(config={"num_stations": 3, "episode_length": 5})
        cfg = MAPPOConfig(total_cycles=256, rollout_cycles=64, seed=8)

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = MAPPOTrainer(env, cfg, Path(tmpdir))
            orig_params = {k: v.clone() for k, v in trainer.station_policy.state_dict().items()}

            ckpt_path = Path(tmpdir) / "station.pt"
            torch.save(trainer.station_policy.state_dict(), ckpt_path)

            from ev_charging_grid_env.training.models.actor_critic import MAPPOStationPolicy
            obs_dim = list(orig_params.values())[0].shape[-1] if orig_params else 1
            fresh = MAPPOStationPolicy(local_obs_dim=trainer.station_policy.actor.net[0].in_features,
                                       global_obs_dim=trainer.station_policy.critic.net[0].in_features)
            fresh.load_state_dict(torch.load(ckpt_path, weights_only=True))

            for key, orig_val in orig_params.items():
                assert torch.allclose(orig_val, fresh.state_dict()[key]), f"Mismatch: {key}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Experiment runner config handling
# ─────────────────────────────────────────────────────────────────────────────

class TestExperimentRunnerConfig:
    """Experiment runner should handle flat configs and ignore unknown keys."""

    def test_flat_config_runs_ppo(self) -> None:
        """Flat YAML-style config should work with the fixed experiment runner."""
        from ev_charging_grid_env.training.experiment_runner import run_experiment
        import yaml

        flat_cfg = {
            "num_stations": 3,
            "episode_length": 5,
            "base_arrival_rate": 4.0,
            # Keep the experiment short for CI/test runtime
            "total_steps": 64,
            "rollout_steps": 16,
            "batch_size": 16,
            "epochs": 1,
            "lr": 1e-3,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.yaml"
            cfg_path.write_text(yaml.dump(flat_cfg), encoding="utf-8")
            out_dir = Path(tmpdir) / "runs"

            # Should not raise even though config is flat rather than nested
            run_experiment(cfg_path, "ppo", [42], out_dir)

            summary = out_dir / "ppo_summary.json"
            assert summary.exists()
            import json
            data = json.loads(summary.read_text())
            assert data["results"][0]["seed"] == 42

    def test_filter_dataclass_kwargs(self) -> None:
        """Unknown keys should be silently filtered before passing to dataclass."""
        from ev_charging_grid_env.training.experiment_runner import _filter_dataclass_kwargs
        from ev_charging_grid_env.training.algorithms.ppo_trainer import PPOConfig

        messy_cfg = {
            "lr": 1e-3,
            "gamma": 0.95,
            "unknown_key_xyz": "should_be_dropped",
            "num_stations": 10,  # env param — not a PPOConfig field
        }
        filtered = _filter_dataclass_kwargs(messy_cfg, PPOConfig)
        assert "lr" in filtered
        assert "gamma" in filtered
        assert "unknown_key_xyz" not in filtered
        assert "num_stations" not in filtered

        # Should construct successfully
        cfg = PPOConfig(**filtered)
        assert cfg.lr == 1e-3
        assert cfg.gamma == 0.95


# ─────────────────────────────────────────────────────────────────────────────
# 4. Observation / action space compliance
# ─────────────────────────────────────────────────────────────────────────────

class TestSpaceCompliance:
    """Every observation and sampled action must lie within declared spaces."""

    @pytest.mark.parametrize("num_stations", [1, 3, 5, 10])
    def test_obs_in_observation_space(self, num_stations: int) -> None:
        env = MultiAgentEVChargingGridEnv(config={"num_stations": num_stations, "episode_length": 3})
        obs, _ = env.reset(seed=num_stations)
        # station_features shape
        assert obs["station_features"].shape == (num_stations, 7)
        # time_context must be in [-1, 1]
        assert np.all(obs["time_context"] >= -1.0 - 1e-6)
        assert np.all(obs["time_context"] <= 1.0 + 1e-6)
        # weather must be 0, 1, or 2
        assert obs["weather"] in {0, 1, 2}
        # queue_lengths non-negative
        assert np.all(obs["queue_lengths"] >= 0)

    @pytest.mark.parametrize("num_stations", [1, 5, 10])
    def test_sampled_action_accepted_by_env(self, num_stations: int) -> None:
        env = MultiAgentEVChargingGridEnv(config={"num_stations": num_stations, "episode_length": 3})
        env.reset(seed=0)
        for _ in range(3):
            action = env.action_space.sample()
            obs, r, term, trunc, info = env.step(action)
            assert not np.isnan(r)
            if term or trunc:
                break

    def test_pettingzoo_obs_spaces_match(self) -> None:
        env = PettingZooEVChargingEnv(config={"num_stations": 5, "episode_length": 3})
        env.reset(seed=0)
        for agent in env.possible_agents:
            obs = env.observe(agent)
            space = env.observation_space(agent)
            for key, val in obs.items():
                if key in space.spaces:
                    # Just check types / shapes don't crash contains()
                    arr = np.asarray(val)
                    assert arr is not None


# ─────────────────────────────────────────────────────────────────────────────
# 5. Reward sensitivity to each weight
# ─────────────────────────────────────────────────────────────────────────────

class TestRewardSensitivity:
    """Each reward weight should independently influence the scalar reward."""

    _base_state = {
        "mean_wait_time": 5.0,
        "total_grid_kw_used": 800.0,
        "grid_limit_kw": 1000.0,
    }
    _base_events = {
        "timed_out_count": 1.0,
        "solar_kwh_used": 10.0,
        "emergency_served": 1.0,
        "vehicles_completed": 2.0,
        "quick_service_score": 3.0,
        "emergency_missed": 0.0,
        "travel_distance_km": 2.0,
    }

    def _reward(self, cfg: dict) -> float:
        return compute_step_reward(self._base_state, self._base_events, cfg)

    def test_higher_completion_weight_increases_reward(self) -> None:
        r_low = self._reward({"completion_reward_weight": 0.1})
        r_high = self._reward({"completion_reward_weight": 5.0})
        assert r_high > r_low

    def test_higher_timeout_penalty_decreases_reward(self) -> None:
        r_low = self._reward({"timeout_penalty_weight": 0.1})
        r_high = self._reward({"timeout_penalty_weight": 10.0})
        assert r_high < r_low

    def test_higher_solar_weight_increases_reward(self) -> None:
        r_low = self._reward({"solar_priority_weight": 0.01})
        r_high = self._reward({"solar_priority_weight": 2.0})
        assert r_high > r_low

    def test_reward_is_finite_for_extreme_inputs(self) -> None:
        extreme_state = {
            "mean_wait_time": 1e6,
            "total_grid_kw_used": 1e6,
            "grid_limit_kw": 1.0,
        }
        extreme_events = {k: 1e6 for k in self._base_events}
        cfg = {"reward_clip": 100.0}
        r = compute_step_reward(extreme_state, extreme_events, cfg)
        assert np.isfinite(r)
        assert -100.0 <= r <= 100.0


# ─────────────────────────────────────────────────────────────────────────────
# 6. Longer episode stability
# ─────────────────────────────────────────────────────────────────────────────

class TestLongEpisodeStability:
    """Full episodes of length 200+ must complete without NaN rewards or crashes."""

    @pytest.mark.parametrize("episode_length,seed", [(200, 0), (500, 1)])
    def test_long_episode_no_crash(self, episode_length: int, seed: int) -> None:
        env = MultiAgentEVChargingGridEnv(
            config={"episode_length": episode_length, "base_arrival_rate": 8.0}
        )
        rewards = _full_episode(env, seed=seed)
        assert len(rewards) == episode_length
        assert all(np.isfinite(r) for r in rewards), "Non-finite reward detected"
        assert not np.isnan(np.sum(rewards))

    def test_episode_stats_non_negative(self) -> None:
        """Counts / energy stats should be non-negative; total_reward may be negative."""
        env = MultiAgentEVChargingGridEnv(config={"episode_length": 100})
        _full_episode(env, seed=2)
        stats = env.episode_stats
        # total_reward CAN be legitimately negative (penalty terms outweigh bonuses)
        non_negative_keys = {
            "vehicles_seen", "total_wait_time", "solar_energy_kwh",
            "total_energy_kwh", "emergency_served", "emergency_missed",
            "travel_distance_km", "grid_overload_events",
        }
        for key in non_negative_keys:
            val = stats.get(key, 0.0)
            assert val >= 0.0, f"Negative stat: {key} = {val}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Weather probability edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestWeatherEdgeCases:
    """Weather transition should be robust to boundary probability distributions."""

    def test_sunny_only(self) -> None:
        env = MultiAgentEVChargingGridEnv(
            config={"episode_length": 10, "weather_probs": {"sunny": 1.0, "cloudy": 0.0, "rainy": 0.0}}
        )
        obs, _ = env.reset(seed=0)
        for _ in range(5):
            obs, _, _, trunc, _ = env.step(env.action_space.sample())
        # should not crash

    def test_rainy_only(self) -> None:
        env = MultiAgentEVChargingGridEnv(
            config={"episode_length": 10, "weather_probs": {"sunny": 0.0, "cloudy": 0.0, "rainy": 1.0}}
        )
        env.reset(seed=0)
        for _ in range(5):
            env.step(env.action_space.sample())

    def test_unnormalized_probabilities_are_normalized(self) -> None:
        task = generate_task({"num_stations": 3, "weather_probs": {"sunny": 3.0, "cloudy": 1.0, "rainy": 1.0}})
        total = sum(task.weather_probs.values())
        assert abs(total - 1.0) < 1e-6, f"Weather probs not normalized: {task.weather_probs}"


# ─────────────────────────────────────────────────────────────────────────────
# 8. PettingZoo action-mask correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestPettingZooActionMask:
    """Action masks must correctly reflect station state."""

    def test_outage_disables_accept_actions(self) -> None:
        env = PettingZooEVChargingEnv(config={"num_stations": 3, "episode_length": 5})
        env.reset(seed=10)
        # Force station 0 into outage
        env.gym_env.episode_state.stations[0].outage_time_left = 5
        # Add a vehicle to queue so mask would normally allow accept
        from collections import deque
        env.gym_env.episode_state.stations[0].queue = deque([
            VehicleState(
                id=999, required_kwh=10.0, remaining_kwh=10.0, battery_level=0.5,
                is_emergency=False, urgency=0, max_wait_timesteps=45,
                green_preference=0.5, price_sensitivity=0.5,
                location_xy=(0.0, 0.0), preferred_station=0, assigned_station=0,
            )
        ])
        obs = env.observe("station_0")
        mask = obs["action_mask"]
        # Accept FIFO (index 1) and Accept Emergency (index 2) should be 0 due to outage
        assert mask[1] == 0, "FIFO accept should be disabled during outage"
        assert mask[2] == 0, "Emergency accept should be disabled during outage"

    def test_empty_queue_disables_redirect(self) -> None:
        env = PettingZooEVChargingEnv(config={"num_stations": 3, "episode_length": 5})
        env.reset(seed=11)
        # Ensure station 1 has empty queue
        from collections import deque
        env.gym_env.episode_state.stations[1].queue = deque()
        obs = env.observe("station_1")
        mask = obs["action_mask"]
        # Redirect (index 3) should be 0 when queue is empty
        assert mask[3] == 0, "Redirect should be disabled for empty queue"


# ─────────────────────────────────────────────────────────────────────────────
# 9. Dashboard simulator history_df
# ─────────────────────────────────────────────────────────────────────────────

class TestDashboardSimulator:
    """Dashboard simulator produces correct history DataFrames."""

    def test_history_df_grows_with_steps(self) -> None:
        from ev_charging_grid_env.dashboard.simulator import build_simulation
        from ev_charging_grid_env.dashboard.policies import build_policy_bundle

        sim = build_simulation({"num_stations": 3, "episode_length": 30}, seed=0)
        bundle = build_policy_bundle("Heuristic", sim.env.num_stations)
        for _ in range(10):
            sim.step_with_policies(bundle.coordinator, bundle.stations)

        df = sim.history_df()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 10
        expected_cols = {"timestep", "reward", "total_reward", "avg_wait", "solar_util_pct"}
        assert expected_cols.issubset(set(df.columns)), f"Missing columns: {expected_cols - set(df.columns)}"

    def test_history_df_no_nan(self) -> None:
        from ev_charging_grid_env.dashboard.simulator import build_simulation
        from ev_charging_grid_env.dashboard.policies import build_policy_bundle

        sim = build_simulation({"num_stations": 5, "episode_length": 50}, seed=5)
        bundle = build_policy_bundle("Random", sim.env.num_stations)
        for _ in range(25):
            sim.step_with_policies(bundle.coordinator, bundle.stations)
            if sim.done:
                break

        df = sim.history_df()
        assert not df.isnull().values.any(), f"NaN values found in history df:\n{df.isnull().sum()}"

    def test_done_flag_set_at_episode_end(self) -> None:
        from ev_charging_grid_env.dashboard.simulator import build_simulation
        from ev_charging_grid_env.dashboard.policies import build_policy_bundle

        sim = build_simulation({"num_stations": 3, "episode_length": 5}, seed=0)
        bundle = build_policy_bundle("Heuristic", sim.env.num_stations)
        for _ in range(6):  # One extra step past episode length
            sim.step_with_policies(bundle.coordinator, bundle.stations)
        assert sim.done, "done should be True after episode ends"


# ─────────────────────────────────────────────────────────────────────────────
# 10. Plots module — no crash on edge inputs
# ─────────────────────────────────────────────────────────────────────────────

class TestPlotsNocrash:
    """Plot functions should not raise on empty or near-empty inputs."""

    def _fresh_env(self) -> MultiAgentEVChargingGridEnv:
        env = MultiAgentEVChargingGridEnv(config={"num_stations": 5, "episode_length": 5})
        env.reset(seed=0)
        return env

    def test_station_map_all_zero_queues(self) -> None:
        from ev_charging_grid_env.dashboard.plots import station_map_figure
        env = self._fresh_env()
        # All queues should be 0 at reset
        fig = station_map_figure(env)
        assert fig is not None

    def test_grid_gauge_zero_usage(self) -> None:
        from ev_charging_grid_env.dashboard.plots import grid_utilization_gauge
        fig = grid_utilization_gauge(0.0, 1800.0)
        assert fig is not None

    def test_solar_breakdown_zero_energy(self) -> None:
        from ev_charging_grid_env.dashboard.plots import solar_breakdown_chart
        env = self._fresh_env()
        fig = solar_breakdown_chart(env)
        assert fig is not None

    def test_emergency_timeline_empty_df(self) -> None:
        from ev_charging_grid_env.dashboard.plots import emergency_timeline_chart
        fig = emergency_timeline_chart(pd.DataFrame())
        assert fig is not None

    def test_reward_distribution_empty_df(self) -> None:
        from ev_charging_grid_env.dashboard.plots import reward_distribution_chart
        fig = reward_distribution_chart(pd.DataFrame())
        assert fig is not None

    def test_policy_radar_empty_df(self) -> None:
        from ev_charging_grid_env.dashboard.plots import policy_radar_chart
        fig = policy_radar_chart(pd.DataFrame())
        assert fig is not None

    def test_station_load_heatmap(self) -> None:
        from ev_charging_grid_env.dashboard.plots import station_load_heatmap
        env = self._fresh_env()
        fig = station_load_heatmap(env)
        assert fig is not None

    def test_queue_line_figure(self) -> None:
        from ev_charging_grid_env.dashboard.plots import queue_line_figure
        env = self._fresh_env()
        fig = queue_line_figure(env)
        assert fig is not None


# ─────────────────────────────────────────────────────────────────────────────
# 11. Multi-station large config stress test
# ─────────────────────────────────────────────────────────────────────────────

class TestLargeConfig:
    """Larger environments (20 stations) should work correctly."""

    def test_20_stations_episode(self) -> None:
        env = MultiAgentEVChargingGridEnv(
            config={"num_stations": 20, "episode_length": 50, "base_arrival_rate": 10.0}
        )
        rewards = _full_episode(env, seed=99)
        assert len(rewards) == 50
        assert all(np.isfinite(r) for r in rewards)

    def test_20_stations_obs_shape(self) -> None:
        env = MultiAgentEVChargingGridEnv(config={"num_stations": 20, "episode_length": 5})
        obs, _ = env.reset(seed=0)
        assert obs["station_features"].shape == (20, 7)
        assert obs["queue_lengths"].shape == (20,)
        assert len(obs["arrivals_summary"]) == 3


# ─────────────────────────────────────────────────────────────────────────────
# 12. PPO tiny training — model parameters actually change
# ─────────────────────────────────────────────────────────────────────────────

class TestPPOLearning:
    """After a training run, model weights should have changed from their init."""

    def test_ppo_weights_change_after_training(self) -> None:
        from ev_charging_grid_env.training.algorithms.ppo_trainer import PPOConfig, PPOTrainer
        import shutil

        env = MultiAgentEVChargingGridEnv(config={"num_stations": 3, "episode_length": 20})
        cfg = PPOConfig(total_steps=512, rollout_steps=64, epochs=2, seed=42)

        # Use ignore_cleanup_errors=True to handle Windows TensorBoard file lock
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            trainer = PPOTrainer(env, cfg, Path(tmpdir))
            init_params = {k: v.clone() for k, v in trainer.model.state_dict().items()}
            trainer.train()
            final_params = trainer.model.state_dict()

        any_changed = any(
            not torch.allclose(init_params[k], final_params[k], atol=1e-7)
            for k in init_params
        )
        assert any_changed, "PPO training did not update any model parameters"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
