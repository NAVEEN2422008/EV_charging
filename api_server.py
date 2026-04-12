"""OpenEnv-compatible API server for EV Charging Grid Optimizer."""

from __future__ import annotations

import json
import logging
from typing import Any

from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import BaseModel, Field, ValidationError
import numpy as np

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

# ──────────────────────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────────────────────

class ResetRequest(BaseModel):
    seed: int | None = None
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

# Global environment instance
_env_instance: MultiAgentEVChargingGridEnv | None = None
_last_observation: dict[str, Any] | None = None


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
    else:
        return obj


# ──────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/", methods=["GET"])
def root() -> tuple[dict, int]:
    """Root endpoint."""
    return jsonify({
        "name": "EV Charging Grid Optimizer API",
        "version": "1.0.0",
        "endpoints": [
            "GET /",
            "GET /health",
            "POST /reset",
            "POST /step",
            "GET /state",
            "GET /info",
        ]
    }), 200


@app.route("/health", methods=["GET"])
def health() -> tuple[dict, int]:
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "ev-charging-grid-env"}), 200


@app.route("/reset", methods=["GET", "POST"])
def reset() -> tuple[dict, int]:
    """Reset environment endpoint (OpenEnv compatible)."""
    if request.method == "GET":
        return jsonify({
            "message": "Reset endpoint. Use POST to reset the environment.",
            "success": True
        }), 200
    try:
        raw_data = request.get_json(force=True, silent=True) or {}
        try:
            req = ResetRequest(**raw_data)
        except ValidationError as ve:
            return jsonify({"error": ve.errors(), "success": False}), 400
            
        seed = req.seed
        config = req.config
        
        logger.info(f"Reset request: seed={seed}")
        
        global _env_instance
        if config:
            _env_instance = MultiAgentEVChargingGridEnv(config=config)
        else:
            _env_instance = get_env()
        
        obs, info = _env_instance.reset(seed=seed)
        
        global _last_observation
        _last_observation = obs
        
        return jsonify({
            "observation": serialize_for_json(obs),
            "info": serialize_for_json(info),
            "success": True,
        }), 200
        
    except Exception as e:
        logger.error(f"Reset failed: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "success": False,
        }), 400


@app.route("/step", methods=["GET", "POST"])
def step() -> tuple[dict, int]:
    """Step environment endpoint (OpenEnv compatible)."""
    if request.method == "GET":
        return jsonify({
            "message": "Step endpoint. Use POST to execute a step.",
            "success": True
        }), 200
    try:
        raw_data = request.get_json(force=True, silent=True)
        if raw_data is None:
             return jsonify({"error": "Missing JSON body", "success": False}), 400
             
        try:
            req = StepRequest(**raw_data)
        except ValidationError as ve:
            return jsonify({"error": ve.errors(), "success": False}), 400

        action = req.action
        env = get_env()
        obs, reward, terminated, truncated, info = env.step(action)
        
        global _last_observation
        _last_observation = obs
        
        return jsonify({
            "observation": serialize_for_json(obs),
            "reward": float(reward),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "info": serialize_for_json(info),
            "success": True,
        }), 200
        
    except Exception as e:
        logger.error(f"Step failed: {e}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 400


@app.route("/state", methods=["GET"])
def get_state() -> tuple[dict, int]:
    """Get current environment state."""
    try:
        global _last_observation
        if _last_observation is None:
            env = get_env()
            obs, _ = env.reset()
            _last_observation = obs
        
        return jsonify({
            "observation": serialize_for_json(_last_observation),
            "success": True,
        }), 200
        
    except Exception as e:
        logger.error(f"Get state failed: {e}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 400


@app.route("/info", methods=["GET"])
def get_info() -> tuple[dict, int]:
    """Get environment info."""
    try:
        env = get_env()
        return jsonify({
            "info": {
                "num_stations": env.num_stations,
                "observation_space": str(env.observation_space),
                "action_space": str(env.action_space),
            },
            "success": True,
        }), 200
        
    except Exception as e:
        logger.error(f"Get info failed: {e}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 400


# ──────────────────────────────────────────────────────────────────────────────
# ERROR HANDLERS
# ──────────────────────────────────────────────────────────────────────────────


@app.errorhandler(404)
def not_found(error: Any) -> tuple[dict, int]:
    """Handle 404 errors."""
    return jsonify({
        "error": "Endpoint not found",
        "path": request.path,
        "method": request.method,
    }), 404


@app.errorhandler(405)
def method_not_allowed(error: Any) -> tuple[dict, int]:
    """Handle 405 errors."""
    return jsonify({
        "error": "Method not allowed",
        "path": request.path,
        "method": request.method,
    }), 405


@app.errorhandler(500)
def internal_error(error: Any) -> tuple[dict, int]:
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}", exc_info=True)
    return jsonify({
        "error": "Internal server error",
        "message": str(error),
    }), 500


# ──────────────────────────────────────────────────────────────────────────────
# ERROR HANDLERS (JSON-only responses)
# ──────────────────────────────────────────────────────────────────────────────


@app.errorhandler(405)
def method_not_allowed(error: Any) -> tuple[dict, int]:
    """Handle 405 Method Not Allowed - return JSON instead of HTML."""
    return jsonify({
        "error": "Method not allowed",
        "method": request.method,
        "path": request.path,
        "allowed_methods": ["POST"] if request.path == "/reset" else ["GET", "POST"],
    }), 405


@app.errorhandler(404)
def not_found(error: Any) -> tuple[dict, int]:
    """Handle 404 Not Found - return JSON instead of HTML."""
    return jsonify({
        "error": "Endpoint not found",
        "path": request.path,
        "method": request.method,
    }), 404


@app.errorhandler(500)
def internal_error(error: Any) -> tuple[dict, int]:
    """Handle 500 Internal Server Error."""
    logger.error(f"Internal error: {error}", exc_info=True)
    return jsonify({
        "error": "Internal server error",
        "message": str(error),
    }), 500


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenEnv API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=5000, help="Server port")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    
    args = parser.parse_args()
    
    logger.info(f"Starting server on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
