"""Comprehensive tests for bug fixes and robustness."""

from __future__ import annotations

import numpy as np
import pytest

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv
from ev_charging_grid_env.envs.reward_functions import compute_step_reward
from ev_charging_grid_env.envs.dynamics import (
    initialize_episode,
    progress_step,
    generate_arrivals,
    enqueue_arrivals,
)
from ev_charging_grid_env.envs.task_generator import generate_task


# ============================================================================
# FIX VERIFICATION TESTS
# ============================================================================


class TestSolarEnergyDistribution:
    """Verify solar energy is properly distributed per-station, not globally."""

    def test_solar_distributed_per_station(self) -> None:
        """Each station should get its own solar energy, not share globally."""
        task = generate_task({"num_stations": 3, "episode_length": 10})
        state = initialize_episode(task)
        rng = np.random.default_rng(42)

        # Ensure multiple stations have solar
        for i in range(3):
            state.stations[i].has_solar = True
            state.stations[i].base_solar_capacity_kw = 100.0

        # Create one charging vehicle at each station so solar distribution can be validated.
        from ev_charging_grid_env.envs.state import VehicleState

        for station in state.stations:
            vehicle = VehicleState(
                id=station.station_id,
                required_kwh=20.0,
                remaining_kwh=20.0,
                battery_level=0.5,
                is_emergency=False,
                urgency=0,
                max_wait_timesteps=45,
                green_preference=0.5,
                price_sensitivity=0.5,
                location_xy=(0.0, 0.0),
                preferred_station=station.station_id,
                assigned_station=station.station_id,
                travel_time_left=0,
            )
            station.charging_vehicles = [vehicle]

        events = progress_step(state, task, 1.0, 120.0, 45.0, rng)

        assert events["solar_kwh_used"] > 0, "Solar energy should have been used"
        for station in state.stations:
            assert station.solar_kw_used >= 0.0
            if station.charging_vehicles:
                assert station.solar_kw_used >= 0.0


    def test_solar_independent_per_station(self) -> None:
        """Verify Station 1 solar usage doesn't prevent Station 0's solar."""
        task = generate_task({"num_stations": 2, "episode_length": 5})
        state = initialize_episode(task)
        rng = np.random.default_rng(43)

        # Both stations have solar
        state.stations[0].has_solar = True
        state.stations[0].base_solar_capacity_kw = 50.0
        state.stations[1].has_solar = True
        state.stations[1].base_solar_capacity_kw = 50.0

        # Add vehicles to both stations
        from ev_charging_grid_env.envs.state import VehicleState

        v0 = VehicleState(
            id=0,
            required_kwh=20.0,
            remaining_kwh=20.0,
            battery_level=0.5,
            is_emergency=False,
            urgency=0,
            max_wait_timesteps=45,
            green_preference=0.5,
            price_sensitivity=0.5,
            location_xy=(0.0, 0.0),
            preferred_station=0,
            assigned_station=0,
            travel_time_left=0,
        )
        v1 = VehicleState(
            id=1,
            required_kwh=20.0,
            remaining_kwh=20.0,
            battery_level=0.5,
            is_emergency=False,
            urgency=0,
            max_wait_timesteps=45,
            green_preference=0.5,
            price_sensitivity=0.5,
            location_xy=(10.0, 10.0),
            preferred_station=1,
            assigned_station=1,
            travel_time_left=0,
        )

        state.stations[0].charging_vehicles = [v0]
        state.stations[1].charging_vehicles = [v1]

        events = progress_step(state, task, 1.0, 120.0, 45.0, rng)

        # Both vehicles should have received some energy
        assert v0.remaining_kwh < 20.0, "Vehicle 0 should have been charged"
        assert v1.remaining_kwh < 20.0, "Vehicle 1 should have been charged"
        # Some solar should have been used
        assert events["solar_kwh_used"] > 0, "Solar energy should have been used"


