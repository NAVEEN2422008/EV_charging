"""OpenEnv-compatible submission graders with task-specific scoring."""

from __future__ import annotations

from typing import Any


def _clip01(value: float) -> float:
    """Clip value to [0, 1] range."""
    return max(0.0, min(1.0, float(value)))


def grade_episode(metrics: dict[str, Any]) -> float:
    """Return the mandatory normalized score in [0, 1].

    Uses weighted combination of:
    - Service ratio (40%): vehicles served / vehicles seen
    - Solar usage ratio (30%): solar energy / total energy
    - Wait time efficiency (30%): 1 - (normalized wait time)
    """
    served_ratio = float(metrics.get("served_ratio", 0.0))
    solar_usage_ratio = float(metrics.get("solar_usage_ratio", 0.0))
    normalized_wait_time = float(metrics.get("normalized_wait_time", 1.0))

    score = (
        0.4 * _clip01(served_ratio)
        + 0.3 * _clip01(solar_usage_ratio)
        + 0.3 * _clip01(1.0 - normalized_wait_time)
    )
    return _clip01(score)


def grade_easy_task(metrics: dict[str, Any], episode_steps: int | None = None) -> float:
    """Grade easy task: lenient thresholds.

    Easy success: >85% served + >40% solar + <8min wait.
    Bonus: emergency service rate.
    """
    base_score = grade_episode(metrics)

    served_ratio = float(metrics.get("served_ratio", 0.0))
    solar_ratio = float(metrics.get("solar_usage_ratio", 0.0))
    avg_wait = float(metrics.get("average_wait_time", 0.0))
    emergency_seen = float(metrics.get("emergency_seen", 0.0))
    emergency_served = float(metrics.get("emergency_served", 0.0))

    # Bonus for exceeding easy targets
    bonus = 0.0
    if served_ratio > 0.85:
        bonus += 0.05
    if solar_ratio > 0.4:
        bonus += 0.05
    if avg_wait < 8.0:
        bonus += 0.05

    # Emergency bonus
    if emergency_seen > 0:
        emergency_ratio = emergency_served / emergency_seen
        if emergency_ratio > 0.9:
            bonus += 0.03

    return _clip01(base_score + bonus)


def grade_medium_task(metrics: dict[str, Any], episode_steps: int | None = None) -> float:
    """Grade medium task: balanced difficulty.

    Medium success: >70% served + >50% solar + <12min wait.
    Bonus: balanced performance across metrics.
    """
    base_score = grade_episode(metrics)

    served_ratio = float(metrics.get("served_ratio", 0.0))
    solar_ratio = float(metrics.get("solar_usage_ratio", 0.0))
    avg_wait = float(metrics.get("average_wait_time", 0.0))
    emergency_seen = float(metrics.get("emergency_seen", 0.0))
    emergency_served = float(metrics.get("emergency_served", 0.0))

    # Bonus for reaching medium targets
    bonus = 0.0
    if served_ratio > 0.70:
        bonus += 0.05
    if solar_ratio > 0.50:
        bonus += 0.05
    if avg_wait < 12.0:
        bonus += 0.05

    # Emergency bonus
    if emergency_seen > 0:
        emergency_ratio = emergency_served / emergency_seen
        if emergency_ratio > 0.85:
            bonus += 0.03

    return _clip01(base_score + bonus)


def grade_hard_task(metrics: dict[str, Any], episode_steps: int | None = None) -> float:
    """Grade hard task: challenging constraints.

    Hard success: >60% served + >40% solar + <16min wait.
    Emphasis on challenging environment, same bonus structure as easy/medium.
    """
    base_score = grade_episode(metrics)

    served_ratio = float(metrics.get("served_ratio", 0.0))
    solar_ratio = float(metrics.get("solar_usage_ratio", 0.0))
    avg_wait = float(metrics.get("average_wait_time", 0.0))
    emergency_seen = float(metrics.get("emergency_seen", 0.0))
    emergency_served = float(metrics.get("emergency_served", 0.0))

    # Bonus for reaching hard targets
    bonus = 0.0
    if served_ratio > 0.60:
        bonus += 0.05
    if solar_ratio > 0.40:
        bonus += 0.05
    if avg_wait < 16.0:
        bonus += 0.05

    # Emergency bonus
    if emergency_seen > 0:
        emergency_ratio = emergency_served / emergency_seen
        if emergency_ratio > 0.80:
            bonus += 0.03

    return _clip01(base_score + bonus)

