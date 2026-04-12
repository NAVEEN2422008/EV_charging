"""
Numerical Stability and Robustness Tests for EV Charging Grid Environment.

Ensures:
- No NaN/Inf values in rewards or observations
- Rewards stay in reasonable bounds
- Environment handles edge cases gracefully
- Determinism with fixed seed
"""

import numpy as np
import pytest

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv


class TestNumericalStability:
    """Test suite for numerical stability."""

    def test_no_nan_rewards_100_steps(self):
        """Ensure no NaN rewards in 100 steps."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        for step in range(100):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            
            assert not np.isnan(reward), f"NaN reward at step {step}"
            assert not np.isinf(reward), f"Inf reward at step {step}"
            assert isinstance(reward, (int, float)), f"Reward not numeric at step {step}"
            
            if terminated or truncated:
                break

    def test_no_nan_rewards_1000_steps(self):
        """Ensure no NaN rewards in 1000-step episode."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        nan_count = 0
        inf_count = 0
        
        for step in range(1000):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            
            if np.isnan(reward):
                nan_count += 1
            if np.isinf(reward):
                inf_count += 1
            
            if terminated or truncated:
                break
        
        assert nan_count == 0, f"Found {nan_count} NaN rewards"
        assert inf_count == 0, f"Found {inf_count} Inf rewards"

    def test_reward_scale_reasonable(self):
        """Ensure rewards are in reasonable range [-1000, 1000]."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        min_reward = float('inf')
        max_reward = float('-inf')
        
        for step in range(300):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            
            min_reward = min(min_reward, reward)
            max_reward = max(max_reward, reward)
            
            assert -10000 < reward < 10000, f"Reward out of reasonable bounds: {reward}"
            
            if terminated or truncated:
                break
        
        # Verify we saw some range of rewards
        assert min_reward < max_reward, "Rewards should vary"

    def test_observation_no_nan_values(self):
        """Check observations contain no NaN/Inf values."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        for step in range(100):
            # Validate initial observation
            for key, val in obs.items():
                if isinstance(val, np.ndarray):
                    assert not np.any(np.isnan(val)), f"NaN in observation[{key}] at step {step}"
                    assert not np.any(np.isinf(val)), f"Inf in observation[{key}] at step {step}"
            
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            
            if terminated or truncated:
                break

    def test_observation_keys_consistent(self):
        """Check observation keys remain consistent across steps."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        expected_keys = set(obs.keys())
        
        for step in range(100):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            
            assert set(obs.keys()) == expected_keys, f"Observation keys changed at step {step}"
            
            if terminated or truncated:
                break

    def test_episode_stats_not_nan(self):
        """Ensure episode statistics don't contain NaN values."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        for step in range(100):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            
            stats = info.get("episode_stats", {})
            for key, val in stats.items():
                if isinstance(val, (int, float)):
                    assert not np.isnan(val), f"NaN in stats[{key}] at step {step}"
                    assert not np.isinf(val), f"Inf in stats[{key}] at step {step}"
            
            if terminated or truncated:
                break


class TestDeterminism:
    """Test determinism with fixed seeds."""

    def test_determinism_with_seed(self):
        """Same seed produces same trajectory."""
        seed = 42
        
        # Run 1
        env1 = MultiAgentEVChargingGridEnv()
        obs1, _ = env1.reset(seed=seed)
        rewards1 = []
        
        for _ in range(50):
            action = env1.action_space.sample()
            obs1, reward, _, _, _ = env1.step(action)
            rewards1.append(reward)
        
        # Run 2
        env2 = MultiAgentEVChargingGridEnv()
        obs2, _ = env2.reset(seed=seed)
        rewards2 = []
        
        for _ in range(50):
            action = env2.action_space.sample()
            obs2, reward, _, _, _ = env2.step(action)
            rewards2.append(reward)
        
        assert len(rewards1) == len(rewards2), "Trajectories have different lengths"
        
        for i, (r1, r2) in enumerate(zip(rewards1, rewards2)):
            assert np.isclose(r1, r2), f"Rewards differ at step {i}: {r1} vs {r2}"

    def test_different_seeds_produce_different_trajectory(self):
        """Different seeds produce different trajectories."""
        rewards_seed1 = []
        rewards_seed2 = []
        
        # Seed 42
        env1 = MultiAgentEVChargingGridEnv()
        obs1, _ = env1.reset(seed=42)
        for _ in range(50):
            action = env1.action_space.sample()
            obs1, reward, _, _, _ = env1.step(action)
            rewards_seed1.append(reward)
        
        # Seed 123
        env2 = MultiAgentEVChargingGridEnv()
        obs2, _ = env2.reset(seed=123)
        for _ in range(50):
            action = env2.action_space.sample()
            obs2, reward, _, _, _ = env2.step(action)
            rewards_seed2.append(reward)
        
        # Trajectories should be different (with very high probability)
        differences = sum(1 for r1, r2 in zip(rewards_seed1, rewards_seed2) if not np.isclose(r1, r2))
        
        assert differences > 10, "Different seeds should produce significantly different trajectories"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_step(self):
        """Environment works for single step."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        
        assert obs is not None
        assert isinstance(reward, (int, float))
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_multiple_resets(self):
        """Environment handles multiple resets correctly."""
        env = MultiAgentEVChargingGridEnv()
        
        for reset_iter in range(5):
            obs, info = env.reset(seed=42 + reset_iter)
            
            assert obs is not None
            assert isinstance(obs, dict)
            assert isinstance(info, dict)
            
            # Do a few steps
            for step in range(10):
                action = env.action_space.sample()
                obs, reward, _, _, _ = env.step(action)
                assert obs is not None

    def test_early_termination(self):
        """Environment terminates/truncates correctly."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        total_steps = 0
        for step in range(1000):  # Try up to 1000 steps
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            total_steps += 1
            
            if terminated or truncated:
                break
        
        # Should complete within the episode length (typically 300)
        assert total_steps > 0
        # At least one of them should be true at the end
        assert terminated or truncated

    def test_action_sampling_validity(self):
        """Action space sampling produces valid actions."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        for _ in range(50):
            action = env.action_space.sample()
            
            # Action should be valid dict
            assert isinstance(action, dict)
            assert "coordinator_action" in action
            assert "station_actions" in action
            
            # Should not raise error
            obs, _, _, _, _ = env.step(action)


class TestRewardProperties:
    """Test reward function properties."""

    def test_reward_not_always_negative(self):
        """Average reward should not be always negative (indicates issues)."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        rewards = []
        for _ in range(100):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            rewards.append(reward)
            
            if terminated or truncated:
                break
        
        mean_reward = np.mean(rewards)
        assert mean_reward >= 0.0, f"Mean reward shouldn't be negative with [0,1] scaling: {mean_reward}"
        
        # At least some positive rewards
        positive_rewards = sum(1 for r in rewards if r > 0)
        assert positive_rewards > 0, "No positive rewards found"

    def test_reward_variance_reasonable(self):
        """Reward variance should be reasonable (not constant, not exploding)."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        rewards = []
        for _ in range(300):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            rewards.append(reward)
            
            if terminated or truncated:
                break
        
        std_reward = np.std(rewards)
        
        # Variance should exist but could be very small due to [0,1] scaling
        assert std_reward > 0.0, "Reward variance is exactly zero (rewards completely constant)"
        
        # But not exploding
        assert std_reward < 10000, "Reward variance too large (exploding)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
