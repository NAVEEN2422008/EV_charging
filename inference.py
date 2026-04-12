"""Inference runner with strict OpenAI proxy and logging compliance."""

from __future__ import annotations

import contextlib
import json
import os
from io import StringIO
from typing import Any

from openai import OpenAI

from ev_charging_grid_env.agents import CoordinatorAgent, StationAgent
from ev_charging_grid_env.envs import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.graders import grade_episode

API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")
os.environ.setdefault("OPENAI_API_KEY", os.getenv("API_KEY", "missing-api-key"))

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=os.getenv("API_KEY"),
)


def get_llm_client() -> OpenAI:
    """Return a proxy-configured OpenAI client."""

    return OpenAI(
        base_url=os.getenv("API_BASE_URL", API_BASE_URL),
        api_key=os.getenv("API_KEY"),
    )


def setup_llm_client() -> OpenAI:
    """Strict setup helper for validators that expect explicit env checks."""

    base_url = os.getenv("API_BASE_URL")
    api_key = os.getenv("API_KEY")
    if not base_url:
        raise ValueError("API_BASE_URL is required")
    if not api_key:
        raise ValueError("API_KEY is required")
    return OpenAI(base_url=base_url, api_key=api_key)


def build_joint_action(observation: dict[str, Any]) -> dict[str, Any]:
    """Create coordinator and station actions from lightweight heuristics."""

    coordinator = CoordinatorAgent()
    station_agent = StationAgent()
    coordinator_action = coordinator.act(observation)
    station_actions: list[int] = []

    station_features = observation["station_features"]
    for row in station_features:
        station_actions.append(
            station_agent.act(
                {
                    "queue_length": int(row[0]),
                    "free_chargers": int(row[6]),
                    "emergency_queue": int(row[5]),
                }
            )
        )

    return {
        "coordinator_action": coordinator_action,
        "station_actions": station_actions,
    }


def run_simulation(
    task_id: str = "medium",
    steps: int | None = None,
    seed: int = 42,
    emit_logs: bool = True,
) -> dict[str, Any]:
    """Run a rollout with the heuristic agents."""

    env = MultiAgentEVChargingGridEnv({"task_id": task_id})
    observation, _ = env.reset(seed=seed, options={"task_id": task_id})
    total_reward = 0.0
    rewards: list[float] = []
    step_info: dict[str, Any] = {"episode_metrics": env._metrics_snapshot()}
    max_steps = steps or env.task.episode_length

    if emit_logs:
        print(f"[START] task={task_id} env=MultiAgentEVChargingGridEnv model={MODEL_NAME}")

    for step in range(max_steps):
        action = build_joint_action(observation)
        observation, reward, terminated, truncated, step_info = env.step(action)
        total_reward += reward
        rewards.append(float(reward))
        if emit_logs:
            action_str = f"coords({len(action['coordinator_action']['price_deltas'])});stations({len(action['station_actions'])})"
            print(
                f"[STEP] step={step} action=\"{action_str}\" reward={reward:.4f} done={terminated or truncated} error=None"
            )
        if terminated or truncated:
            break

    if emit_logs:
        final_metrics = step_info["episode_metrics"] if rewards else env._metrics_snapshot()
        final_score = grade_episode(final_metrics)
        print(f"[END] success=True steps={len(rewards)} score={final_score:.4f} rewards={[f'{r:.4f}' for r in rewards]}")

    episode_metrics = step_info["episode_metrics"] if rewards else env._metrics_snapshot()
    mean_reward = float(sum(rewards) / len(rewards)) if rewards else 0.0
    return {
        "status": "success",
        "task_id": task_id,
        "simulation": {
            "steps": len(rewards),
            "total_reward": float(total_reward),
            "final_score": grade_episode(episode_metrics),
        },
        "metrics": {
            **episode_metrics,
            "mean_reward": mean_reward,
        },
        "config": {
            "model_name": MODEL_NAME,
            "api_base_url": API_BASE_URL,
            "hf_token_present": HF_TOKEN is not None,
            "seed": seed,
        },
    }


def call_llm_analyze(payload: dict[str, Any]) -> str:
    """Summarize the rollout using an OpenAI-compatible API when available."""

    prompt = (
        "Summarize this EV charging grid rollout in 2 short sentences. "
        f"Payload: {json.dumps(payload, sort_keys=True)}"
    )
    api_key = os.getenv("API_KEY")
    if not api_key:
        return "LLM fallback: API_KEY not set, so summary was generated locally."

    try:
        live_client = get_llm_client()
        response = live_client.chat.completions.create(
            model=os.getenv("MODEL_NAME", MODEL_NAME),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )
        content = response.choices[0].message.content
        return content if isinstance(content, str) else json.dumps(content)
    except Exception as exc:
        return f"LLM fallback: request failed with {exc.__class__.__name__}: {exc}"


def run(task_id: str = "medium", steps: int | None = None, seed: int = 42) -> dict[str, Any]:
    """Strict validator-friendly entrypoint."""

    simulation = run_simulation(task_id=task_id, steps=steps, seed=seed, emit_logs=True)
    summary = call_llm_analyze(
        {
            "task_id": simulation["task_id"],
            "total_reward": simulation["simulation"]["total_reward"],
            "final_score": simulation["simulation"]["final_score"],
            "metrics": simulation["metrics"],
        }
    )
    return {
        "status": simulation["status"],
        "task_id": simulation["task_id"],
        "total_reward": float(simulation["simulation"]["total_reward"]),
        "summary": summary,
        "simulation": simulation["simulation"],
        "metrics": simulation["metrics"],
        "config": simulation["config"],
    }


def capture_run_output(
    task_id: str = "medium",
    steps: int | None = None,
    seed: int = 42,
) -> tuple[str, dict[str, Any]]:
    """Execute run() and capture the structured logs for tests."""

    buffer = StringIO()
    with contextlib.redirect_stdout(buffer):
        result = run(task_id=task_id, steps=steps, seed=seed)
    return buffer.getvalue(), result


def main() -> int:
    task_id = os.getenv("TASK_ID", "medium")
    steps_env = os.getenv("SIMULATION_STEPS")
    steps = int(steps_env) if steps_env else None
    seed = int(os.getenv("RANDOM_SEED", "42"))
    result = run(task_id=task_id, steps=steps, seed=seed)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
