"""Task graders for OpenEnv evaluation."""

from ev_charging_grid_env.graders.task_graders import (
    grade_easy_task,
    grade_medium_task,
    grade_hard_task,
)


def grade_episode(metrics: dict) -> float:
    """Unified grading entry point."""
    task_id = metrics.get("task_id", "medium")
    if task_id == "easy":
        return grade_easy_task(metrics)
    if task_id == "hard":
        return grade_hard_task(metrics)
    return grade_medium_task(metrics)


__all__ = [
    "grade_easy_task",
    "grade_medium_task",
    "grade_hard_task",
    "grade_episode",
]