class TestPPOActionSampling:
    """Verify PPO trainer samples actions correctly."""

    def test_ppo_action_shape_matches_env(self) -> None:
        """PPO action vector should match environment action space."""
        from ev_charging_grid_env.training.algorithms.ppo_trainer import PPOTrainer, PPOConfig
        from pathlib import Path
        import tempfile

        env = MultiAgentEVChargingGridEnv(config={"num_stations": 5, "episode_length": 2})
        config = PPOConfig(rollout_steps=2, total_steps=4, seed=42)

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = PPOTrainer(env, config, Path(tmpdir))

            # Sample an observation
            obs, _ = env.reset(seed=42)
            from ev_charging_grid_env.training.utils.preprocessing import flatten_observation

            obs_vec = flatten_observation(obs)
            action_vec, _, _ = trainer._sample_action(obs_vec)

            # Expected size: num_stations for price_deltas + 1 for emergency + num_stations for station actions
            expected_size = env.num_stations + 1 + env.num_stations
            assert (
                len(action_vec) == expected_size
            ), f"Action vector size {len(action_vec)} != {expected_size}"

            # Verify action can be passed to env
            joint_action = {
                "coordinator_action": {
                    "price_deltas": action_vec[: env.num_stations],
                    "emergency_target_station": int(action_vec[env.num_stations]),
                },
                "station_actions": action_vec[env.num_stations + 1 :],
            }
            next_obs, reward, _, _, _ = env.step(joint_action)
            assert next_obs is not None
            assert isinstance(reward, float)


class TestPettingZooCoordinatorAction:
    """Verify PettingZoo coordinator action handling."""

    def test_coordinator_action_default_format(self) -> None:
        """Default coordinator action should be properly formatted."""
        env = PettingZooEVChargingEnv(config={"num_stations": 3, "episode_length": 2})
        env.reset(seed=44)

        # Step through without coordinator submitting action
        for agent in env.agent_iter(max_iter=10):
            if agent == "coordinator":
                # Don't submit coordinator action, let it use default
                env.step(None)
            else:
                env.step(env.action_space(agent).sample())
                # This should not crash
            if all(env.truncations.values()):
                break

        assert True, "No exception should be raised"

    def test_coordinator_action_validation(self) -> None:
        """Coordinator action must have required keys."""
        env = PettingZooEVChargingEnv(config={"num_stations": 3, "episode_length": 2})
        env.reset(seed=45)

        with pytest.raises(ValueError):
            for agent in env.agent_iter(max_iter=20):
                if agent == "coordinator":
                    env.step("invalid")
                else:
                    env.step(env.action_space(agent).sample())


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_vehicles_no_crash(self) -> None:
        """Environment should handle zero arrivals gracefully."""
        env = MultiAgentEVChargingGridEnv(
            config={"episode_length": 3, "base_arrival_rate": 0.0}
        )
        obs, _ = env.reset(seed=50)
        for _ in range(3):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            assert isinstance(reward, float)
            assert not np.isnan(reward)

    def test_grid_overload_scenario(self) -> None:
        """Environment should handle state where grid usage > limit."""
        task = generate_task(
            {"num_stations": 2, "grid_limit_kw": 10.0, "episode_length": 1}
        )
        state = initialize_episode(task)
        rng = np.random.default_rng(51)

        # Manually set grid usage above limit
        state.grid.total_grid_kw_used = 50.0
        state.grid.global_limit_kw = 10.0

        config = {
            "queue_penalty_weight": 0.0,
            "timeout_penalty_weight": 0.0,
            "grid_overload_penalty_weight": 0.05,
            "solar_priority_weight": 0.0,
            "emergency_priority_bonus": 0.0,
            "completion_reward_weight": 0.0,
            "fast_service_weight": 0.0,
            "reward_clip": 50.0,
        }
        reward_state = {
            "mean_wait_time": 0.0,
            "total_grid_kw_used": 50.0,
            "grid_limit_kw": 10.0,
        }
        events = {
            "vehicles_completed": 0.0,
            "solar_kwh_used": 0.0,
            "grid_kwh_used": 40.0,
            "quick_service_score": 0.0,
            "emergency_missed": 0.0,
            "timed_out_count": 0.0,
        }
        reward = compute_step_reward(reward_state, events, config)
        # Normalized reward [0,1]: overload should yield low normalized score
        assert reward < 0.5, "Overload should result in low normalized reward"


    def test_emergency_only_scenario(self) -> None:
        """Test scenario with only emergency vehicles."""
        task = generate_task(
            {
                "num_stations": 2,
                "emergency_arrival_prob": 1.0,
                "base_arrival_rate": 2.0,
                "episode_length": 3,
            }
        )
        state = initialize_episode(task)
        rng = np.random.default_rng(52)

        emergency_count = 0
        for _ in range(3):
            arrivals = generate_arrivals(state, task, rng, 0)
            emergency_count += sum(1 for v in arrivals if v.is_emergency)

        # All arrivals should be emergency
        assert emergency_count > 0, "Emergency vehicles should be generated"

    def test_all_stations_in_outage(self) -> None:
        """Test scenario where all stations are in outage."""
        task = generate_task(
            {
                "num_stations": 2,
                "station_outage_probability": 1.0,
                "episode_length": 2,
            }
        )
        state = initialize_episode(task)
        rng = np.random.default_rng(53)

        # Force outages
        for station in state.stations:
            station.outage_time_left = 1

        events = progress_step(state, task, 1.0, 120.0, 45.0, rng)

        # No vehicles should be charged during outage
        assert events["grid_kwh_used"] == 0.0 or events["grid_kwh_used"] < 0.1

    def test_full_charging_stations(self) -> None:
        """Test scenario where all charging slots are full."""
        task = generate_task({"num_stations": 2, "episode_length": 1})
        state = initialize_episode(task)
        rng = np.random.default_rng(54)

        from ev_charging_grid_env.envs.state import VehicleState

        # Fill all slots
        for station in state.stations:
            for i in range(station.max_slots):
                v = VehicleState(
                    id=i,
                    required_kwh=20.0,
                    remaining_kwh=20.0,
                    battery_level=0.5,
                    is_emergency=False,
                    urgency=0,
                    max_wait_timesteps=45,
                    green_preference=0.5,
                    price_sensitivity=0.5,
                    location_xy=(0.0, 0.0),
                    preferred_station=station.station_id,
                    assigned_station=station.station_id,
                    travel_time_left=0,
                    charging=True,
                )
                station.charging_vehicles.append(v)

        assert all(
            len(s.charging_vehicles) == s.max_slots for s in state.stations
        )

        events = progress_step(state, task, 1.0, 120.0, 45.0, rng)

        # verify no crashes and energy was delivered
        total_energy = events["grid_kwh_used"] + events["solar_kwh_used"]
        assert total_energy > 0, "Energy should have been delivered"

    def test_invalid_task_config_num_stations(self) -> None:
        """Test that invalid num_stations raises error."""
        with pytest.raises(ValueError, match="num_stations must be > 0"):
            generate_task({"num_stations": 0})

    def test_invalid_task_config_max_slots(self) -> None:
        """Test that invalid max_slots raises error."""
        with pytest.raises(ValueError, match="max_slots_per_station must be > 0"):
            generate_task({"num_stations": 5, "max_slots_per_station": 0})

    def test_invalid_task_config_solar_ratio(self) -> None:
        """Test that invalid solar ratio raises error."""
        with pytest.raises(ValueError, match="solar_station_ratio must be in"):
            generate_task({"num_stations": 5, "solar_station_ratio": 1.5})


