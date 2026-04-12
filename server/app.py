"""OpenEnv-compatible API server for EV Charging Grid Optimizer."""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import BaseModel, Field, ValidationError
import numpy as np

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

# ──────────────────────────────────────────────────────────────────────────────
# TASK ID → ENVIRONMENT CONFIG MAP (must match openenv.yaml task ids)
# ──────────────────────────────────────────────────────────────────────────────

TASK_REGISTRY: dict[str, dict[str, Any]] = {
    "basic_grid_operation": {
        "num_stations": 2,
        "base_arrival_rate": 4.0,
        "emergency_arrival_prob": 0.02,
        "episode_length": 120,
    },
    "queue_optimization": {
        "num_stations": 4,
        "base_arrival_rate": 6.0,
        "emergency_arrival_prob": 0.05,
        "episode_length": 180,
    },
    "full_grid_management": {
        "num_stations": 6,
        "base_arrival_rate": 8.0,
        "emergency_arrival_prob": 0.08,
        "episode_length": 240,
    },
}

DEFAULT_TASK_ID = "basic_grid_operation"

# ──────────────────────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ──────────────────────────────────────────────────────────────────────────────

class ResetRequest(BaseModel):
    task_id: Optional[str] = None
    seed: Optional[int] = None
    config: dict[str, Any] = Field(default_factory=dict)

class StepRequest(BaseModel):
    action: dict[str, Any]

# ──────────────────────────────────────────────────────────────────────────────
# FLASK APP SETUP
# ──────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)
app.url_map.strict_slashes = False
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
_env_instance: MultiAgentEVChargingGridEnv | None = None
_last_observation: dict[str, Any] | None = None
_current_task_id: str = DEFAULT_TASK_ID


def get_env() -> MultiAgentEVChargingGridEnv:
    """Get or create the environment instance."""
    global _env_instance
    if _env_instance is None:
        _env_instance = MultiAgentEVChargingGridEnv()
    return _env_instance


def serialize_for_json(obj: Any) -> Any:
    """Convert numpy arrays to JSON-serializable format."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.floating)):
        return float(obj) if isinstance(obj, np.floating) else int(obj)
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    return obj


# ──────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/", methods=["GET"])
def root() -> tuple:
    return jsonify({
        "name": "EV Charging Grid Optimizer API",
        "version": "1.0.0",
        "tasks": list(TASK_REGISTRY.keys()),
        "endpoints": ["GET /", "GET /health", "POST /reset", "POST /step", "GET /state", "GET /tasks"],
    }), 200


@app.route("/health", methods=["GET"])
def health() -> tuple:
    env = get_env()
    return jsonify({
        "status": "healthy",
        "service": "ev-charging-grid-env",
        "current_task": _current_task_id,
        "available_tasks": list(TASK_REGISTRY.keys()),
        "num_stations": env.num_stations,
    }), 200


@app.route("/tasks", methods=["GET"])
def list_tasks() -> tuple:
    """List all available tasks — required for OpenEnv task validation."""
    tasks = []
    for task_id, cfg in TASK_REGISTRY.items():
        tasks.append({
            "id": task_id,
            "num_stations": cfg["num_stations"],
            "episode_length": cfg["episode_length"],
        })
    return jsonify({"tasks": tasks, "success": True}), 200


@app.route("/reset", methods=["GET", "POST"])
def reset() -> tuple:
    """Reset environment — now accepts task_id to switch tasks."""
    if request.method == "GET":
        return jsonify({"message": "Use POST to reset.", "success": True}), 200
    try:
        raw_data = request.get_json(force=True, silent=True) or {}
        try:
            req = ResetRequest(**raw_data)
        except ValidationError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        # Resolve task config
        task_id = req.task_id or DEFAULT_TASK_ID
        if task_id not in TASK_REGISTRY:
            return jsonify({"success": False, "error": f"Unknown task_id: {task_id}"}), 400

        global _env_instance, _current_task_id
        _current_task_id = task_id

        # Merge registry config with any overrides from request
        task_config = {**TASK_REGISTRY[task_id], **req.config}
        task_config["task_id"] = task_id # Ensure it's in the env config

        # ALWAYS create a fresh instance for the new task to ensure num_stations etc are correct
        _env_instance = MultiAgentEVChargingGridEnv(config=task_config)
        obs, info = _env_instance.reset(seed=req.seed)

        return jsonify({
            "success": True,
            "observation": serialize_for_json(obs),
            "info": serialize_for_json(info),
            "task_id": task_id
        }), 200

    except Exception as e:
        logger.error(f"Reset failed: {e}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 400


@app.route("/step", methods=["GET", "POST"])
def step() -> tuple:
    """Step the environment."""
    if request.method == "GET":
        return jsonify({"message": "Use POST to step.", "success": True}), 200
    try:
        raw_data = request.get_json(force=True, silent=True)
        if raw_data is None:
            return jsonify({"error": "Missing JSON body", "success": False}), 400

        try:
            req = StepRequest(**raw_data)
        except ValidationError as ve:
            return jsonify({"error": ve.errors(), "success": False}), 400

        env = get_env()
        obs, reward, terminated, truncated, info = env.step(req.action)

        global _last_observation
        _last_observation = obs

        return jsonify({
            "observation": serialize_for_json(obs),
            "reward": float(reward),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "done": bool(terminated or truncated),
            "info": serialize_for_json(info),
            "success": True,
        }), 200

    except Exception as e:
        logger.error(f"Step failed: {e}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 400


@app.route("/state", methods=["GET"])
def get_state() -> tuple:
    global _last_observation
    if _last_observation is None:
        env = get_env()
        obs, _ = env.reset()
        _last_observation = obs
    return jsonify({"observation": serialize_for_json(_last_observation), "success": True}), 200


# ──────────────────────────────────────────────────────────────────────────────
# ERROR HANDLERS
# ──────────────────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(error: Any) -> tuple:
    return jsonify({"error": "Not found", "path": request.path}), 404

@app.errorhandler(405)
def method_not_allowed(error: Any) -> tuple:
    return jsonify({"error": "Method not allowed", "path": request.path, "method": request.method}), 405

@app.errorhandler(500)
def internal_error(error: Any) -> tuple:
    return jsonify({"error": "Internal server error", "message": str(error)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="OpenEnv EV Charging API Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    logger.info(f"Starting server on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()
