"""
Comprehensive tests for OpenEnv validation.

Tests cover:
- Environment API compliance
- Inference execution
- LLM proxy integration
- Edge cases
"""

import json
import os
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv


# ──────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT API TESTS
# ──────────────────────────────────────────────────────────────────────────────


def test_environment_initialization():
    """Test environment can be created without errors."""
    env = MultiAgentEVChargingGridEnv()
    assert env is not None
    assert env.num_stations > 0
    assert env.observation_space is not None
    assert env.action_space is not None


def test_environment_reset():
    """Test reset returns correct tuple."""
    env = MultiAgentEVChargingGridEnv()
    obs, info = env.reset(seed=42)
    
    # Check return types
    assert isinstance(obs, dict), "Observation must be dict"
    assert isinstance(info, dict), "Info must be dict"
    
    # Check observation keys
    assert "station_features" in obs
    assert "queue_lengths" in obs
    assert "time_context" in obs


def test_environment_step():
    """Test step returns correct 5-tuple."""
    env = MultiAgentEVChargingGridEnv()
    obs, _ = env.reset(seed=42)
    
    # Create valid action
    action = {
        "coordinator_action": {
            "price_deltas": [1] * env.num_stations,
            "emergency_target_station": 0
        },
        "station_actions": [0] * env.num_stations
    }
    
    # Execute step
    result = env.step(action)
    
    # Check 5-tuple
    assert len(result) == 5, "step() must return 5-tuple"
    obs, reward, terminated, truncated, info = result
    
    # Type checks
    assert isinstance(obs, dict), "Observation must be dict"
    assert isinstance(reward, (int, float)), "Reward must be numeric"
    assert isinstance(terminated, bool), "Terminated must be bool"
    assert isinstance(truncated, bool), "Truncated must be bool"
    assert isinstance(info, dict), "Info must be dict"


def test_environment_multiple_steps():
    """Test environment runs 100 steps without crash."""
    env = MultiAgentEVChargingGridEnv()
    obs, _ = env.reset(seed=42)
    
    total_reward = 0.0
    step_count = 0
    
    for _ in range(100):
        # Random action
        action = {
            "coordinator_action": {
                "price_deltas": [1] * env.num_stations,
                "emergency_target_station": 0
            },
            "station_actions": [0] * env.num_stations
        }
        
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        step_count += 1
        
        # Check for NaN/Inf
        assert not float('inf') == reward and not float('-inf') == reward, \
            f"Reward is inf at step {step_count}"
        assert reward == reward, f"Reward is NaN at step {step_count}"
        
        if terminated or truncated:
            break
    
    assert step_count == 100, f"Expected 100 steps, got {step_count}"
    assert total_reward != float('inf') and total_reward != float('-inf'), \
        "Total reward is infinite"
    assert total_reward == total_reward, "Total reward is NaN"


def test_environment_deterministic():
    """Test environment is deterministic with same seed."""
    env1 = MultiAgentEVChargingGridEnv()
    env2 = MultiAgentEVChargingGridEnv()
    
    obs1, _ = env1.reset(seed=42)
    obs2, _ = env2.reset(seed=42)
    
    action = {
        "coordinator_action": {
            "price_deltas": [1] * env1.num_stations,
            "emergency_target_station": 0
        },
        "station_actions": [0] * env1.num_stations
    }
    
    result1 = env1.step(action)
    result2 = env2.step(action)
    
    # Rewards should be identical
    assert result1[1] == result2[1], "Rewards differ with same seed"


# ──────────────────────────────────────────────────────────────────────────────
# INFERENCE TESTS
# ──────────────────────────────────────────────────────────────────────────────


def test_inference_import():
    """Test inference module can be imported."""
    try:
        import inference
        assert hasattr(inference, 'run')
        assert hasattr(inference, 'run_simulation')
        assert hasattr(inference, 'call_llm_analyze')
    except ImportError as e:
        pytest.skip(f"Inference module not available: {e}")


