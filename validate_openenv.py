#!/usr/bin/env python3
"""
OpenEnv Validation Script

Performs comprehensive validation of the EV Charging Grid environment
for OpenEnv Phase 1 compliance.

Validation Checks:
1. ✅ Environment Entrypoint
2. ✅ Gym API Compliance
3. ⚠️ PettingZoo Wrapper (optional)
4. ✅ Inference Script
5. ✅ LLM Proxy Integration
6. ✅ openenv.yaml
"""

import sys
import os
import json
import yaml
from typing import Any, Dict
import importlib.util

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def load_openenv_spec() -> Dict[str, Any]:
    """Load openenv.yaml specification."""
    spec_path = os.path.join(os.path.dirname(__file__), 'openenv.yaml')
    with open(spec_path, 'r') as f:
        return yaml.safe_load(f)

def check_environment_entrypoint(spec: Dict[str, Any]) -> bool:
    """Check 1: Environment Entrypoint."""
    print("🔍 Checking Environment Entrypoint...")

    entrypoint = spec.get('entrypoint', '')
    if not entrypoint:
        print("❌ FAIL: No entrypoint in openenv.yaml")
        return False

    try:
        module_name, class_name = entrypoint.split(':')
        module = importlib.import_module(module_name)
        env_class = getattr(module, class_name)

        # Try to instantiate
        env = env_class()
        print(f"✅ PASS: Environment {entrypoint} instantiated successfully")
        return True
    except Exception as e:
        print(f"❌ FAIL: Environment entrypoint error: {e}")
        return False

def check_gym_api_compliance() -> bool:
    """Check 2: Gym API Compliance."""
    print("🔍 Checking Gym API Compliance...")

    try:
        from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

        env = MultiAgentEVChargingGridEnv()

        # Check required attributes
        required_attrs = ['observation_space', 'action_space', 'reset', 'step']
        for attr in required_attrs:
            if not hasattr(env, attr):
                print(f"❌ FAIL: Missing required attribute: {attr}")
                return False

        # Test reset
        obs, info = env.reset(seed=42)
        if not isinstance(obs, dict) or not isinstance(info, dict):
            print("❌ FAIL: reset() must return (dict, dict)")
            return False

        # Test step
        action = {
            "coordinator_action": {
                "price_deltas": [1] * env.num_stations,
                "emergency_target_station": 0
            },
            "station_actions": [0] * env.num_stations
        }

        result = env.step(action)
        if len(result) != 5:
            print("❌ FAIL: step() must return 5-tuple")
            return False

        obs, reward, terminated, truncated, info = result
        if not isinstance(obs, dict) or not isinstance(reward, (int, float)):
            print("❌ FAIL: Invalid step() return types")
            return False

        print("✅ PASS: Gym API compliance verified")
        return True
    except Exception as e:
        print(f"❌ FAIL: Gym API error: {e}")
        return False

def check_pettingzoo_wrapper() -> bool:
    """Check 3: PettingZoo Wrapper (optional)."""
    print("🔍 Checking PettingZoo Wrapper...")

    try:
        from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVEnv

        env = PettingZooEVEnv()
        obs, info = env.reset(seed=42)

        # Check AEC API
        if not hasattr(env, 'agents'):
            print("❌ FAIL: PettingZoo env missing agents attribute")
            return False

        print("✅ PASS: PettingZoo wrapper available")
        return True
    except ImportError:
        print("⚠️ SKIP: PettingZoo wrapper not available (optional)")
        return True
    except Exception as e:
        print(f"❌ FAIL: PettingZoo wrapper error: {e}")
        return False

