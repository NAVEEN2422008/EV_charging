"""Reward and metrics logic for EV charging grid optimization."""

from __future__ import annotations

import numpy as np
from typing import Any


def compute_step_reward(state: dict[str, Any], events: dict[str, float], config: dict[str, float]) -> float:
    """Compute scalar reward from weighted objective terms."""
    waiting_weight = float(config.get("queue_penalty_weight", 0.15))
    timeout_weight = float(config.get("timeout_penalty_weight", 2.5))
    overload_weight = float(config.get("grid_overload_penalty_weight", 0.04))
    solar_weight = float(config.get("solar_priority_weight", 0.3))
    emergency_bonus = float(config.get("emergency_priority_bonus", 4.0))
    completion_bonus = float(config.get("completion_reward_weight", 1.8))
    fast_service_bonus = float(config.get("fast_service_weight", 0.08))

    mean_wait = float(state.get("mean_wait_time", 0.0))
    timed_out = float(events.get("timed_out_count", 0.0))
    overload_kw = max(0.0, float(state.get("total_grid_kw_used", 0.0)) - float(state.get("grid_limit_kw", 0.0)))
    solar_kwh = float(events.get("solar_kwh_used", 0.0))
    emergency_served = float(events.get("emergency_served", 0.0))
    completed = float(events.get("vehicles_completed", 0.0))
    quick_service = float(events.get("quick_service_score", 0.0))
    emergency_missed = float(events.get("emergency_missed", 0.0))

    travel_weight = float(config.get("travel_distance_penalty_weight", 0.08))
    reward_clip = float(config.get("reward_clip", 50.0))
    reward = 0.0
    reward -= waiting_weight * mean_wait
    reward -= timeout_weight * timed_out
    reward -= overload_weight * overload_kw
    reward += solar_weight * solar_kwh
    reward += emergency_bonus * emergency_served
    reward += completion_bonus * completed
    reward += fast_service_bonus * quick_service
    reward -= emergency_bonus * 1.2 * emergency_missed
    reward -= travel_weight * float(events.get("travel_distance_km", 0.0))
    # Clip to the configured reward range so extreme values remain bounded.
    reward = np.clip(reward, -reward_clip, reward_clip)
    # Normalize to [0, 1] range for OpenEnv compatibility using the clipping bound
    normalized_reward = (reward + reward_clip) / (2.0 * reward_clip)
    return float(np.clip(normalized_reward, 0.0, 1.0))


def compute_episode_summary_metrics(episode_events: dict[str, float], episode_steps: int) -> dict[str, float]:
    """Aggregate episode-level analytics for logs and comparisons."""
    steps = max(1, episode_steps)
    total_energy = float(episode_events.get("total_energy_kwh", 0.0))
    solar_energy = float(episode_events.get("solar_energy_kwh", 0.0))
    total_wait_time = float(episode_events.get("total_wait_time", 0.0))
    vehicles_seen = max(1.0, float(episode_events.get("vehicles_seen", 0.0)))
    total_slots = max(1.0, float(episode_events.get("total_slots_time", 0.0)))
    occupied_slots = float(episode_events.get("occupied_slots_time", 0.0))

    return {
        "average_wait_time": total_wait_time / vehicles_seen,
        "solar_utilization_pct": 100.0 * (solar_energy / total_energy) if total_energy > 0 else 0.0,
        "station_utilization_pct": 100.0 * (occupied_slots / total_slots),
        "emergency_served": float(episode_events.get("emergency_served", 0.0)),
        "emergency_missed": float(episode_events.get("emergency_missed", 0.0)),
        "total_energy_kwh": total_energy,
        "mean_reward_per_step": float(episode_events.get("total_reward", 0.0)) / steps,
    }
