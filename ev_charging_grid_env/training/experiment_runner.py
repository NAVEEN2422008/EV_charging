"""Multi-seed experiment runner with checkpointing and logs."""

from __future__ import annotations

import argparse
import dataclasses
import json
from dataclasses import asdict
from pathlib import Path

import torch
import yaml

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv
from ev_charging_grid_env.training.algorithms.mappo_trainer import MAPPOConfig, MAPPOTrainer
from ev_charging_grid_env.training.algorithms.ppo_trainer import PPOConfig, PPOTrainer


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _filter_dataclass_kwargs(cfg: dict, dataclass_type: type) -> dict:
    """Filter a config dict to only keys that are valid fields of the dataclass.

    Prevents TypeError when config has extra environment keys alongside training keys.
    """
    valid_keys = {f.name for f in dataclasses.fields(dataclass_type)}
    return {k: v for k, v in cfg.items() if k in valid_keys}


def run_experiment(
    config_path: Path,
    algorithm: str,
    seeds: list[int],
    output_dir: Path,
) -> None:
    """Run multi-seed RL experiment with checkpointing.

    Supports both flat configs (all keys at top level) and nested configs
    with ``env:`` and ``training:`` sub-sections.
    """
    cfg = load_yaml(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Flat config: use the whole cfg as env config and allow top-level
    # training hyperparameters to be filtered for the trainer.
    # Nested config: use env and training sub-sections.
    env_cfg: dict = cfg.get("env", cfg)
    if "training" in cfg:
        train_cfg: dict = cfg["training"]
    elif "env" in cfg:
        train_cfg = {}
    else:
        train_cfg = cfg

    all_results: list[dict] = []

    for seed in seeds:
        run_dir = output_dir / f"{algorithm}_seed{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[Experiment] Starting {algorithm.upper()} | seed={seed} | run_dir={run_dir}")

        if algorithm == "ppo":
            env = MultiAgentEVChargingGridEnv(config=env_cfg)
            filtered = _filter_dataclass_kwargs(train_cfg, PPOConfig)
            trainer_cfg = PPOConfig(**{**filtered, "seed": seed})
            trainer = PPOTrainer(env, trainer_cfg, run_dir=run_dir)
            result = trainer.train()
            ckpt_path = run_dir / "checkpoint.pt"
            torch.save(trainer.model.state_dict(), ckpt_path)
            print(f"  [OK] Checkpoint saved -> {ckpt_path}")
            result["config"] = asdict(trainer_cfg)
            result["checkpoint"] = str(ckpt_path)

        elif algorithm in {"mappo", "independent_ppo"}:
            env = PettingZooEVChargingEnv(config=env_cfg)
            filtered = _filter_dataclass_kwargs(train_cfg, MAPPOConfig)
            trainer_cfg = MAPPOConfig(**{**filtered, "seed": seed})
            trainer = MAPPOTrainer(env, trainer_cfg, run_dir=run_dir)
            result = trainer.train()
            station_ckpt = run_dir / "station_policy.pt"
            coord_ckpt = run_dir / "coordinator_policy.pt"
            torch.save(trainer.station_policy.state_dict(), station_ckpt)
            torch.save(trainer.coordinator_policy.state_dict(), coord_ckpt)
            print(f"  [OK] Station checkpoint -> {station_ckpt}")
            print(f"  [OK] Coordinator checkpoint -> {coord_ckpt}")
            result["config"] = asdict(trainer_cfg)
            result["mode"] = (
                "shared_station_policy" if algorithm == "mappo" else "independent_baseline_approx"
            )
            result["checkpoints"] = {
                "station_policy": str(station_ckpt),
                "coordinator_policy": str(coord_ckpt),
            }

        else:
            raise ValueError(f"Unsupported algorithm: {algorithm!r}. Choose ppo, mappo, or independent_ppo.")

        result["seed"] = seed
        result["algorithm"] = algorithm
        all_results.append(result)

        result_path = run_dir / "result.json"
        with result_path.open("w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)
        print(f"  [OK] Result saved -> {result_path}")
        print(f"  mean_reward={result.get('mean_update_reward', 0.0):.4f}  "
              f"last_reward={result.get('last_update_reward', 0.0):.4f}")

    summary_path = output_dir / f"{algorithm}_summary.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump({"algorithm": algorithm, "results": all_results}, fh, indent=2, default=str)
    print(f"\n[OK] Experiment complete. Summary -> {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EV Charging Grid RL Experiment Runner — trains PPO/MAPPO agents."
    )
    parser.add_argument("--config", type=Path, required=True, help="Path to YAML environment config")
    parser.add_argument(
        "--algorithm",
        type=str,
        choices=["ppo", "mappo", "independent_ppo"],
        default="ppo",
        help="RL algorithm to train",
    )
    parser.add_argument(
        "--seeds", type=int, nargs="+", default=[42, 43, 44], help="Random seeds for multi-run"
    )
    parser.add_argument("--output", type=Path, default=Path("runs"), help="Directory for outputs")
    args = parser.parse_args()
    run_experiment(args.config, args.algorithm, args.seeds, args.output)


if __name__ == "__main__":
    main()
