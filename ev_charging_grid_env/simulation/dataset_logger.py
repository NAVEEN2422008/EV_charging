"""Offline transition logger for imitation/offline RL datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DatasetLogger:
    """Append-only JSONL logger for environment transitions."""

    def __init__(self, output_path: str | Path) -> None:
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def log_transition(
        self,
        obs: dict[str, Any],
        action: dict[str, Any],
        reward: float,
        next_obs: dict[str, Any],
        done: bool,
        agent_id: str = "centralized",
    ) -> None:
        record = {
            "agent_id": agent_id,
            "reward": reward,
            "done": done,
            "obs": self._to_jsonable(obs),
            "action": self._to_jsonable(action),
            "next_obs": self._to_jsonable(next_obs),
        }
        with self.output_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def _to_jsonable(self, value: Any) -> Any:
        if hasattr(value, "tolist"):
            return value.tolist()
        if isinstance(value, dict):
            return {k: self._to_jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._to_jsonable(v) for v in value]
        return value
