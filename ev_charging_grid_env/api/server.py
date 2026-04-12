"""FastAPI service exposing the OpenEnv environment."""

from __future__ import annotations

from typing import Any

import numpy as np
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ev_charging_grid_env.envs import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.ui import render_dashboard_html

app = FastAPI(title="EV Charging Grid Optimizer", version="1.0.0")
_ENV = MultiAgentEVChargingGridEnv()


class ResetRequest(BaseModel):
    seed: int | None = None
    task_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class StepRequest(BaseModel):
    action: dict[str, Any]


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


def get_env() -> MultiAgentEVChargingGridEnv:
    return _ENV


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    state = get_env().state()
    metrics = get_env()._metrics_snapshot()
    snapshot = {
        "task_id": metrics["task_id"],
        "step": get_env().current_step,
        "queue_length": int(sum(state["queue_lengths"])),
        "vehicles_served": int(metrics["vehicles_served"]),
    }
    return render_dashboard_html(snapshot)


@app.get("/health")
def health() -> dict[str, Any]:
    env = get_env()
    return {"status": "ok", "task_id": env.task_id, "step": env.current_step}


@app.post("/reset")
def reset(request: ResetRequest) -> dict[str, Any]:
    global _ENV
    config = dict(request.config)
    if request.task_id:
        config["task_id"] = request.task_id
    _ENV = MultiAgentEVChargingGridEnv(config=config)
    observation, info = _ENV.reset(seed=request.seed, options=config)
    return {
        "observation": _to_jsonable(observation),
        "info": _to_jsonable(info),
        "success": True,
    }


@app.post("/step")
def step(request: StepRequest) -> dict[str, Any]:
    observation, reward, terminated, truncated, info = get_env().step(request.action)
    return {
        "observation": _to_jsonable(observation),
        "reward": float(reward),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "info": _to_jsonable(info),
        "success": True,
    }


@app.get("/state")
def state() -> dict[str, Any]:
    observation = get_env().state()
    return {"observation": _to_jsonable(observation), "success": True}


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