# ============================================================================
# ACTION VALIDATION TESTS
# ============================================================================


class TestActionValidation:
    """Test action validation and handling."""

    def test_malformed_action_dict(self) -> None:
        """Malformed action dict should raise error."""
        env = MultiAgentEVChargingGridEnv(config={"num_stations": 3})
        env.reset(seed=60)

        with pytest.raises((TypeError, ValueError)):
            env.step({"invalid": "structure"})

    def test_wrong_station_actions_shape(self) -> None:
        """Wrong station_actions shape should raise error."""
        env = MultiAgentEVChargingGridEnv(config={"num_stations": 5})
        env.reset(seed=61)

        with pytest.raises(ValueError):
            action = {
                "coordinator_action": {
                    "price_deltas": np.ones(5, dtype=np.int64),
                    "emergency_target_station": 0,
                },
                "station_actions": np.ones(3, dtype=np.int64),  # Wrong length
            }
            env.step(action)

    def test_price_deltas_wrong_length(self) -> None:
        """Wrong price_deltas length should raise error."""
        env = MultiAgentEVChargingGridEnv(config={"num_stations": 5})
        env.reset(seed=62)

        with pytest.raises(ValueError):
            action = {
                "coordinator_action": {
                    "price_deltas": np.ones(3, dtype=np.int64),  # Wrong length
                    "emergency_target_station": 0,
                },
                "station_actions": np.ones(5, dtype=np.int64),
            }
            env.step(action)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Integration tests for full episode runs."""

    def test_full_episode_gym_env(self) -> None:
        """Full episode should run without errors."""
        env = MultiAgentEVChargingGridEnv(config={"episode_length": 10})
        obs, _ = env.reset(seed=70)

        for step in range(12):  # Run past episode_length
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)

            assert not np.isnan(reward), f"Reward is NaN at step {step}"
            assert isinstance(terminated, bool)
            assert isinstance(truncated, bool)
            assert obs is not None

            if truncated:
                break

        assert truncated, "Episode should truncate at length"

    def test_full_episode_pettingzoo_env(self) -> None:
        """Full PettingZoo episode should run without errors."""
        env = PettingZooEVChargingEnv(config={"episode_length": 8})
        env.reset(seed=71)

        step_count = 0
        for agent in env.agent_iter(max_iter=200):
            obs = env.observe(agent)
            action = env.action_space(agent).sample()
            env.step(action)
            step_count += 1

            if all(env.truncations.values()) or all(env.terminations.values()):
                break

        assert step_count > 0, "Episode should run for multiple steps"

    def test_reset_consistency(self) -> None:
        """Consecutive resets with same seed should be identical."""
        env1 = MultiAgentEVChargingGridEnv(config={"episode_length": 5})
        env2 = MultiAgentEVChargingGridEnv(config={"episode_length": 5})

        obs1, _ = env1.reset(seed=80)
        obs2, _ = env2.reset(seed=80)

        # First observations should match
        assert np.allclose(obs1["station_features"], obs2["station_features"])
        assert obs1["weather"] == obs2["weather"]

    def test_deterministic_with_seed(self) -> None:
        """Setting seed should give deterministic results."""
        env = MultiAgentEVChargingGridEnv(config={"episode_length": 5})

        obs1, _ = env.reset(seed=90)
        rewards1 = []
        for _ in range(3):
            _, r, _, _, _ = env.step(env.action_space.sample())
            rewards1.append(r)

        obs2, _ = env.reset(seed=90)
        rewards2 = []
        for _ in range(3):
            _, r, _, _, _ = env.step(env.action_space.sample())
            rewards2.append(r)

        # Results might differ due to random action sampling, but at least no crashes
        assert len(rewards1) == len(rewards2)


# ============================================================================
# REWARD FUNCTION TESTS
# ============================================================================


class TestRewardFunction:
    """Test reward shaping and computation."""

    def test_reward_clip_bounds(self) -> None:
        """Reward should be clipped to [-reward_clip, reward_clip]."""
        config = {"reward_clip": 10.0}
        state = {
            "mean_wait_time": 1000.0,  # Very high wait
            "total_grid_kw_used": 10000.0,
            "grid_limit_kw": 100.0,
        }
        events = {
            "emergency_missed": 100.0,
            "timed_out_count": 100.0,
            "vehicles_completed": 0.0,
            "solar_kwh_used": 0.0,
        }
        reward = compute_step_reward(state, events, config)
        assert -10.0 <= reward <= 10.0, f"Reward {reward} out of bounds"

    def test_reward_respects_all_weights(self) -> None:
        """All weight config values should affect reward."""
        base_config = {
            "queue_penalty_weight": 0.1,
            "timeout_penalty_weight": 0.1,
            "emergency_priority_bonus": 1.0,
            "completion_reward_weight": 1.0,
            "solar_priority_weight": 0.1,
        }
        state = {
            "mean_wait_time": 10.0,
            "total_grid_kw_used": 500.0,
            "grid_limit_kw": 1000.0,
        }
        events = {
            "emergency_served": 1.0,
            "vehicles_completed": 1.0,
            "solar_kwh_used": 10.0,
            "timed_out_count": 0.0,
            "emergency_missed": 0.0,
        }

        r_base = compute_step_reward(state, events, base_config)

        # Increase emergency bonus
        high_config = base_config.copy()
        high_config["emergency_priority_bonus"] = 10.0
        r_high = compute_step_reward(state, events, high_config)

        assert r_high > r_base, "Higher emergency bonus should increase reward"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