def check_inference_script() -> bool:
    """Check 4: Inference Script."""
    print("🔍 Checking Inference Script...")

    try:
        # Import inference module
        spec = importlib.util.spec_from_file_location("inference", "inference.py")
        inference_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inference_module)

        # Check required function
        if not hasattr(inference_module, 'run'):
            print("❌ FAIL: inference.py missing run() function")
            return False

        # Test run function (with minimal steps)
        os.environ['SIMULATION_STEPS'] = '10'
        os.environ['RANDOM_SEED'] = '42'

        result = inference_module.run()

        required_keys = ['status', 'total_reward']
        for key in required_keys:
            if key not in result:
                print(f"❌ FAIL: inference.py result missing key: {key}")
                return False

        if result.get('status') != 'success':
            print(f"❌ FAIL: inference.py status: {result.get('status')}")
            return False

        print("✅ PASS: Inference script functional")
        return True
    except Exception as e:
        print(f"❌ FAIL: Inference script error: {e}")
        return False

def check_llm_proxy_integration() -> bool:
    """Check 5: LLM Proxy Integration."""
    print("🔍 Checking LLM Proxy Integration...")

    try:
        # Import inference module
        spec = importlib.util.spec_from_file_location("inference", "inference.py")
        inference_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inference_module)

        # Check LLM client setup
        if not hasattr(inference_module, 'get_llm_client'):
            print("❌ FAIL: inference.py missing get_llm_client() function")
            return False

        # Test with dummy env vars
        old_vars = {}
        env_vars = ['API_BASE_URL', 'API_KEY', 'HF_TOKEN']
        for var in env_vars:
            old_vars[var] = os.environ.get(var)
            os.environ[var] = 'dummy_value'

        try:
            client = inference_module.get_llm_client()
            print("✅ PASS: LLM proxy integration configured")
            return True
        except Exception as e:
            print(f"❌ FAIL: LLM client setup error: {e}")
            return False
        finally:
            # Restore env vars
            for var, value in old_vars.items():
                if value is None:
                    os.environ.pop(var, None)
                else:
                    os.environ[var] = value

    except Exception as e:
        print(f"❌ FAIL: LLM proxy integration error: {e}")
        return False

def check_openenv_yaml(spec: Dict[str, Any]) -> bool:
    """Check 6: openenv.yaml."""
    print("🔍 Checking openenv.yaml...")

    required_keys = ['name', 'entrypoint', 'tasks']
    for key in required_keys:
        if key not in spec:
            print(f"❌ FAIL: openenv.yaml missing required key: {key}")
            return False

    # Check tasks
    tasks = spec.get('tasks', {})
    if not isinstance(tasks, dict) or len(tasks) < 3:
        print("❌ FAIL: openenv.yaml must have at least 3 tasks")
        return False

    # Check each task has grader
    tasks_with_graders = 0
    for task_name, task_config in tasks.items():
        grader = task_config.get('grader', {})
        if grader and grader.get('type') == 'custom' and grader.get('entrypoint'):
            tasks_with_graders += 1

    if tasks_with_graders < 3:
        print(f"❌ FAIL: Only {tasks_with_graders} tasks with graders, need at least 3")
        return False

    print(f"✅ PASS: openenv.yaml valid with {tasks_with_graders} tasks with graders")
    return True

def main():
    """Run all validation checks."""
    print("🚀 OpenEnv Validation Starting...")
    print("=" * 50)

    # Load spec
    try:
        spec = load_openenv_spec()
    except Exception as e:
        print(f"❌ FAIL: Cannot load openenv.yaml: {e}")
        return 1

    # Run checks
    checks = [
        ("Environment Entrypoint", lambda: check_environment_entrypoint(spec)),
        ("Gym API Compliance", check_gym_api_compliance),
        ("PettingZoo Wrapper", check_pettingzoo_wrapper),
        ("Inference Script", check_inference_script),
        ("LLM Proxy Integration", check_llm_proxy_integration),
        ("openenv.yaml", lambda: check_openenv_yaml(spec)),
    ]

    passed = 0
    total = len(checks)

    for name, check_func in checks:
        try:
            if check_func():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ FAIL: {name} - Unexpected error: {e}")
            print()

    print("=" * 50)
    print(f"Results: {passed} passed, {total - passed} failed")

    if passed == total:
        print("🎉 ALL CHECKS PASSED - Ready for OpenEnv submission!")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Fix issues before submission")
        return 1

