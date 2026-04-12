"""Comprehensive round-one validator for the EV charging OpenEnv project."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

import inference
from ev_charging_grid_env.api.server import app
from ev_charging_grid_env.envs import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.graders import grade_episode


ROOT = Path(__file__).resolve().parent


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def validate_structure() -> None:
    required = [
        "openenv.yaml",
        "Dockerfile",
        "requirements.txt",
        "inference.py",
        "api_server.py",
        "api/server.py",
        "scripts/start.sh",
        "ev_charging_grid_env/envs/ev_charging_env.py",
        "ev_charging_grid_env/api/server.py",
        "ev_charging_grid_env/graders/task_grader.py",
        "ev_charging_grid_env/agents/coordinator_agent.py",
        "ev_charging_grid_env/agents/station_agent.py",
        "ev_charging_grid_env/ui/dashboard.py",
        "ev_charging_grid_env/config/tasks.py",
    ]
    for relative in required:
        assert (ROOT / relative).exists(), f"Missing required file: {relative}"


def validate_imports() -> None:
    importlib.import_module("ev_charging_grid_env")
    importlib.import_module("ev_charging_grid_env.envs")
    importlib.import_module("ev_charging_grid_env.graders")


def validate_openenv_yaml() -> None:
    spec = yaml.safe_load(_read("openenv.yaml"))
    assert spec["name"] == "ev-charging-grid"
    assert spec["entrypoint"] == "ev_charging_grid_env.envs.ev_charging_env:MultiAgentEVChargingGridEnv"
    assert [task["id"] for task in spec["tasks"]] == ["easy", "medium", "hard"]
    assert spec["grader"]["type"] == "reward"


def validate_environment() -> None:
    env = MultiAgentEVChargingGridEnv({"task_id": "medium"})
    assert hasattr(env, "reset")
    assert hasattr(env, "step")
    assert hasattr(env, "state")
    assert hasattr(env, "render")
    assert hasattr(env, "close")

    obs, info = env.reset(seed=42)
    assert isinstance(obs, dict)
    assert isinstance(info, dict)
    assert "station_features" in obs
    assert "queue_lengths" in obs
    assert "time_context" in obs

    result = env.step(
        {
            "coordinator_action": {
                "price_deltas": [0] * env.num_stations,
                "emergency_target_station": 0,
            },
            "station_actions": [1] * env.num_stations,
        }
    )
    assert len(result) == 5
    next_obs, reward, terminated, truncated, step_info = result
    assert isinstance(next_obs, dict)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(step_info, dict)
    assert isinstance(env.state(), dict)


def validate_reward_and_grader() -> None:
    env = MultiAgentEVChargingGridEnv()
    env.reset(seed=42)
    reward = env._compute_reward(
        {
            "vehicles_served": 4.0,
            "solar_kwh_used": 20.0,
            "emergency_served": 1.0,
            "avg_wait_time": 3.0,
            "queue_length": 5.0,
            "grid_overload": 2.0,
        }
    )
    expected_reward = (
        2.0 * 4.0
        + 1.5 * 20.0
        + 5.0 * 1.0
        - 0.5 * 3.0
        - 1.0 * 5.0
        - 3.0 * 2.0
    ) / 10.0
    assert reward == expected_reward

    score = grade_episode(
        {
            "served_ratio": 0.8,
            "solar_usage_ratio": 0.5,
            "normalized_wait_time": 0.25,
        }
    )
    expected_score = 0.4 * 0.8 + 0.3 * 0.5 + 0.3 * (1.0 - 0.25)
    assert abs(score - expected_score) < 1e-9


def validate_inference() -> None:
    source = _read("inference.py")
    for marker in ("[START]", "[STEP]", "[END]", "os.getenv", "OpenAI", "HF_TOKEN"):
        assert marker in source, f"Missing inference marker: {marker}"

    logs, result = inference.capture_run_output(task_id="easy", steps=5, seed=42)
    assert "[START]" in logs
    assert "[STEP] step=0 reward=" in logs
    assert "[END]" in logs
    assert isinstance(result["total_reward"], float)
    assert isinstance(result["summary"], str)
    json.dumps(result)


def validate_api() -> None:
    client = TestClient(app)
    reset_response = client.post("/reset", json={"seed": 42, "task_id": "easy"})
    assert reset_response.status_code == 200
    assert "observation" in reset_response.json()

    step_response = client.post(
        "/step",
        json={
            "action": {
                "coordinator_action": {
                    "price_deltas": [0] * 10,
                    "emergency_target_station": 0,
                },
                "station_actions": [1] * 10,
            }
        },
    )
    assert step_response.status_code == 200
    assert "reward" in step_response.json()

    state_response = client.get("/state")
    assert state_response.status_code == 200
    assert "observation" in state_response.json()


def validate_hf_server_and_docker() -> None:
    api_source = _read("ev_charging_grid_env/api/server.py")
    assert 'uvicorn.run(app, host="0.0.0.0", port=7860)' in api_source

    dockerfile = _read("Dockerfile")
    assert "FROM python:3.11-slim" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "COPY . ." in dockerfile
    assert "RUN pip install -r requirements.txt" in dockerfile
    assert 'CMD ["python", "api/server.py"]' in dockerfile


def main() -> int:
    validators = [
        validate_structure,
        validate_imports,
        validate_openenv_yaml,
        validate_environment,
        validate_reward_and_grader,
        validate_inference,
        validate_api,
        validate_hf_server_and_docker,
    ]
    for validator in validators:
        validator()
    print("round1: 100% pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
