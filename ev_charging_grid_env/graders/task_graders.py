"""Task grader functions for EV Charging Grid environment."""

from __future__ import annotations

from typing import Any


def _normalize_wait_time(avg_wait_time: float, max_acceptable: float = 20.0) -> float:
    """Normalize average wait time to [0.0, 1.0] score (lower wait = higher score).
    
    Args:
        avg_wait_time: Average wait time in timesteps
        max_acceptable: Wait time above this is considered poor (default 20 ts ≈ 2 min)
    
    Returns:
        Score in [0.0, 1.0] where 1.0 is optimal (no wait) and 0.0 is worst
    """
    if avg_wait_time <= 0.0:
        return 1.0
    # Linear decay: at max_acceptable, score = 0.5; at 2*max, score = 0.0
    score = max(0.0, 1.0 - (avg_wait_time / max_acceptable))
    return min(1.0, score)


def _normalize_solar_utilization(solar_pct: float) -> float:
    """Normalize solar utilization percentage to [0.0, 1.0] score.
    
    Args:
        solar_pct: Percentage of energy from solar [0, 100]
    
    Returns:
        Score in [0.0, 1.0] where 1.0 is 100% solar and 0.0 is 0% solar
    """
    return min(1.0, max(0.0, solar_pct / 100.0))


def _normalize_emergency_response(
    emergency_served: float, 
    emergency_missed: float, 
    total_vehicles: float = 100.0
) -> float:
    """Normalize emergency response rate to [0.0, 1.0] score.
    
    Args:
        emergency_served: Count of emergency vehicles served
        emergency_missed: Count of emergency vehicles missed/timed out
        total_vehicles: Typical episode vehicle count (for normalization)
    
    Returns:
        Score in [0.0, 1.0] where 1.0 is perfect emergency handling
    """
    total_emergency = emergency_served + emergency_missed
    if total_emergency <= 0.0:
        # No emergencies is acceptable, return neutral score
        return 0.7
    
    served_rate = emergency_served / total_emergency
    return served_rate  # Direct ratio [0.0, 1.0]


def _normalize_grid_stability(grid_overload_events: float, episode_steps: int = 300) -> float:
    """Normalize grid stability (inverse of overload events) to [0.0, 1.0] score.
    
    Args:
        grid_overload_events: Count of timesteps with grid overload
        episode_steps: Total timesteps in episode
    
    Returns:
        Score in [0.0, 1.0] where 1.0 is no overload and 0.0 is constant overload
    """
    if episode_steps <= 0:
        return 1.0
    
    overload_ratio = grid_overload_events / float(episode_steps)
    # High stability = low overload ratio
    return max(0.0, 1.0 - overload_ratio)


def _normalize_completion_rate(
    vehicles_seen: float, 
    vehicles_completed: float,
    # Note: vehicles_completed must come from episode_stats
) -> float:
    """Normalize vehicle completion rate to [0.0, 1.0] score.
    
    Args:
        vehicles_seen: Total vehicles that arrived
        vehicles_completed: Vehicles that completed charging
    
    Returns:
        Score in [0.0, 1.0] where 1.0 is 100% completion
    """
    if vehicles_seen <= 0.0:
        return 1.0
    
    completion_rate = vehicles_completed / vehicles_seen
    return min(1.0, max(0.0, completion_rate))


def grade_easy_task(metrics: dict[str, Any], episode_steps: int = 300) -> float:
    """Grade easy task: Basic charging grid operation.
    
    Focuses on:
    - Vehicle completion rate (40%)
    - Solar utilization (30%)
    - Service quality / waiting time (30%)
    
    Args:
        metrics: Dictionary with keys from compute_episode_summary_metrics()
                 and episode_stats: average_wait_time, solar_utilization_pct,
                 vehicles_seen, emergency_served, total_reward, grid_overload_events
        episode_steps: Total timesteps in episode
    
    Returns:
        Grade in [0.0, 1.0] where 1.0 is perfect performance
    """
    # Default values if metrics missing
    avg_wait = float(metrics.get("average_wait_time", 10.0))
    solar_pct = float(metrics.get("solar_utilization_pct", 20.0))
    vehicles_seen = float(metrics.get("vehicles_seen", 1.0))
    vehicles_completed = float(metrics.get("vehicles_completed", vehicles_seen * 0.8))
    
    # Normalize components
    wait_score = _normalize_wait_time(avg_wait, max_acceptable=25.0)  # More tolerant for easy
    solar_score = _normalize_solar_utilization(solar_pct)
    completion_score = _normalize_completion_rate(vehicles_seen, vehicles_completed)
    
    # Weighted average for easy task
    grade = (
        0.40 * completion_score +
        0.30 * solar_score +
        0.30 * wait_score
    )
    
    return min(1.0, max(0.0, grade))


