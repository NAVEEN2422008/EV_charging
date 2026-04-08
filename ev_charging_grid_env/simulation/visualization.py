"""Visualization helpers for simulation rollouts."""

from __future__ import annotations

from typing import Sequence

import matplotlib.pyplot as plt


def print_episode_table(metrics: dict[str, float]) -> None:
    """Print compact CLI table of key episode metrics."""
    keys = [
        "total_reward",
        "average_wait_time",
        "solar_utilization_pct",
        "station_utilization_pct",
        "emergency_served",
        "emergency_missed",
        "total_energy_kwh",
    ]
    for key in keys:
        print(f"{key:>24}: {metrics.get(key, 0.0):.3f}")


def plot_reward_curve(reward_history: Sequence[float]) -> None:
    """Plot per-timestep reward history."""
    plt.figure(figsize=(8, 4))
    plt.plot(reward_history, label="Reward per timestep")
    plt.xlabel("Timestep")
    plt.ylabel("Reward")
    plt.title("EV Charging Grid Reward Curve")
    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_energy_split(solar_kwh: Sequence[float], grid_kwh: Sequence[float]) -> None:
    """Plot solar vs grid energy usage over time."""
    plt.figure(figsize=(8, 4))
    plt.plot(solar_kwh, label="Solar kWh")
    plt.plot(grid_kwh, label="Grid kWh")
    plt.xlabel("Timestep")
    plt.ylabel("Energy (kWh)")
    plt.title("Energy Source Split")
    plt.legend()
    plt.tight_layout()
    plt.show()
