#!/usr/bin/env python3
"""
OpenEnv-Compliant Inference Engine for EV Charging Grid Optimizer.

This script provides a deterministic evaluation loop with strict log formatting
and optional LLM analysis. It is intended to serve as the root inference entry
point for OpenEnv validation.
"""

import json
import os
import sys
from typing import Any, Dict

from openai import OpenAI
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
SIMULATION_STEPS = int(os.getenv("SIMULATION_STEPS", "30"))
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

# ============================================================================
# LLM CLIENT
# ============================================================================


def get_llm_client() -> OpenAI:
    api_key = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
    if not api_key:
        raise ValueError("HF_TOKEN or API_KEY environment variable must be set")
    return OpenAI(base_url=API_BASE_URL, api_key=api_key)


try:
    llm_client = get_llm_client()
except Exception:
    llm_client = None


def call_llm(prompt: str) -> str:
    if llm_client is None:
        return f"[Mock Response] {prompt[:50]}..."

    try:
        response = llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        return f"[Error] {str(exc)}"


# ============================================================================
# ENVIRONMENT LOOP
# ============================================================================


def create_environment() -> MultiAgentEVChargingGridEnv:
    return MultiAgentEVChargingGridEnv()


def step_environment(env: MultiAgentEVChargingGridEnv) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any], dict[str, Any]]:
    action = {
        "coordinator_action": {
            "price_deltas": [0] * env.num_stations,
            "emergency_target_station": 0,
        },
        "station_actions": [0] * env.num_stations,
    }
    obs, reward, terminated, truncated, info = env.step(action)
    return obs, float(reward), bool(terminated), bool(truncated), info, action


def run() -> Dict[str, Any]:
    task = "baseline"
    env_name = "ev-charging-grid-env"

    print(f"[START] task={task} env={env_name} model={MODEL_NAME} seed={RANDOM_SEED}")

    env = create_environment()
    env.reset(seed=RANDOM_SEED)

    total_reward = 0.0
    episode_rewards: list[float] = []
    steps_executed = 0

    for step in range(SIMULATION_STEPS):
        obs, reward, terminated, truncated, info, action = step_environment(env)
        total_reward += reward
        episode_rewards.append(reward)
        done = terminated or truncated
        action_str = json.dumps(action, separators=(",", ":"))

        print(f"[STEP] step={step} action=\"{action_str}\" reward={reward:.4f} done={done} error=None")

        steps_executed += 1
        if done:
            break

    score = max(0.0, min(1.0, 0.5 + total_reward / 100.0)) if steps_executed > 0 else 0.0
    rewards_str = json.dumps(episode_rewards)

    print(f"[END] success=true steps={steps_executed} score={score:.4f} rewards={rewards_str}")

    summary = call_llm(
        f"Total reward: {total_reward:.2f}. Steps: {steps_executed}. Explain system performance."
    )

    return {
        "status": "success",
        "total_reward": float(total_reward),
        "steps_completed": steps_executed,
        "score": float(score),
        "rewards": episode_rewards,
        "summary": summary,
        "config": {
            "model": MODEL_NAME,
            "steps": SIMULATION_STEPS,
            "seed": RANDOM_SEED,
        },
    }


def main() -> Dict[str, Any]:
    try:
        return run()
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


if __name__ == "__main__":
    results = main()
    print(json.dumps(results, indent=2))
    sys.exit(0 if results.get("status") == "success" else 1)