if __name__ == "__main__":
    sys.exit(main())#!/usr/bin/env python3
"""
OpenEnv Validation Script

Performs comprehensive validation of the EV Charging Grid environment
for OpenEnv Phase 1 compliance.

Validation Checks:
1. ✅ Environment Entrypoint
2. ✅ Gym API Compliance
3. ⚠️ PettingZoo Wrapper (optional)
4. ✅ Inference Script
5. ✅ LLM Proxy Integration
6. ✅ openenv.yaml
"""

import sys
import os
import json
import yaml
from typing import Any, Dict
import importlib.util

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def load_openenv_spec() -> Dict[str, Any]:
    """Load openenv.yaml specification."""
    spec_path = os.path.join(os.path.dirname(__file__), 'openenv.yaml')
    with open(spec_path, 'r') as f:
        return yaml.safe_load(f)

def check_environment_entrypoint(spec: Dict[str, Any]) -> bool:
    """Check 1: Environment Entrypoint."""
    print("🔍 Checking Environment Entrypoint...")

    entrypoint = spec.get('entrypoint', '')
    if not entrypoint:
        print("❌ FAIL: No entrypoint in openenv.yaml")
        return False

    try:
        module_name, class_name = entrypoint.split(':')
        module = importlib.import_module(module_name)
        env_class = getattr(module, class_name)

        # Try to instantiate
        env = env_class()
        print(f"✅ PASS: Environment {entrypoint} instantiated successfully")
        return True
    except Exception as e:
        print(f"❌ FAIL: Environment entrypoint error: {e}")
        return False

def check_gym_api_compliance() -> bool:
    """Check 2: Gym API Compliance."""
    print("🔍 Checking Gym API Compliance...")

    try:
        from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

        env = MultiAgentEVChargingGridEnv()

        # Check required attributes
        required_attrs = ['observation_space', 'action_space', 'reset', 'step']
        for attr in required_attrs:
            if not hasattr(env, attr):
                print(f"❌ FAIL: Missing required attribute: {attr}")
                return False

        # Test reset
        obs, info = env.reset(seed=42)
        if not isinstance(obs, dict) or not isinstance(info, dict):
            print("❌ FAIL: reset() must return (dict, dict)")
            return False

        # Test step
        action = {
            "coordinator_action": {
                "price_deltas": [1] * env.num_stations,
                "emergency_target_station": 0
            },
            "station_actions": [0] * env.num_stations
        }

        result = env.step(action)
        if len(result) != 5:
            print("❌ FAIL: step() must return 5-tuple")
            return False

        obs, reward, terminated, truncated, info = result
        if not isinstance(obs, dict) or not isinstance(reward, (int, float)):
            print("❌ FAIL: Invalid step() return types")
            return False

        print("✅ PASS: Gym API compliance verified")
        return True
    except Exception as e:
        print(f"❌ FAIL: Gym API error: {e}")
        return False

def check_pettingzoo_wrapper() -> bool:
    """Check 3: PettingZoo Wrapper (optional)."""
    print("🔍 Checking PettingZoo Wrapper...")

    try:
        from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVEnv

        env = PettingZooEVEnv()
        obs, info = env.reset(seed=42)

        # Check AEC API
        if not hasattr(env, 'agents'):
            print("❌ FAIL: PettingZoo env missing agents attribute")
            return False

        print("✅ PASS: PettingZoo wrapper available")
        return True
    except ImportError:
        print("⚠️ SKIP: PettingZoo wrapper not available (optional)")
        return True
    except Exception as e:
        print(f"❌ FAIL: PettingZoo wrapper error: {e}")
        return False

