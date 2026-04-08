"""Centralized PPO trainer for joint-action environment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import optim
from torch.distributions import Categorical
from torch.utils.tensorboard import SummaryWriter

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.training.models.actor_critic import CentralizedActorCritic
from ev_charging_grid_env.training.utils.preprocessing import RunningNorm, flatten_observation
from ev_charging_grid_env.training.utils.rollout_buffer import RolloutBuffer


@dataclass
class PPOConfig:
    total_steps: int = 40_000
    rollout_steps: int = 512
    batch_size: int = 128
    epochs: int = 4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_coef: float = 0.2
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    max_grad_norm: float = 0.5
    lr: float = 3e-4
    reward_norm: bool = True
    lr_anneal: bool = True
    min_lr_scale: float = 0.1
    seed: int = 42


class PPOTrainer:
    """PPO training loop for centralized control."""

    def __init__(self, env: MultiAgentEVChargingGridEnv, config: PPOConfig, run_dir: Path) -> None:
        self.env = env
        self.cfg = config
        self.device = torch.device("cpu")
        obs, _ = self.env.reset(seed=self.cfg.seed)
        obs_vec = flatten_observation(obs)
        self.obs_norm = RunningNorm()
        self.obs_norm.update(obs_vec)
        self.model = CentralizedActorCritic(obs_dim=obs_vec.shape[0], num_stations=self.env.num_stations).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=self.cfg.lr)
        self.num_updates = max(1, self.cfg.total_steps // self.cfg.rollout_steps)
        self.scheduler = optim.lr_scheduler.LambdaLR(
            self.optimizer,
            lr_lambda=(lambda step: max(self.cfg.min_lr_scale, 1.0 - (step / max(1, self.num_updates))))
            if self.cfg.lr_anneal
            else (lambda _: 1.0),
        )
        self.buffer = RolloutBuffer(gamma=self.cfg.gamma, gae_lambda=self.cfg.gae_lambda)
        self.writer = SummaryWriter(log_dir=str(run_dir / "tensorboard"))
        self.reward_norm = RunningNorm()

    def _sample_action(self, obs_vec: np.ndarray) -> tuple[np.ndarray, float, float]:
        x = torch.as_tensor(obs_vec[None, :], dtype=torch.float32, device=self.device)
        price_logits, emergency_logits, station_logits, value = self.model(x)
        # price_logits: [1, num_stations, 3]
        # emergency_logits: [1, num_stations + 1]
        # station_logits: [1, num_stations, 4]
        price_logits_sq = price_logits.squeeze(0)  # [num_stations, 3]
        emergency_logits_sq = emergency_logits.squeeze(0)  # [num_stations + 1]
        station_logits_sq = station_logits.squeeze(0)  # [num_stations, 4]
        
        # Sample price deltas for each station
        price_dist = Categorical(logits=price_logits_sq)
        price_action = price_dist.sample()
        price_logprobs = price_dist.log_prob(price_action).sum()

        emergency_dist = Categorical(logits=emergency_logits_sq)
        emergency_action = emergency_dist.sample()
        emergency_logprob = emergency_dist.log_prob(emergency_action)

        station_dist = Categorical(logits=station_logits_sq)
        station_action = station_dist.sample()
        station_logprobs = station_dist.log_prob(station_action).sum()

        log_prob = price_logprobs + emergency_logprob + station_logprobs
        action_vec = torch.cat([price_action, emergency_action.view(1), station_action]).cpu().numpy()
        return action_vec.astype(np.int64), float(log_prob.item()), float(value.item())

    def train(self) -> dict[str, float]:
        obs, _ = self.env.reset(seed=self.cfg.seed)
        episode_reward = 0.0
        global_step = 0
        reward_trace: list[float] = []
        for update in range(self.num_updates):
            self.buffer.clear()
            for _ in range(self.cfg.rollout_steps):
                obs_vec_raw = flatten_observation(obs)
                self.obs_norm.update(obs_vec_raw)
                obs_vec = self.obs_norm.normalize(obs_vec_raw)
                action_vec, log_prob, value = self._sample_action(obs_vec)
                joint_action = {
                    "coordinator_action": {
                        "price_deltas": action_vec[: self.env.num_stations],
                        "emergency_target_station": int(action_vec[self.env.num_stations]),
                    },
                    "station_actions": action_vec[self.env.num_stations + 1 :],
                }
                next_obs, reward, terminated, truncated, _ = self.env.step(joint_action)
                done = bool(terminated or truncated)
                self.buffer.observations.append(obs_vec)
                self.buffer.actions.append(action_vec)
                self.buffer.log_probs.append(log_prob)
                self.buffer.values.append(value)
                reward_value = float(reward)
                if self.cfg.reward_norm:
                    r_vec = np.asarray([reward_value], dtype=np.float32)
                    self.reward_norm.update(r_vec)
                    reward_value = float(self.reward_norm.normalize(r_vec)[0])
                self.buffer.rewards.append(reward_value)
                self.buffer.dones.append(done)
                obs = next_obs if not done else self.env.reset()[0]
                episode_reward += float(reward)
                global_step += 1
            self.buffer.compute_returns_and_advantages(last_value=0.0)
            stats = self._update_policy()
            self.writer.add_scalar("train/episode_reward", episode_reward, update)
            self.writer.add_scalar("train/policy_loss", stats["policy_loss"], update)
            self.writer.add_scalar("train/value_loss", stats["value_loss"], update)
            self.writer.add_scalar("train/entropy", stats["entropy"], update)
            self.writer.add_scalar("train/lr", self.optimizer.param_groups[0]["lr"], update)
            self.scheduler.step()
            reward_trace.append(float(episode_reward))
            episode_reward = 0.0
        return {
            "total_steps": float(global_step),
            "mean_update_reward": float(np.mean(reward_trace)) if reward_trace else 0.0,
            "last_update_reward": float(reward_trace[-1]) if reward_trace else 0.0,
        }

    def _update_policy(self) -> dict[str, float]:
        obs_arr, action_arr, old_logp_arr, returns_arr, adv_arr = self.buffer.as_arrays()
        adv_arr = (adv_arr - adv_arr.mean()) / (adv_arr.std() + 1e-8)
        idxs = np.arange(obs_arr.shape[0])
        policy_losses: list[float] = []
        value_losses: list[float] = []
        entropies: list[float] = []
        for _ in range(self.cfg.epochs):
            np.random.shuffle(idxs)
            for start in range(0, len(idxs), self.cfg.batch_size):
                mb = idxs[start : start + self.cfg.batch_size]
                obs_t = torch.as_tensor(obs_arr[mb], dtype=torch.float32, device=self.device)
                act_t = torch.as_tensor(action_arr[mb], dtype=torch.int64, device=self.device)
                old_logp_t = torch.as_tensor(old_logp_arr[mb], dtype=torch.float32, device=self.device)
                ret_t = torch.as_tensor(returns_arr[mb], dtype=torch.float32, device=self.device)
                adv_t = torch.as_tensor(adv_arr[mb], dtype=torch.float32, device=self.device)

                price_logits, emergency_logits, station_logits, value = self.model(obs_t)
                price_dist = Categorical(logits=price_logits)
                emergency_dist = Categorical(logits=emergency_logits)
                station_dist = Categorical(logits=station_logits)

                price_action = act_t[:, : self.env.num_stations]
                emergency_action = act_t[:, self.env.num_stations]
                station_action = act_t[:, self.env.num_stations + 1 :]

                new_logp = (
                    price_dist.log_prob(price_action).sum(-1)
                    + emergency_dist.log_prob(emergency_action)
                    + station_dist.log_prob(station_action).sum(-1)
                )
                entropy = (
                    price_dist.entropy().sum(-1).mean()
                    + emergency_dist.entropy().mean()
                    + station_dist.entropy().sum(-1).mean()
                )
                ratio = torch.exp(new_logp - old_logp_t)
                pg_loss1 = ratio * adv_t
                pg_loss2 = torch.clamp(ratio, 1 - self.cfg.clip_coef, 1 + self.cfg.clip_coef) * adv_t
                policy_loss = -torch.min(pg_loss1, pg_loss2).mean()
                value_loss = ((value - ret_t) ** 2).mean()
                loss = policy_loss + self.cfg.value_coef * value_loss - self.cfg.entropy_coef * entropy
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.cfg.max_grad_norm)
                self.optimizer.step()
                policy_losses.append(float(policy_loss.item()))
                value_losses.append(float(value_loss.item()))
                entropies.append(float(entropy.item()))
        return {
            "policy_loss": float(np.mean(policy_losses)) if policy_losses else 0.0,
            "value_loss": float(np.mean(value_losses)) if value_losses else 0.0,
            "entropy": float(np.mean(entropies)) if entropies else 0.0,
        }
