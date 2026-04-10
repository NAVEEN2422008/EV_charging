"""Quick validation test for submission readiness."""
import sys
import os

# Suppress Unicode errors
os.environ['PYTHONIOENCODING'] = 'utf-8'

print("\n" + "="*60)
print("PHASE 1 SUBMISSION READINESS TEST")
print("="*60)

# Test 1: Syntax
print("\n[1/5] Testing inference.py syntax...")
try:
    import py_compile
    py_compile.compile('inference.py', doraise=True)
    print("PASS: Syntax OK")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

# Test 2: Import
print("\n[2/5] Testing inference module import...")
try:
    import inference
    print("PASS: Module imports")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

# Test 3: run() function
print("\n[3/5] Testing run() function execution...")
try:
    result = inference.run()
    print("PASS: run() executed")
except Exception as e:
    print(f"FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Result structure
print("\n[4/5] Validating return structure...")
try:
    assert isinstance(result, dict), "run() must return dict"
    assert "total_reward" in result, "Missing total_reward"
    assert "summary" in result, "Missing summary"
    assert isinstance(result["total_reward"], float), "total_reward must be float"
    assert isinstance(result["summary"], str), "summary must be string"
    assert len(result["summary"]) > 0, "summary must not be empty"
    print("PASS: Structure valid")
    print(f"  - total_reward={result['total_reward']}")
    print(f"  - summary length={len(result['summary'])}")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

# Test 5: JSON serialization
print("\n[5/5] Testing JSON serialization...")
try:
    import json
    json_str = json.dumps(result)
    json.loads(json_str)
    print("PASS: JSON serializable")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("ALL TESTS PASSED - READY FOR SUBMISSION")
print("="*60 + "\n")
sys.exit(0)