def check_inference_script() -> bool:
    """Check 4: Inference Script."""
    print("🔍 Checking Inference Script...")

    try:
        # Import inference module
        spec = importlib.util.spec_from_file_location("inference", "inference.py")
        inference_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inference_module)

        # Check required function
        if not hasattr(inference_module, 'run'):
            print("❌ FAIL: inference.py missing run() function")
            return False

        # Test run function (with minimal steps)
        os.environ['SIMULATION_STEPS'] = '10'
        os.environ['RANDOM_SEED'] = '42'

        result = inference_module.run()

        required_keys = ['status', 'total_reward']
        for key in required_keys:
            if key not in result:
                print(f"❌ FAIL: inference.py result missing key: {key}")
                return False

        if result.get('status') != 'success':
            print(f"❌ FAIL: inference.py status: {result.get('status')}")
            return False

        print("✅ PASS: Inference script functional")
        return True
    except Exception as e:
        print(f"❌ FAIL: Inference script error: {e}")
        return False

def check_llm_proxy_integration() -> bool:
    """Check 5: LLM Proxy Integration."""
    print("🔍 Checking LLM Proxy Integration...")

    try:
        # Import inference module
        spec = importlib.util.spec_from_file_location("inference", "inference.py")
        inference_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inference_module)

        # Check LLM client setup
        if not hasattr(inference_module, 'get_llm_client'):
            print("❌ FAIL: inference.py missing get_llm_client() function")
            return False

        # Test with dummy env vars
        old_vars = {}
        env_vars = ['API_BASE_URL', 'API_KEY', 'HF_TOKEN']
        for var in env_vars:
            old_vars[var] = os.environ.get(var)
            os.environ[var] = 'dummy_value'

        try:
            client = inference_module.get_llm_client()
            print("✅ PASS: LLM proxy integration configured")
            return True
        except Exception as e:
            print(f"❌ FAIL: LLM client setup error: {e}")
            return False
        finally:
            # Restore env vars
            for var, value in old_vars.items():
                if value is None:
                    os.environ.pop(var, None)
                    os.environ[var] = value

    except Exception as e:
        print(f"❌ FAIL: LLM proxy integration error: {e}")
        return False

def check_openenv_yaml(spec: Dict[str, Any]) -> bool:
    """Check 6: openenv.yaml."""
    print("🔍 Checking openenv.yaml...")

    required_keys = ['name', 'entrypoint', 'tasks']
    for key in required_keys:
        if key not in spec:
            print(f"❌ FAIL: openenv.yaml missing required key: {key}")
            return False

    # Check tasks
    tasks = spec.get('tasks', {})
    if not isinstance(tasks, dict) or len(tasks) < 3:
        print("❌ FAIL: openenv.yaml must have at least 3 tasks")
        return False

    # Check each task has grader
    tasks_with_graders = 0
    for task_name, task_config in tasks.items():
        grader = task_config.get('grader', {})
        if grader and grader.get('type') == 'custom' and grader.get('entrypoint'):
            tasks_with_graders += 1

    if tasks_with_graders < 3:
        print(f"❌ FAIL: Only {tasks_with_graders} tasks with graders, need at least 3")
        return False

    print(f"✅ PASS: openenv.yaml valid with {tasks_with_graders} tasks with graders")
    return True

def main():
    """Run all validation checks."""
    print("🚀 OpenEnv Validation Starting...")
    print("=" * 50)

    # Load spec
    try:
        spec = load_openenv_spec()
    except Exception as e:
        print(f"❌ FAIL: Cannot load openenv.yaml: {e}")
        return 1

    # Run checks
    checks = [
        ("Environment Entrypoint", lambda: check_environment_entrypoint(spec)),
        ("Gym API Compliance", check_gym_api_compliance),
        ("PettingZoo Wrapper", check_pettingzoo_wrapper),
        ("Inference Script", check_inference_script),
        ("LLM Proxy Integration", check_llm_proxy_integration),
        ("openenv.yaml", lambda: check_openenv_yaml(spec)),
    ]

    passed = 0
    total = len(checks)

    for name, check_func in checks:
        try:
            if check_func():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ FAIL: {name} - Unexpected error: {e}")
            print()

    print("=" * 50)
    print(f"Results: {passed} passed, {total - passed} failed")

    if passed == total:
        print("🎉 ALL CHECKS PASSED - Ready for OpenEnv submission!")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Fix issues before submission")
        return 1

