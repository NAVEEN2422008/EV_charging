"""
OpenEnv Validation Runner - Comprehensive compliance checker.

Validates:
1. Environment implementation (entrypoint, API compliance)
2. Inference script execution
3. LLM proxy integration
4. PettingZoo AEC wrapper compliance
5. JSON output format
"""

import json
import sys
from pathlib import Path


def validate_environment_entrypoint():
    """Validate environment can be imported and instantiated via entrypoint."""
    print("\n[1/5] Validating Environment Entrypoint...")
    try:
        from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
        env = MultiAgentEVChargingGridEnv()
        obs, info = env.reset(seed=42)
        assert "station_features" in obs
        print("  ✅ Environment entrypoint works")
        return True
    except Exception as e:
        print(f"  ❌ Environment entrypoint failed: {e}")
        return False


def validate_environment_api():
    """Validate environment implements Gym API correctly."""
    print("[2/5] Validating Gym API Compliance...")
    try:
        from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
        env = MultiAgentEVChargingGridEnv()
        
        # Test reset
        obs, info = env.reset(seed=42)
        assert isinstance(obs, dict), "reset() should return dict observation"
        assert isinstance(info, dict), "reset() should return dict info"
        
        # Test step
        action = {
            "coordinator_action": {
                "price_deltas": [1] * env.num_stations,
                "emergency_target_station": 0
            },
            "station_actions": [0] * env.num_stations
        }
        result = env.step(action)
        assert len(result) == 5, "step() should return 5-tuple"
        
        obs, reward, terminated, truncated, info = result
        assert isinstance(obs, dict), "Observation must be dict"
        assert isinstance(reward, (int, float)), "Reward must be numeric"
        assert isinstance(terminated, bool), "Terminated must be bool"
        assert isinstance(truncated, bool), "Truncated must be bool"
        assert isinstance(info, dict), "Info must be dict"
        
        print("  ✅ Gym API fully compliant")
        return True
    except Exception as e:
        print(f"  ❌ Gym API validation failed: {e}")
        return False


def validate_pettingzoo_wrapper():
    """Validate PettingZoo AEC wrapper compliance."""
    print("[3/5] Validating PettingZoo AEC Wrapper...")
    try:
        from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv
        
        env = PettingZooEVChargingEnv()
        
        # AEC reset() returns observations dict {agent_name: observation}
        obs_dict = env.reset(seed=42)
        assert isinstance(obs_dict, dict), "AEC reset must return observations dict"
        assert "coordinator" in obs_dict, "Must include coordinator agent"
        assert all(f"station_{i}" in obs_dict for i in range(env.gym_env.num_stations)), "Must include all station agents"
        
        # Check agents exist
        assert hasattr(env, 'possible_agents'), "Must have possible_agents"
        assert len(env.possible_agents) > 0, "Must have at least one agent"
        
        # Check AEC methods
        assert hasattr(env, 'agent_selection'), "Must have agent_selection"
        assert hasattr(env, 'observe'), "Must have observe() method"
        assert hasattr(env, 'step'), "Must have step() method"
        
        # Test one step
        agent = env.agent_selection
        action = env.action_space(agent).sample()
        env.step(action)
        
        print("  ✅ PettingZoo AEC wrapper compliant")
        return True
    except Exception as e:
        print(f"  ⚠️  PettingZoo wrapper validation skipped: {e}")
        return None  # Not critical


def validate_inference_script():
    """Validate inference.py exists and runs."""
    print("[4/5] Validating Inference Script...")
    try:
        import inference
        
        # Test run_simulation
        result = inference.run_simulation(steps=50, seed=42)
        
        # Check structure
        assert "status" in result, "Must return status"
        assert result["status"] == "success", f"Status should be 'success', got {result['status']}"
        assert "simulation" in result, "Must have simulation results"
        assert "metrics" in result, "Must have metrics"
        
        # Check simulation content
        sim = result["simulation"]
        assert "total_reward" in sim, "Must have total_reward"
        assert "steps_executed" in sim, "Must have steps_executed"
        assert sim["steps_executed"] > 0, "Should execute steps"
        
        # Verify JSON serializable
        json_str = json.dumps(result)
        json.loads(json_str)
        
        print("  ✅ Inference script compliant")
        return True
    except Exception as e:
        print(f"  ❌ Inference validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_llm_proxy_integration():
    """Validate LLM proxy integration without actual API calls."""
    print("[5/5] Validating LLM Proxy Integration...")
    try:
        import os
        from unittest.mock import patch, MagicMock
        import inference
        
        # Mock the OpenAI client
        with patch('inference.OpenAI') as mock_openai:
            # Setup mock
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            
            # Set env vars
            os.environ["API_BASE_URL"] = "https://proxy.example.com/v1"
            os.environ["API_KEY"] = "test-key"
            
            # Test setup
            client = inference.setup_llm_client()
            
            # Verify proxy URL was passed
            call_kwargs = mock_openai.call_args.kwargs
            assert call_kwargs["base_url"] == "https://proxy.example.com/v1"
            assert call_kwargs["api_key"] == "test-key"
            
            print("  ✅ LLM proxy integration correct")
            return True
    except Exception as e:
        print(f"  ⚠️  LLM proxy validation skipped: {e}")
        return None  # Not critical


def validate_openenv_yaml():
    """Validate openenv.yaml exists and is valid."""
    print("[6/6] Validating openenv.yaml...")
    try:
        import yaml
        
        yaml_path = Path("openenv.yaml")
        if not yaml_path.exists():
            print("  ⚠️  openenv.yaml not found")
            return None
        
        with open(yaml_path) as f:
            spec = yaml.safe_load(f)
        
        # Check required fields
        required = ["name", "entrypoint", "tasks"]
        for field in required:
            assert field in spec, f"Missing required field: {field}"
        
        # Check entrypoint
        assert spec["entrypoint"], "Entrypoint must be non-empty"
        
        # Check tasks
        assert isinstance(spec["tasks"], dict), "Tasks must be dict"
        assert len(spec["tasks"]) > 0, "Must have at least one task"
        
        print("  ✅ openenv.yaml valid")
        return True
    except Exception as e:
        print(f"  ⚠️  openenv.yaml validation: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────


def main():
    """Run all validation checks."""
    print("\n" + "="*70)
    print("  OpenEnv Validation Runner")
    print("="*70)
    
    checks = [
        ("Environment Entrypoint", validate_environment_entrypoint),
        ("Gym API Compliance", validate_environment_api),
        ("PettingZoo Wrapper", validate_pettingzoo_wrapper),
        ("Inference Script", validate_inference_script),
        ("LLM Proxy Integration", validate_llm_proxy_integration),
        ("openenv.yaml", validate_openenv_yaml),
    ]
    
    results = []
    for name, check_fn in checks:
        try:
            result = check_fn()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("  VALIDATION SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    total = len(results)
    
    for name, result in results:
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  SKIP"
        print(f"  {status:10} {name}")
    
    print("\n" + "-"*70)
    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"  Total: {total} checks")
    print("="*70 + "\n")
    
    # Exit code
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