def grade_medium_task(metrics: dict[str, Any], episode_steps: int = 300) -> float:
    """Grade medium task: Optimize queue management with dynamic pricing.
    
    Focuses on:
    - Vehicle completion rate (35%)
    - Solar utilization (25%)
    - Service quality / waiting time (20%)
    - Emergency response (20%)
    
    Args:
        metrics: Dictionary with keys from compute_episode_summary_metrics()
                 and episode_stats: average_wait_time, solar_utilization_pct,
                 vehicles_seen, emergency_served, emergency_missed, 
                 total_reward, grid_overload_events
        episode_steps: Total timesteps in episode
    
    Returns:
        Grade in [0.0, 1.0] where 1.0 is perfect performance
    """
    # Default values if metrics missing
    avg_wait = float(metrics.get("average_wait_time", 15.0))
    solar_pct = float(metrics.get("solar_utilization_pct", 30.0))
    vehicles_seen = float(metrics.get("vehicles_seen", 1.0))
    vehicles_completed = float(metrics.get("vehicles_completed", vehicles_seen * 0.85))
    emergency_served = float(metrics.get("emergency_served", 0.0))
    emergency_missed = float(metrics.get("emergency_missed", 0.0))
    
    # Normalize components
    wait_score = _normalize_wait_time(avg_wait, max_acceptable=20.0)  # Standard threshold
    solar_score = _normalize_solar_utilization(solar_pct)
    completion_score = _normalize_completion_rate(vehicles_seen, vehicles_completed)
    emergency_score = _normalize_emergency_response(emergency_served, emergency_missed, vehicles_seen)
    
    # Weighted average for medium task
    grade = (
        0.35 * completion_score +
        0.25 * solar_score +
        0.20 * wait_score +
        0.20 * emergency_score
    )
    
    return min(1.0, max(0.0, grade))


def grade_hard_task(metrics: dict[str, Any], episode_steps: int = 300) -> float:
    """Grade hard task: Maximize solar + emergency response + grid stability.
    
    Focuses on:
    - Vehicle completion rate (25%)
    - Solar utilization (25%)
    - Service quality / waiting time (20%)
    - Emergency response (15%)
    - Grid stability (15%)
    
    Args:
        metrics: Dictionary with keys from compute_episode_summary_metrics()
                 and episode_stats: average_wait_time, solar_utilization_pct,
                 vehicles_seen, emergency_served, emergency_missed,
                 total_reward, grid_overload_events
        episode_steps: Total timesteps in episode
    
    Returns:
        Grade in [0.0, 1.0] where 1.0 is perfect performance
    """
    # Default values if metrics missing
    avg_wait = float(metrics.get("average_wait_time", 15.0))
    solar_pct = float(metrics.get("solar_utilization_pct", 40.0))
    vehicles_seen = float(metrics.get("vehicles_seen", 1.0))
    vehicles_completed = float(metrics.get("vehicles_completed", vehicles_seen * 0.90))
    emergency_served = float(metrics.get("emergency_served", 0.0))
    emergency_missed = float(metrics.get("emergency_missed", 0.0))
    grid_overload_events = float(metrics.get("grid_overload_events", 10.0))
    
    # Normalize components
    wait_score = _normalize_wait_time(avg_wait, max_acceptable=18.0)  # Stricter threshold
    solar_score = _normalize_solar_utilization(solar_pct)
    completion_score = _normalize_completion_rate(vehicles_seen, vehicles_completed)
    emergency_score = _normalize_emergency_response(emergency_served, emergency_missed, vehicles_seen)
    stability_score = _normalize_grid_stability(grid_overload_events, episode_steps)
    
    # Weighted average for hard task (emphasis on solar + stability + emergency)
    grade = (
        0.25 * completion_score +
        0.25 * solar_score +
        0.20 * wait_score +
        0.15 * emergency_score +
        0.15 * stability_score
    )
    
    return min(1.0, max(0.0, grade))