def test_inference_simulation_runs():
    """Test simulation runs without errors."""
    try:
        from inference import run_simulation
        result = run_simulation(steps=50, seed=42)
        
        assert result.get("status") == "success"
        assert "simulation" in result
        assert "metrics" in result
        assert result["simulation"]["total_reward"] is not None
    except ImportError:
        pytest.skip("Inference module not available")


def test_inference_json_output():
    """Test inference outputs valid JSON."""
    try:
        from inference import run_simulation
        result = run_simulation(steps=50, seed=42)
        
        # Should be JSON-serializable
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        
        assert parsed == result
    except ImportError:
        pytest.skip("Inference module not available")


# ──────────────────────────────────────────────────────────────────────────────
# LLM PROXY TESTS
# ──────────────────────────────────────────────────────────────────────────────


def test_llm_client_setup_requires_env_vars():
    """Test LLM client setup fails without environment variables."""
    try:
        from inference import setup_llm_client
        
        # Remove env vars if present
        old_base = os.environ.pop("API_BASE_URL", None)
        old_key = os.environ.pop("API_KEY", None)
        
        try:
            with pytest.raises(ValueError, match="API_BASE_URL"):
                setup_llm_client()
        finally:
            # Restore
            if old_base:
                os.environ["API_BASE_URL"] = old_base
            if old_key:
                os.environ["API_KEY"] = old_key
                
    except ImportError:
        pytest.skip("Inference module not available")


@patch('inference.OpenAI')
def test_llm_client_uses_proxy_url(mock_openai_class):
    """Test LLM client uses proxy base_url from env."""
    try:
        from inference import setup_llm_client
        
        # Set env vars
        os.environ["API_BASE_URL"] = "https://proxy.example.com/v1"
        os.environ["API_KEY"] = "test-key-123"
        
        try:
            setup_llm_client()
            
            # Check OpenAI was called with proxy URL
            mock_openai_class.assert_called_once()
            call_kwargs = mock_openai_class.call_args.kwargs
            assert call_kwargs["base_url"] == "https://proxy.example.com/v1"
            assert call_kwargs["api_key"] == "test-key-123"
            
        finally:
            # Clean up
            os.environ.pop("API_BASE_URL", None)
            os.environ.pop("API_KEY", None)
            
    except ImportError:
        pytest.skip("Inference module not available")


# ──────────────────────────────────────────────────────────────────────────────
# EDGE CASE TESTS
# ──────────────────────────────────────────────────────────────────────────────


def test_environment_empty_config():
    """Test environment with no config."""
    env = MultiAgentEVChargingGridEnv(config={})
    obs, info = env.reset()
    assert obs is not None


def test_environment_custom_config():
    """Test environment with custom config."""
    config = {
        "base_arrival_rate": 2.0,
        "emergency_arrival_prob": 0.1,
        "episode_length": 100
    }
    env = MultiAgentEVChargingGridEnv(config=config)
    obs, info = env.reset()
    assert obs is not None


def test_environment_invalid_action():
    """Test environment rejects invalid actions."""
    env = MultiAgentEVChargingGridEnv()
    obs, _ = env.reset()
    
    # Invalid action (not dict)
    with pytest.raises(TypeError):
        env.step([1, 2, 3])
    
    # Invalid action (missing keys)
    with pytest.raises(ValueError):
        env.step({"coordinator_action": {}})


def test_environment_large_episode():
    """Test environment can run for 1000 steps."""
    env = MultiAgentEVChargingGridEnv(config={"episode_length": 1000})
    obs, _ = env.reset(seed=42)
    
    for _ in range(1000):
        action = {
            "coordinator_action": {
                "price_deltas": [1] * env.num_stations,
                "emergency_target_station": 0
            },
            "station_actions": [0] * env.num_stations
        }
        obs, _, terminated, truncated, _ = env.step(action)
        
        if terminated or truncated:
            break
    
    assert env.episode_stats["vehicles_seen"] > 0


# ──────────────────────────────────────────────────────────────────────────────
# RUN TESTS
# ──────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
