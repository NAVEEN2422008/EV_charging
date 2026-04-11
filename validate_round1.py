"""Comprehensive Round-1 compliance validation."""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


def check_file_exists(filepath: str, description: str) -> tuple[bool, str]:
    """Check if a required file exists."""
    path = Path(filepath)
    if path.exists():
        return True, f"✓ {description}: {filepath}"
    return False, f"✗ {description}: {filepath} NOT FOUND"


def check_module_importable(module_name: str, description: str) -> tuple[bool, str]:
    """Check if a module can be imported."""
    try:
        __import__(module_name)
        return True, f"✓ {description}: {module_name} imports successfully"
    except ImportError as e:
        return False, f"✗ {description}: {module_name} failed - {e}"


def check_grader_functions() -> tuple[bool, str]:
    """Check that grader functions work."""
    try:
        from ev_charging_grid_env.graders import (
            grade_easy_task,
            grade_medium_task,
            grade_hard_task,
        )
        
        # Test with sample metrics
        test_metrics = {
            "average_wait_time": 12.5,
            "solar_utilization_pct": 45.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 45.0,
            "emergency_served": 3.0,
            "emergency_missed": 1.0,
            "grid_overload_events": 15.0,
        }
        
        easy = grade_easy_task(test_metrics)
        medium = grade_medium_task(test_metrics)
        hard = grade_hard_task(test_metrics)
        
        # Validate outputs are in [0.0, 1.0]
        for score, task in [(easy, "easy"), (medium, "medium"), (hard, "hard")]:
            if not (0.0 <= score <= 1.0):
                return False, f"✗ Grader {task} returned invalid score: {score}"
        
        return True, f"✓ All graders functional: easy={easy:.3f}, medium={medium:.3f}, hard={hard:.3f}"
    except Exception as e:
        return False, f"✗ Grader functions failed: {e}"


def check_environment_api() -> tuple[bool, str]:
    """Check that environment implements proper Gym API."""
    try:
        from ev_charging_grid_env.envs import MultiAgentEVChargingGridEnv
        
        # Verify class exists and has required methods
        required_methods = ["reset", "step", "render", "close"]
        env = MultiAgentEVChargingGridEnv()
        
        for method in required_methods:
            if not hasattr(env, method):
                return False, f"✗ Environment missing method: {method}"
        
        # Test basic reset/step
        obs, info = env.reset(seed=42)
        if obs is None:
            return False, "✗ Environment.reset() returned None observation"
        
        # Test step with dummy action
        dummy_action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(dummy_action)
        
        if obs is None or not isinstance(reward, (int, float)):
            return False, f"✗ Environment.step() returned invalid values"
        
        return True, "✓ Environment implements full Gym API (reset, step, action/observation spaces)"
    except Exception as e:
        return False, f"✗ Environment API check failed: {e}"


def check_openenv_spec() -> tuple[bool, str]:
    """Check that openenv.yaml is valid."""
    try:
        import yaml
        spec = yaml.safe_load(Path("openenv.yaml").read_text())
        
        # Check required fields
        required_fields = ["name", "version", "tasks", "grader", "config", "api"]
        for field in required_fields:
            if field not in spec:
                return False, f"✗ openenv.yaml missing field: {field}"
        
        # Check tasks
        tasks = spec.get("tasks", {})
        if not all(k in tasks for k in ["easy", "medium", "hard"]):
            return False, "✗ openenv.yaml missing required tasks (easy/medium/hard)"
        
        return True, "✓ openenv.yaml is valid with all required fields and 3 tasks"
    except Exception as e:
        return False, f"✗ openenv.yaml validation failed: {e}"


def check_inference_compliance() -> tuple[bool, str]:
    """Check that inference.py is compliant."""
    try:
        import subprocess
        from pathlib import Path
        import os
        
        # Check file exists
        if not Path("inference.py").exists():
            return False, "✗ inference.py not found"
        
        # Read file and check for required elements
        content = Path("inference.py").read_text()
        
        required_patterns = [
            ("[START]", "bracketed start marker"),
            ("[STEP]", "bracketed step marker"),
            ("[END]", "bracketed end marker"),
            ("os.getenv", "environment variable reading"),
            ("OpenAI", "LLM client initialization"),
        ]
        
        for pattern, description in required_patterns:
            if pattern not in content:
                return False, f"✗ inference.py missing: {description} ({pattern})"
        
        return True, "✓ inference.py has all required compliance elements (bracketed logs, env vars, LLM)"
    except Exception as e:
        return False, f"✗ inference.py check failed: {e}"


