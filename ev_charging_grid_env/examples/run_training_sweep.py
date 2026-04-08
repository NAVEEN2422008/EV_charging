"""Run 3 training configurations and auto-select best result."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cmd(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}")


def read_result(path: Path) -> dict:
    if not path.exists():
        return {"total_steps": 0.0}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    out_dir = root / "runs" / "ppo_sweep"
    configs = [
        ("sweep_a", root / "ev_charging_grid_env" / "config" / "training" / "ppo_sweep_a.yaml"),
        ("sweep_b", root / "ev_charging_grid_env" / "config" / "training" / "ppo_sweep_b.yaml"),
        ("sweep_c", root / "ev_charging_grid_env" / "config" / "training" / "ppo_sweep_c.yaml"),
    ]
    scores: dict[str, float] = {}
    for name, cfg_path in configs:
        run_cmd(
            [
                sys.executable,
                "-m",
                "ev_charging_grid_env.training.experiment_runner",
                "--config",
                str(cfg_path),
                "--algorithm",
                "ppo",
                "--seeds",
                "42",
                "--output",
                str(out_dir / name),
            ]
        )
        result_path = out_dir / name / "ppo_seed42" / "result.json"
        result = read_result(result_path)
        score = float(result.get("mean_update_reward", result.get("last_update_reward", result.get("total_steps", 0.0))))
        scores[name] = score

    best_name = max(scores, key=scores.get)
    best_cfg = next(path for name, path in configs if name == best_name)
    summary = {"scores": scores, "best_config_name": best_name, "best_config_path": str(best_cfg)}
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "best_config.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
