#!/usr/bin/env python3
"""
inference.py — EV Charging Grid Optimizer
OpenEnv Submission | Multi-Agent Smart Grid RL
================================================

STDOUT format (strict):
    [START] task=<task> env=<benchmark> model=<model>
    [STEP]  step=<n> action=<action> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<0.000> rewards=<r1,r2,...>

Runs ALL 3 tasks so the validator sees all graders.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from typing import List, Optional, Dict, Any

from openai import OpenAI

# ──────────────────────────────────────────────────────────
# REQUIRED ENVIRONMENT VARIABLES (strict OpenEnv spec)
API_BASE_URL     = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME       = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN         = os.getenv("HF_TOKEN")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

# Environment-specific config
ENV_BASE_URL  = os.getenv("ENV_BASE_URL", "https://naveenkumar24022008-ev.hf.space")
BENCHMARK     = os.getenv("EV_BENCH", "ev-charging-grid-env")
RANDOM_SEED   = int(os.getenv("RANDOM_SEED", "42"))

# Run ALL tasks so validator sees 3 graders
ALL_TASKS = [
    "basic_grid_operation",
    "queue_optimization",
    "full_grid_management",
]

# Task-specific step counts aligned with openenv.yaml max_steps
TASK_MAX_STEPS = {
    "basic_grid_operation": 30,   # subset of 120 for speed
    "queue_optimization":   30,   # subset of 180
    "full_grid_management": 30,   # subset of 240
}

# Task → environment config mapping
TASK_CONFIGS = {
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

SUCCESS_SCORE_THRESHOLD = 0.5

# ──────────────────────────────────────────────────────────
# LOGGING (strict format)

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    action_clean = str(action).replace("\n", " ").strip()[:200]
    error_val = error if error else "null"
    print(f"[STEP] step={step} action={action_clean!r} reward={reward:.2f} done={str(done).lower()} error={error_val}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)

# ──────────────────────────────────────────────────────────
# ENV HTTP CLIENT

def env_request(path: str, method: str = "GET", body: Optional[dict] = None) -> dict:
    url  = ENV_BASE_URL.rstrip("/") + path
    data = json.dumps(body or {}).encode()
    req  = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()[:100]}"}
    except Exception as ex:
        return {"error": str(ex)}

def env_reset(task_id: str) -> dict:
    config = TASK_CONFIGS.get(task_id, {})
    return env_request("/reset", "POST", {"task_id": task_id, "config": config, "seed": RANDOM_SEED})

def env_step(action: dict) -> dict:
    return env_request("/step", "POST", {"action": action})

# ──────────────────────────────────────────────────────────
# LLM COORDINATOR AGENT

def get_llm_action(client: OpenAI, num_stations: int, obs: dict, step: int) -> dict:
    """Use LLM to decide coordinator actions (pricing and emergency routing)."""
    try:
        # Simplified observation summary for the prompt
        station_info = obs.get("observation", {}).get("station_features", [])
        queue_info   = obs.get("observation", {}).get("queue_lengths", [])
        
        prompt = f"""
        Task: Coordinate {num_stations} EV charging stations.
        Step: {step}
        Queues: {queue_info}
        Weather: {obs.get("observation", {}).get("weather", "unknown")}
        
        Decide:
        1. price_deltas: Array of {num_stations} integers (-1, 0, or 1)
        2. emergency_target_station: Index [0-{num_stations-1}]
        
        Return JSON only:
        {{"price_deltas": [...], "emergency_target_station": idx}}
        """

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=10
        )
        data = json.loads(response.choices[0].message.content)
        
        # Validate and sanitize response
        price_deltas = data.get("price_deltas", [0] * num_stations)
        if len(price_deltas) != num_stations:
            price_deltas = [0] * num_stations
            
        target = int(data.get("emergency_target_station", 0)) % num_stations
        
        return {
            "coordinator_action": {
                "price_deltas": price_deltas,
                "emergency_target_station": target,
            },
            "station_actions": [1] * num_stations,
        }
    except Exception as e:
        # Fallback to heuristic if LLM fails
        return build_heuristic_action(num_stations, step)


def build_heuristic_action(num_stations: int, step: int) -> dict:
    """Fallback heuristic policy."""
    return {
        "coordinator_action": {
            "price_deltas": [0] * num_stations,
            "emergency_target_station": step % num_stations,
        },
        "station_actions": [1] * num_stations,
    }


def get_llm_client() -> Optional[OpenAI]:
    """Initialize OpenAI client pointing to the OpenEnv proxy."""
    api_key = os.getenv("API_KEY") or os.getenv("HF_TOKEN")
    if not api_key:
        return None
    return OpenAI(base_url=API_BASE_URL, api_key=api_key)


# ──────────────────────────────────────────────────────────
# TASK RUNNER

def run_task(task_id: str) -> float:
    """Run a single task episode and return the score."""
    rewards:     List[float] = []
    steps_taken  = 0
    score        = 0.0
    success      = False
    num_stations = TASK_CONFIGS.get(task_id, {}).get("num_stations", 2)
    max_steps    = TASK_MAX_STEPS.get(task_id, 30)

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    # Initialize client (may be None if no API key present)
    client = get_llm_client()

    try:
        obs = env_reset(task_id)
        if "error" in obs:
            print(f"[DEBUG] Reset error: {obs['error']}", flush=True)
            obs = {"success": False}

        for step in range(1, max_steps + 1):
            # Decision (LLM or Heuristic)
            if client:
                action = get_llm_action(client, num_stations, obs, step)
            else:
                action = build_heuristic_action(num_stations, step)
                
            # Execute step
            res = env_step(action)
            steps_taken = step

            if "error" in res:
                error_msg = res["error"]
                log_step(step, json.dumps(action), 0.0, False, error_msg)
                rewards.append(0.0)
                continue

            reward = float(res.get("reward", 0.0))
            done   = bool(res.get("terminated", False) or res.get("truncated", False))
            obs    = res # update for next step observe
            
            rewards.append(reward)
            log_step(step, json.dumps(action), reward, done, None)

            if done:
                break

        # Result calculation
        raw_score  = sum(rewards) / max(len(rewards), 1)
        score      = max(0.0, min(1.0, raw_score))
        success    = score >= SUCCESS_SCORE_THRESHOLD

    except Exception as exc:
        print(f"[DEBUG] Task exception: {exc}", flush=True)
        score = 0.01

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


# ──────────────────────────────────────────────────────────
# LLM CLIENT (required by validate_openenv.py)

def get_llm_client() -> Optional[OpenAI]:
    """Return OpenAI client using env vars. Called by local validator."""
    api_key = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
    if not api_key:
        raise ValueError("HF_TOKEN or API_KEY environment variable must be set")
    return OpenAI(base_url=API_BASE_URL, api_key=api_key)


def run() -> Dict[str, Any]:
    """Run all tasks and return summary dict. Called by local validate_openenv.py."""
    specific_task = os.getenv("MY_ENV_V4_TASK")
    tasks_to_run  = [specific_task] if specific_task else ALL_TASKS

    all_scores: Dict[str, float] = {}
    total_reward = 0.0
    for task_id in tasks_to_run:
        score = run_task(task_id)
        all_scores[task_id] = score
        total_reward += score
        print("", flush=True)

    return {
        "status": "success",
        "total_reward": total_reward,
        "scores": all_scores,
    }


def main() -> None:
    """Entry point: run all tasks unless MY_ENV_V4_TASK overrides."""
    results = run()
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
