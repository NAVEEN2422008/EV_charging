"""Task presets for OpenEnv difficulty levels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskProfile:
    """Scenario-level parameters for a charging-grid episode."""

    id: str
    arrival_lambda: float
    emergency_probability: float
    solar_multiplier: float
    grid_capacity_kw: float
    episode_length: int
    weather_weights: tuple[float, float, float]
    wait_normalizer: float


TASKS: dict[str, TaskProfile] = {
    "easy": TaskProfile(
        id="easy",
        arrival_lambda=3.5,
        emergency_probability=0.01,
        solar_multiplier=1.15,
        grid_capacity_kw=1750.0,
        episode_length=96,
        weather_weights=(0.7, 0.2, 0.1),
        wait_normalizer=8.0,
    ),
    "medium": TaskProfile(
        id="medium",
        arrival_lambda=7.0,
        emergency_probability=0.05,
        solar_multiplier=0.85,
        grid_capacity_kw=1300.0,
        episode_length=120,
        weather_weights=(0.45, 0.35, 0.2),
        wait_normalizer=12.0,
    ),
    "hard": TaskProfile(
        id="hard",
        arrival_lambda=11.0,
        emergency_probability=0.12,
        solar_multiplier=0.55,
        grid_capacity_kw=950.0,
        episode_length=144,
        weather_weights=(0.25, 0.35, 0.4),
        wait_normalizer=16.0,
    ),
}


def get_task_profile(task_id: str | None) -> TaskProfile:
    """Return a validated task profile."""

    resolved = task_id or "medium"
    if resolved not in TASKS:
        valid = ", ".join(sorted(TASKS))
        raise ValueError(f"Unknown task_id={resolved!r}. Expected one of: {valid}")
    return TASKS[resolved]

