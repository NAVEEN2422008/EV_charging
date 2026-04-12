"""Unit tests for reward shaping behavior."""

from __future__ import annotations

from ev_charging_grid_env.envs.reward_functions import compute_step_reward


def _base_config() -> dict[str, float]:
    return {
        "queue_penalty_weight": 0.2,
        "timeout_penalty_weight": 3.0,
        "grid_overload_penalty_weight": 0.05,
        "solar_priority_weight": 0.4,
        "emergency_priority_bonus": 5.0,
        "completion_reward_weight": 2.0,
        "fast_service_weight": 0.1,
        "reward_clip": 50.0,
    }


def test_emergency_served_quickly_is_high_reward() -> None:
    reward = compute_step_reward(
        state={"mean_wait_time": 1.0, "total_grid_kw_used": 200.0, "grid_limit_kw": 1000.0},
        events={"emergency_served": 1.0, "vehicles_completed": 2.0, "quick_service_score": 30.0, "solar_kwh_used": 10.0},
        config=_base_config(),
    )
    # Reward is normalized to [0,1], so 0.6+ is high
    assert reward > 0.5, f"Expected high normalized reward, got {reward}"


def test_emergency_missed_is_strong_negative() -> None:
    reward = compute_step_reward(
        state={"mean_wait_time": 5.0, "total_grid_kw_used": 500.0, "grid_limit_kw": 1000.0},
        events={"emergency_missed": 1.0, "timed_out_count": 1.0, "vehicles_completed": 0.0, "solar_kwh_used": 0.0},
        config=_base_config(),
    )
    # Normalized reward, so <0.5 is low/negative
    assert reward < 0.5, f"Expected low normalized reward for missed emergency, got {reward}"


def test_grid_overload_penalty() -> None:
    reward = compute_step_reward(
        state={"mean_wait_time": 0.0, "total_grid_kw_used": 1300.0, "grid_limit_kw": 1000.0},
        events={"vehicles_completed": 0.0, "solar_kwh_used": 0.0},
        config=_base_config(),
    )
    # Overload constraint violation should yield low reward
    assert reward < 0.5, f"Expected low normalized reward for severe overload, got {reward}"


def test_solar_heavy_better_than_grid_only() -> None:
    state = {"mean_wait_time": 1.0, "total_grid_kw_used": 700.0, "grid_limit_kw": 1000.0}
    grid_events = {"vehicles_completed": 2.0, "solar_kwh_used": 0.0}
    solar_events = {"vehicles_completed": 2.0, "solar_kwh_used": 30.0}
    r_grid = compute_step_reward(state=state, events=grid_events, config=_base_config())
    r_solar = compute_step_reward(state=state, events=solar_events, config=_base_config())
    assert r_solar > r_grid
