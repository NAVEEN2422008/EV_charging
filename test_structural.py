"""Test to verify environment works and can be imported correctly.

This tests:
1. Environment can be imported from the entrypoint
2. reset() works without errors  
3. step() works without errors
4. All returns are correct types
5. No crashes on extended runs
"""

import sys
import traceback


def test_environment_import():
    """Test that environment can be imported from entrypoint."""
    try:
        from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
        print("✅ Environment import successful")
        return MultiAgentEVChargingGridEnv
    except Exception as e:
        print(f"❌ Environment import failed: {e}")
        traceback.print_exc()
        return None


def test_environment_instantiation(env_class):
    """Test that environment can be instantiated."""
    try:
        env = env_class()
        print("✅ Environment instantiation successful")
        return env
    except Exception as e:
        print(f"❌ Environment instantiation failed: {e}")
        traceback.print_exc()
        return None


def test_environment_reset(env):
    """Test that reset() works correctly."""
    try:
        obs, info = env.reset(seed=42)
        
        # Check types
        assert isinstance(obs, dict), f"Observation should be dict, got {type(obs)}"
        assert isinstance(info, dict), f"Info should be dict, got {type(info)}"
        
        # Check observation keys
        assert "station_features" in obs, "Missing station_features in observation"
        assert "queue_lengths" in obs, "Missing queue_lengths in observation"
        
        print("✅ Environment reset successful")
        return True, obs
    except Exception as e:
        print(f"❌ Environment reset failed: {e}")
        traceback.print_exc()
        return False, None


def test_environment_step(env, obs):
    """Test that step() works correctly."""
    try:
        action = {
            "coordinator_action": {
                "price_deltas": [1] * env.num_stations,
                "emergency_target_station": 0,
            },
            "station_actions": [0] * env.num_stations,
        }
        
        result = env.step(action)
        
        # Check return value is 5-tuple
        assert len(result) == 5, f"step() should return 5-tuple, got {len(result)}"
        
        obs, reward, terminated, truncated, info = result
        
        # Check types
        assert isinstance(obs, dict), f"Observation should be dict, got {type(obs)}"
        assert isinstance(reward, (int, float)), f"Reward should be numeric, got {type(reward)}"
        assert isinstance(terminated, bool), f"Terminated should be bool, got {type(terminated)}"
        assert isinstance(truncated, bool), f"Truncated should be bool, got {type(truncated)}"
        assert isinstance(info, dict), f"Info should be dict, got {type(info)}"
        
        # Check no NaN/Inf
        import math
        assert not math.isnan(reward), "Reward is NaN"
        assert not math.isinf(reward), "Reward is Inf"
        
        print("✅ Environment step successful")
        return True
    except Exception as e:
        print(f"❌ Environment step failed: {e}")
        traceback.print_exc()
        return False


def test_environment_extended(env):
    """Test that environment runs for multiple steps without crashing."""
    try:
        env.reset(seed=42)
        
        for step_num in range(50):
            action = {
                "coordinator_action": {
                    "price_deltas": [1] * env.num_stations,
                    "emergency_target_station": 0,
                },
                "station_actions": [0] * env.num_stations,
            }
            
            obs, reward, terminated, truncated, info = env.step(action)
            
            if step_num % 10 == 0:
                print(f"  Step {step_num}: reward={reward:.2f}")
            
            if terminated or truncated:
                print(f"  Episode ended at step {step_num}")
                break
        
        print("✅ Environment extended run successful")
        return True
    except Exception as e:
        print(f"❌ Environment extended run failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("  ENVIRONMENT STRUCTURAL VALIDATION")
    print("="*70 + "\n")
    
    # Test 1: Import
    print("[1/5] Testing environment import...")
    env_class = test_environment_import()
    if not env_class:
        print("\n❌ CRITICAL: Cannot import environment")
        return 1
    
    # Test 2: Instantiation
    print("\n[2/5] Testing environment instantiation...")
    env = test_environment_instantiation(env_class)
    if not env:
        print("\n❌ CRITICAL: Cannot instantiate environment")
        return 1
    
    # Test 3: Reset
    print("\n[3/5] Testing environment reset...")
    success, obs = test_environment_reset(env)
    if not success:
        print("\n❌ CRITICAL: Reset failed")
        return 1
    
    # Test 4: Single step
    print("\n[4/5] Testing environment step...")
    success = test_environment_step(env, obs)
    if not success:
        print("\n❌ CRITICAL: Step failed")
        return 1
    
    # Test 5: Extended run
    print("\n[5/5] Testing extended environment run...")
    success = test_environment_extended(env)
    if not success:
        print("\n❌ CRITICAL: Extended run failed")
        return 1
    
    print("\n" + "="*70)
    print("  ✅ ALL STRUCTURAL TESTS PASSED")
    print("="*70 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
