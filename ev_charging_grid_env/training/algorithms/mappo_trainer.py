"""MAPPO and Independent PPO trainers on PettingZoo interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import optim
from torch.distributions import Categorical
from torch.utils.tensorboard import SummaryWriter

from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv
from ev_charging_grid_env.training.models.actor_critic import MAPPOStationPolicy, MLP
from ev_charging_grid_env.training.utils.action_utils import build_station_action_mask
from ev_charging_grid_env.training.utils.preprocessing import RunningNorm, flatten_observation
from ev_charging_grid_env.training.utils.rollout_buffer import RolloutBuffer


@dataclass
class MAPPOConfig:
    total_cycles: int = 10_000
    rollout_cycles: int = 256
    epochs: int = 4
    batch_size: int = 128
    lr: float = 3e-4
    reward_norm: bool = True
    lr_anneal: bool = True
    min_lr_scale: float = 0.1
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_coef: float = 0.2
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    max_grad_norm: float = 0.5
    seed: int = 42


class MAPPOTrainer:
    """MAPPO with shared station actor and centralized critic."""

    def __init__(self, env: PettingZooEVChargingEnv, config: MAPPOConfig, run_dir: Path) -> None:
        self.env = env
        self.cfg = config
        self.device = torch.device("cpu")
        self.env.reset(seed=self.cfg.seed)
        global_obs = flatten_observation(self.env.observe("coordinator"))
        station_obs = self.env.observe("station_0")
        local_dim = int(
            np.asarray(station_obs["local_features"], dtype=np.float32).shape[0] + 3 + len(station_obs["neighbor_queue_lengths"])
        )
        # Use local critic context for robust shape consistency in this baseline MAPPO implementation.
        self.station_policy = MAPPOStationPolicy(local_obs_dim=local_dim, global_obs_dim=local_dim).to(self.device)
        self.coordinator_policy = MLP(global_obs.shape[0], 256, self.env.action_space("coordinator")["emergency_target_station"].n).to(self.device)
        self.optim = optim.Adam(list(self.station_policy.parameters()) + list(self.coordinator_policy.parameters()), lr=self.cfg.lr)
        total_updates = max(1, self.cfg.total_cycles // max(1, self.cfg.rollout_cycles))
        self.scheduler = optim.lr_scheduler.LambdaLR(
            self.optim,
            lr_lambda=(lambda step: max(self.cfg.min_lr_scale, 1.0 - (step / max(1, total_updates))))
            if self.cfg.lr_anneal
            else (lambda _: 1.0),
        )
        self.buffer = RolloutBuffer(gamma=self.cfg.gamma, gae_lambda=self.cfg.gae_lambda)
        self.writer = SummaryWriter(log_dir=str(run_dir / "tensorboard"))
        self.reward_norm = RunningNorm()

    def _flatten_station_obs(self, obs: dict[str, Any]) -> np.ndarray:
        return np.concatenate(
            [
                np.asarray(obs["local_features"], dtype=np.float32),
                np.asarray(obs["global_context"], dtype=np.float32),
                np.asarray(obs["neighbor_queue_lengths"], dtype=np.float32),
            ]
        ).astype(np.float32)

    def train(self) -> dict[str, float]:
        total_reward = 0.0
        cycles = 0
        reward_trace: list[float] = []
        updates = max(1, self.cfg.total_cycles // max(1, self.cfg.rollout_cycles))
        for _ in range(updates):
            self.buffer.clear()
            self.env.reset(seed=self.cfg.seed + cycles)
            collected_cycles = 0
            for agent in self.env.agent_iter(max_iter=self.cfg.rollout_cycles * len(self.env.possible_agents) * 3):
                obs = self.env.observe(agent)
                if self.env.terminations.get(agent, False) or self.env.truncations.get(agent, False):
                    self.env.step(None)
                    continue
                if agent == "coordinator":
                    global_vec = flatten_observation(obs)
                    logits = self.coordinator_policy(torch.as_tensor(global_vec[None, :], dtype=torch.float32))
                    dist = Categorical(logits=logits.squeeze(0))
                    target = dist.sample()
                    action = {
                        "price_deltas": np.ones(self.env.gym_env.num_stations, dtype=np.int64),
                        "emergency_target_station": int(target.item()),
                    }
                    self.env.step(action)
                else:
                    local_vec = self._flatten_station_obs(obs)
                    local_t = torch.as_tensor(local_vec[None, :], dtype=torch.float32, device=self.device)
                    logits = self.station_policy.act_logits(local_t).squeeze(0)
                    mask = torch.as_tensor(build_station_action_mask(obs), dtype=torch.float32, device=self.device)
                    logits = logits + (mask + 1e-8).log()
                    dist = Categorical(logits=logits)
                    action = dist.sample()
                    log_prob = dist.log_prob(action)
                    value = self.station_policy.value(local_t).squeeze(0)
                    self.env.step(int(action.item()))
                    reward = float(self.env.rewards.get(agent, 0.0))
                    if self.cfg.reward_norm:
                        r_vec = np.asarray([reward], dtype=np.float32)
                        self.reward_norm.update(r_vec)
                        reward = float(self.reward_norm.normalize(r_vec)[0])
                    done = bool(self.env.terminations.get(agent, False) or self.env.truncations.get(agent, False))
                    self.buffer.observations.append(local_vec)
                    self.buffer.actions.append(np.asarray([int(action.item())], dtype=np.int64))
                    self.buffer.log_probs.append(float(log_prob.item()))
                    self.buffer.values.append(float(value.item()))
                    self.buffer.rewards.append(reward)
                    self.buffer.dones.append(done)
                    total_reward += reward
                    if agent == self.env.possible_agents[-1]:
                        cycles += 1
                        collected_cycles += 1
                        if collected_cycles >= self.cfg.rollout_cycles:
                            break
            self.buffer.compute_returns_and_advantages()
            stats = self._update_station_policy()
            self.writer.add_scalar("train/reward", total_reward / max(1, self.cfg.rollout_cycles), cycles)
            self.writer.add_scalar("train/policy_loss", stats["policy_loss"], cycles)
            self.writer.add_scalar("train/value_loss", stats["value_loss"], cycles)
            self.writer.add_scalar("train/entropy", stats["entropy"], cycles)
            self.writer.add_scalar("train/lr", self.optim.param_groups[0]["lr"], cycles)
            reward_trace.append(float(total_reward / max(1, self.cfg.rollout_cycles)))
            self.scheduler.step()
            total_reward = 0.0
        return {
            "cycles": float(cycles),
            "mean_update_reward": float(np.mean(reward_trace)) if reward_trace else 0.0,
            "last_update_reward": float(reward_trace[-1]) if reward_trace else 0.0,
        }

    def _update_station_policy(self) -> dict[str, float]:
        obs_arr, action_arr, old_logp_arr, returns_arr, adv_arr = self.buffer.as_arrays()
        if len(obs_arr) == 0:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}
        adv_arr = (adv_arr - adv_arr.mean()) / (adv_arr.std() + 1e-8)
        idxs = np.arange(len(obs_arr))
        policy_losses: list[float] = []
        value_losses: list[float] = []
        entropies: list[float] = []
        for _ in range(self.cfg.epochs):
            np.random.shuffle(idxs)
            for start in range(0, len(idxs), self.cfg.batch_size):
                mb = idxs[start : start + self.cfg.batch_size]
                local = torch.as_tensor(obs_arr[mb], dtype=torch.float32, device=self.device)
                action = torch.as_tensor(action_arr[mb].squeeze(-1), dtype=torch.int64, device=self.device)
                old_logp = torch.as_tensor(old_logp_arr[mb], dtype=torch.float32, device=self.device)
                ret = torch.as_tensor(returns_arr[mb], dtype=torch.float32, device=self.device)
                adv = torch.as_tensor(adv_arr[mb], dtype=torch.float32, device=self.device)
                logits = self.station_policy.act_logits(local)
                dist = Categorical(logits=logits)
                new_logp = dist.log_prob(action)
                entropy = dist.entropy().mean()
                ratio = torch.exp(new_logp - old_logp)
                pg_loss = -torch.min(ratio * adv, torch.clamp(ratio, 1 - self.cfg.clip_coef, 1 + self.cfg.clip_coef) * adv).mean()
                value = self.station_policy.critic(local).squeeze(-1)
                value_loss = ((value - ret) ** 2).mean()
                loss = pg_loss + self.cfg.value_coef * value_loss - self.cfg.entropy_coef * entropy
                self.optim.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.station_policy.parameters(), self.cfg.max_grad_norm)
                self.optim.step()
                policy_losses.append(float(pg_loss.item()))
                value_losses.append(float(value_loss.item()))
                entropies.append(float(entropy.item()))
        return {
            "policy_loss": float(np.mean(policy_losses)),
            "value_loss": float(np.mean(value_losses)),
            "entropy": float(np.mean(entropies)),
        }