if __name__ == "__main__":
    sys.exit(main())
    """Test that reward is properly normalized to [0,1]."""
    print("\nTEST: Reward normalization")
    try:
        env = MultiAgentEVChargingGridEnv({"task_id": "hard"})
        obs, _ = env.reset(seed=42)

        rewards = []
        coord_agent = HeuristicCoordinatorAgent()
        station_agent = HeuristicStationAgent()

        for _ in range(30):
            coord_action = coord_agent.act(obs)
            station_actions = []
            for i in range(env.num_stations):
                action = station_agent.act(i, obs, coord_action)
                station_actions.append(action)

            action = {
                "coordinator_action": coord_action,
                "station_actions": station_actions
            }
            obs, reward, _, truncated, _ = env.step(action)
            rewards.append(reward)

            if truncated:
                break

        min_r = min(rewards)
        max_r = max(rewards)
        mean_r = np.mean(rewards)

        assert 0.0 <= min_r, f"Min reward {min_r} < 0"
        assert max_r <= 1.0, f"Max reward {max_r} > 1"

        print("  OK: All rewards are normalized to [0,1]")
        print(f"     - Min: {min_r:.4f}, Max: {max_r:.4f}, Mean: {mean_r:.4f}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_grader_normalization() -> bool:
    """Test that graders return normalized scores."""
    print("\nTEST: Grader normalization [0,1]")
    try:
        env = MultiAgentEVChargingGridEnv({"task_id": "medium"})
        obs, _ = env.reset(seed=42)

        coord_agent = HeuristicCoordinatorAgent()
        station_agent = HeuristicStationAgent()

        for _ in range(min(50, env.task.episode_length)):
            coord_action = coord_agent.act(obs)
            station_actions = []
            for i in range(env.num_stations):
                action = station_agent.act(i, obs, coord_action)
                station_actions.append(action)

            action = {
                "coordinator_action": coord_action,
                "station_actions": station_actions
            }
            obs, _, _, truncated, info = env.step(action)

            if truncated:
                break

        metrics = env._metrics_snapshot()
        score_episode = grade_episode(metrics)

        assert 0.0 <= score_episode <= 1.0, f"Episode score {score_episode} not in [0,1]"

        print("  OK: Grader returns normalized score [0,1]")
        print(f"     - Episode score: {score_episode:.4f}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_task_definitions() -> bool:
    """Test all task definitions."""
    print("\nTEST: Task definitions (easy, medium, hard)")
    try:
        for task_id in ["easy", "medium", "hard"]:
            env = MultiAgentEVChargingGridEnv({"task_id": task_id})
            obs, info = env.reset(seed=42)

            assert env.task_id == task_id
            assert env.task.episode_length > 0

            print(f"  OK: Task '{task_id}' valid")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main() -> int:
    """Run all validations."""
    print("\n" + "=" * 60)
    print("OpenEnv Compliance Validation")
    print("=" * 60)

    tests = [
        ("Environment Reset/Step", test_env_reset_step),
        ("Reward Normalization", test_reward_normalization),
        ("Grader Normalization", test_grader_normalization),
        ("Task Definitions", test_task_definitions),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            results.append((name, False))

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {name}")

    readiness_score = (passed_count / total_count) * 100
    print(f"\nReadiness Score: {readiness_score:.1f}% ({passed_count}/{total_count})")

    if readiness_score == 100:
        print("\nOPENENV-COMPLIANT AND READY FOR SUBMISSION!")
    else:
        print("\nPlease address failing tests.")

    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
