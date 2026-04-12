"""Grader tests."""

from __future__ import annotations

from ev_charging_grid_env.graders import grade_easy_task, grade_hard_task, grade_medium_task


def test_grader_range_and_formula_direction() -> None:
    weak = {
        "served_ratio": 0.2,
        "solar_usage_ratio": 0.1,
        "normalized_wait_time": 0.9,
    }
    strong = {
        "served_ratio": 0.9,
        "solar_usage_ratio": 0.8,
        "normalized_wait_time": 0.1,
    }
    easy_weak = grade_easy_task(weak)
    easy_strong = grade_easy_task(strong)
    medium_strong = grade_medium_task(strong)
    hard_strong = grade_hard_task(strong)
    assert 0.0 <= easy_weak <= 1.0
    assert 0.0 <= easy_strong <= 1.0
    assert easy_strong > easy_weak
    assert medium_strong == easy_strong
    assert hard_strong == easy_strong