def check_dockerization() -> tuple[bool, str]:
    """Check that Docker is properly configured."""
    try:
        dockerfile = Path("Dockerfile").read_text()
        
        # Check for required elements
        if "7860" not in dockerfile:
            return False, "✗ Dockerfile not using port 7860 (required for HF Spaces)"
        
        if "0.0.0.0" not in dockerfile:
            return False, "✗ Dockerfile not binding to 0.0.0.0 (required for container networking)"
        
        if "streamlit" in dockerfile.lower():
            streamlit_config = Path(".streamlit/config.toml").read_text()
            if "address" not in streamlit_config or "enableCORS" not in streamlit_config:
                return False, "✗ Streamlit config missing required settings"
        
        return True, "✓ Dockerfile configured for HF Spaces deployment (port 7860, 0.0.0.0)"
    except Exception as e:
        return False, f"✗ Docker check failed: {e}"


def run_validation() -> bool:
    """Run all validation checks and report results."""
    print("\n" + "="*70)
    print("OPENENV ROUND-1 COMPLIANCE VALIDATION")
    print("="*70 + "\n")
    
    checks = [
        ("File Structure", [
            ("openenv.yaml", "OpenEnv specification"),
            ("Dockerfile", "Docker configuration"),
            ("inference.py", "Inference script"),
            ("api_server.py", "API server"),
            ("requirements.txt", "Dependencies"),
        ]),
        ("Module Imports", [
            ("ev_charging_grid_env", "Main package"),
            ("ev_charging_grid_env.envs", "Environment module"),
            ("ev_charging_grid_env.graders", "Graders module (NEW)"),
        ]),
        ("API & Functionality", [
            (check_environment_api, "Environment API compliance"),
            (check_grader_functions, "Task grader functions (NEW)"),
            (check_openenv_spec, "OpenEnv specification validation"),
            (check_inference_compliance, "Inference script compliance"),
            (check_dockerization, "Docker/HF Spaces configuration"),
        ]),
    ]
    
    all_passed = True
    
    # File existence checks
    print("FILE STRUCTURE CHECK:")
    print("-" * 70)
    for category, files in [(k, v) for k, v in checks[:2] if k == "File Structure"]:
        for item in files:
            if isinstance(item, tuple) and len(item) == 2:
                filepath, desc = item
                passed, msg = check_file_exists(filepath, desc)
                print(msg)
                all_passed = all_passed and passed
    
    # Module import checks
    print("\nMODULE IMPORTS CHECK:")
    print("-" * 70)
    for category, modules in [(k, v) for k, v in checks[:2] if k == "Module Imports"]:
        for item in modules:
            if isinstance(item, tuple) and len(item) == 2:
                module, desc = item
                passed, msg = check_module_importable(module, desc)
                print(msg)
                all_passed = all_passed and passed
    
    # Function checks
    print("\nFUNCTIONAL CHECKS:")
    print("-" * 70)
    for category, funcs in [(k, v) for k, v in checks if k == "API & Functionality"]:
        for item in funcs:
            if callable(item):
                func = item
                passed, msg = func()
            else:
                func, desc = item
                passed, msg = func()
            print(msg)
            all_passed = all_passed and passed
    
    # Summary
    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL CHECKS PASSED - READY FOR ROUND-1 SUBMISSION")
        print("="*70)
        print("\nREMAINING MANUAL STEPS (for HF Spaces):")
        print("  1. Make Hugging Face Space PUBLIC")
        print("  2. Add secrets in Space settings:")
        print("     - HF_TOKEN: Your Hugging Face API token")
        print("     - API_KEY: For LLM proxy authentication")
        print("="*70)
        return True
    else:
        print("✗ SOME CHECKS FAILED - FIX ISSUES BEFORE SUBMISSION")
        print("="*70)
        return False


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
