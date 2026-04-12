#!/usr/bin/env python3
"""
OpenEnv Validation Script

Performs comprehensive validation of the EV Charging Grid environment
for OpenEnv compliance.

Validation Checks:
1. Environment Entrypoint
2. Gym API Compliance
3. PettingZoo Wrapper (optional)
4. Inference Script
5. LLM Proxy Integration
6. openenv.yaml
"""

import sys
import os
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

        required_attrs = ['observation_space', 'action_space', 'reset', 'step']
        for attr in required_attrs:
            if not hasattr(env, attr):
                print(f"❌ FAIL: Missing required attribute: {attr}")
                return False

        obs, info = env.reset(seed=42)
        if not isinstance(obs, dict) or not isinstance(info, dict):
            print("❌ FAIL: reset() must return (dict, dict)")
            return False

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
        spec = importlib.util.spec_from_file_location("inference", "inference.py")
        inference_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inference_module)

        if not hasattr(inference_module, 'run'):
            print("❌ FAIL: inference.py missing run() function")
            return False

        os.environ.setdefault('SIMULATION_STEPS', '5')
        os.environ.setdefault('RANDOM_SEED', '42')
        # Point to a dummy env that won't fail on missing server
        os.environ.setdefault('ENV_BASE_URL', 'http://localhost:5000')

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
        spec = importlib.util.spec_from_file_location("inference", "inference.py")
        inference_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inference_module)

        if not hasattr(inference_module, 'get_llm_client'):
            print("❌ FAIL: inference.py missing get_llm_client() function")
            return False

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
            for var, value in old_vars.items():
                if value is None:
                    os.environ.pop(var, None)
                else:
                    os.environ[var] = value

    except Exception as e:
        print(f"❌ FAIL: LLM proxy integration error: {e}")
        return False


def check_openenv_yaml(spec: Dict[str, Any]) -> bool:
    """Check 6: openenv.yaml structure."""
    print("🔍 Checking openenv.yaml...")

    required_keys = ['name', 'entrypoint', 'tasks']
    for key in required_keys:
        if key not in spec:
            print(f"❌ FAIL: openenv.yaml missing required key: {key}")
            return False

    tasks = spec.get('tasks', [])

    # Support both list format (new) and dict format (old)
    if isinstance(tasks, list):
        tasks_with_graders = sum(1 for t in tasks if t.get('grading'))
        task_count = len(tasks)
    elif isinstance(tasks, dict):
        tasks_with_graders = sum(
            1 for t in tasks.values()
            if t.get('grader', {}).get('type') == 'custom' and t.get('grader', {}).get('entrypoint')
        )
        task_count = len(tasks)
    else:
        print("❌ FAIL: tasks must be a list or dict")
        return False

    if task_count < 3:
        print(f"❌ FAIL: Need at least 3 tasks, found {task_count}")
        return False

    if tasks_with_graders < 3:
        print(f"❌ FAIL: Only {tasks_with_graders} tasks with graders, need at least 3")
        return False

    print(f"✅ PASS: openenv.yaml valid — {tasks_with_graders} tasks with graders")
    return True


def main():
    """Run all validation checks."""
    print("🚀 OpenEnv Validation Starting...")
    print("=" * 50)

    try:
        spec = load_openenv_spec()
    except Exception as e:
        print(f"❌ FAIL: Cannot load openenv.yaml: {e}")
        return 1

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
    print(f"Results: {passed}/{total} passed")

    if passed == total:
        print("🎉 ALL CHECKS PASSED - Ready for OpenEnv submission!")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Fix issues before submission")
        return 1


if __name__ == "__main__":
    sys.exit(main())
