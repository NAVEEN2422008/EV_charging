#!/usr/bin/env python3
"""Comprehensive OpenEnv compliance validation."""

from __future__ import annotations

import sys
import numpy as np

try:
    from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
    from ev_charging_grid_env.agents import HeuristicCoordinatorAgent, HeuristicStationAgent
    from ev_charging_grid_env.graders import grade_episode
    print("All imports successful")
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def test_env_reset_step() -> bool:
    """Test environment reset and step."""
    print("\nTEST: Environment reset/step")
    try:
        env = MultiAgentEVChargingGridEnv({"task_id": "medium"})
        obs, info = env.reset(seed=42)

        coord_agent = HeuristicCoordinatorAgent()
        station_agent = HeuristicStationAgent()

        coord_action = coord_agent.act(obs)
        station_actions = []
        for i in range(env.num_stations):
            action = station_agent.act(i, obs, coord_action)
            station_actions.append(action)

        action = {
            "coordinator_action": coord_action,
            "station_actions": station_actions
        }

        obs, reward, terminated, truncated, info = env.step(action)

        assert isinstance(reward, float), f"Reward must be float, got {type(reward)}"
        assert 0.0 <= reward <= 1.0, f"Reward must be in [0,1], got {reward}"

        print("  OK: Environment reset/step works correctly")
        print(f"     - Reward: {reward:.4f} (normalized)")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_reward_normalization() -> bool:
    """Test that reward is properly normalized to [0,1]."""
    print("\nTEST: Reward normalization")
    try:
        env = MultiAgentEVChargingGridEnv({"task_id": "hard"})
        obs, _ = env.reset(seed=42)

        rewards = []
        coord_agent = HeuristicCoordinatorAgent()
        station_agent = HeuristicStationAgent()

        for _ in range(30):
            coord_action = coord_agent.act(obs)
            station_actions = []
            for i in range(env.num_stations):
                action = station_agent.act(i, obs, coord_action)
                station_actions.append(action)

            action = {
                "coordinator_action": coord_action,
                "station_actions": station_actions
            }
            obs, reward, _, truncated, _ = env.step(action)
            rewards.append(reward)

            if truncated:
                break

        min_r = min(rewards)
        max_r = max(rewards)
        mean_r = np.mean(rewards)

        assert 0.0 <= min_r, f"Min reward {min_r} < 0"
        assert max_r <= 1.0, f"Max reward {max_r} > 1"

        print("  OK: All rewards are normalized to [0,1]")
        print(f"     - Min: {min_r:.4f}, Max: {max_r:.4f}, Mean: {mean_r:.4f}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_grader_normalization() -> bool:
    """Test that graders return normalized scores."""
    print("\nTEST: Grader normalization [0,1]")
    try:
        env = MultiAgentEVChargingGridEnv({"task_id": "medium"})
        obs, _ = env.reset(seed=42)

        coord_agent = HeuristicCoordinatorAgent()
        station_agent = HeuristicStationAgent()

        for _ in range(min(50, env.task.episode_length)):
            coord_action = coord_agent.act(obs)
            station_actions = []
            for i in range(env.num_stations):
                action = station_agent.act(i, obs, coord_action)
                station_actions.append(action)

            action = {
                "coordinator_action": coord_action,
                "station_actions": station_actions
            }
            obs, _, _, truncated, info = env.step(action)

            if truncated:
                break

        metrics = env._metrics_snapshot()
        score_episode = grade_episode(metrics)

        assert 0.0 <= score_episode <= 1.0, f"Episode score {score_episode} not in [0,1]"

        print("  OK: Grader returns normalized score [0,1]")
        print(f"     - Episode score: {score_episode:.4f}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def test_task_definitions() -> bool:
    """Test all task definitions."""
    print("\nTEST: Task definitions (easy, medium, hard)")
    try:
        for task_id in ["easy", "medium", "hard"]:
            env = MultiAgentEVChargingGridEnv({"task_id": task_id})
            obs, info = env.reset(seed=42)

            assert env.task_id == task_id
            assert env.task.episode_length > 0

            print(f"  OK: Task '{task_id}' valid")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main() -> int:
    """Run all validations."""
    print("\n" + "=" * 60)
    print("OpenEnv Compliance Validation")
    print("=" * 60)

    tests = [
        ("Environment Reset/Step", test_env_reset_step),
        ("Reward Normalization", test_reward_normalization),
        ("Grader Normalization", test_grader_normalization),
        ("Task Definitions", test_task_definitions),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            results.append((name, False))

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {name}")

    readiness_score = (passed_count / total_count) * 100
    print(f"\nReadiness Score: {readiness_score:.1f}% ({passed_count}/{total_count})")

    if readiness_score == 100:
        print("\nOPENENV-COMPLIANT AND READY FOR SUBMISSION!")
    else:
        print("\nPlease address failing tests.")

    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
