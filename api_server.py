"""OpenEnv-compatible API server for EV Charging Grid Optimizer.

Exposes the environment as HTTP endpoints for OpenEnv validation.
Handles reset, step, and state requests.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

# ──────────────────────────────────────────────────────────────────────────────
# FLASK APP SETUP
# ──────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
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
    """Convert numpy arrays and other objects to JSON-serializable format."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/health", methods=["GET"])
def health() -> dict[str, str]:
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "ev-charging-grid-env"})


# ──────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT ENDPOINTS (OPENENV API)
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/reset", methods=["POST"])
def reset() -> dict[str, Any]:
    """Reset environment endpoint.
    
    OpenEnv calls this to reset the environment before running an episode.
    
    Request body (optional):
    {
        "seed": int,  # Random seed
        "config": dict  # Environment config
    }
    
    Response:
    {
        "observation": dict,
        "info": dict,
        "success": bool
    }
    """
    try:
        data = request.get_json() or {}
        seed = data.get("seed", None)
        config = data.get("config", {})
        
        logger.info(f"Reset request: seed={seed}, config_keys={list(config.keys())}")
        
        # Initialize/reset environment
        global _env_instance
        if config:
            _env_instance = MultiAgentEVChargingGridEnv(config=config)
        else:
            env = get_env()
        
        env = get_env()
        obs, info = env.reset(seed=seed)
        
        global _last_observation
        _last_observation = obs
        
        response = {
            "observation": serialize_for_json(obs),
            "info": serialize_for_json(info),
            "success": True,
        }
        
        logger.info("Reset successful")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Reset failed: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "success": False,
        }), 400


@app.route("/step", methods=["POST"])
def step() -> dict[str, Any]:
    """Step environment endpoint.
    
    OpenEnv calls this to execute an action and get the next state.
    
    Request body:
    {
        "action": dict or list or int,  # Action from policy
        "action_type": str  # "coordinator" or "station" or "combined"
    }
    
    Response:
    {
        "observation": dict,
        "reward": float,
        "terminated": bool,
        "truncated": bool,
        "info": dict,
        "success": bool
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data", "success": False}), 400
        
        action = data.get("action")
        if action is None:
            return jsonify({"error": "Missing action", "success": False}), 400
        
        logger.info(f"Step request: action_type={type(action).__name__}")
        
        env = get_env()
        obs, reward, terminated, truncated, info = env.step(action)
        
        global _last_observation
        _last_observation = obs
        
        response = {
            "observation": serialize_for_json(obs),
            "reward": float(reward),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "info": serialize_for_json(info),
            "success": True,
        }
        
        logger.info(f"Step successful: reward={reward:.2f}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Step failed: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "success": False,
        }), 400


@app.route("/state", methods=["GET"])
def get_state() -> dict[str, Any]:
    """Get current environment state endpoint.
    
    Returns the last observation without stepping.
    """
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
        return jsonify({
            "error": str(e),
            "success": False,
        }), 400


@app.route("/info", methods=["GET"])
def get_info() -> dict[str, Any]:
    """Get environment info endpoint.
    
    Returns metadata about the environment.
    """
    try:
        env = get_env()
        info = {
            "num_stations": env.num_stations,
            "observation_space": str(env.observation_space),
            "action_space": str(env.action_space),
            "episode_stats": serialize_for_json(env.episode_stats),
        }
        
        return jsonify({
            "info": info,
            "success": True,
        }), 200
        
    except Exception as e:
        logger.error(f"Get info failed: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "success": False,
        }), 400


# ──────────────────────────────────────────────────────────────────────────────
# ERROR HANDLERS
# ──────────────────────────────────────────────────────────────────────────────


@app.errorhandler(404)
def not_found(error: Any) -> tuple[dict[str, str], int]:
    """Handle 404 errors."""
    return jsonify({
        "error": "Endpoint not found",
        "path": request.path,
        "method": request.method,
    }), 404


@app.route("/", methods=["GET"])
def root() -> dict[str, str]:
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
    })


@app.errorhandler(405)
def method_not_allowed(error: Any) -> tuple[dict[str, str], int]:
    """Handle 405 errors."""
    return jsonify({
        "error": "Method not allowed",
        "path": request.path,
        "method": request.method,
        "allowed_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    }), 405


@app.errorhandler(500)
def internal_error(error: Any) -> tuple[dict[str, str], int]:
    """Handle 500 errors."""
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
