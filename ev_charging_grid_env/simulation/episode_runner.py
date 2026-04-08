"""Episode rollout helper utilities."""

from __future__ import annotations

from typing import Any

from ev_charging_grid_env.envs.reward_functions import compute_episode_summary_metrics
from ev_charging_grid_env.simulation.dataset_logger import DatasetLogger


def run_episode(
    env: Any,
    coordinator: Any,
    stations: list[Any],
    render: bool = False,
    logger: DatasetLogger | None = None,
) -> dict[str, float]:
    """Run one episode with provided coordinator and station policies."""
    observation, _ = env.reset()
    total_reward = 0.0
    done = False
    step_count = 0

    while not done:
        coordinator_action = coordinator.act(observation)
        station_actions = [agent.act(i, observation, coordinator_action) for i, agent in enumerate(stations)]
        joint_action = {
            "coordinator_action": coordinator_action,
            "station_actions": station_actions,
        }
        previous_obs = observation
        observation, reward, terminated, truncated, _ = env.step(joint_action)
        if logger is not None:
            logger.log_transition(previous_obs, joint_action, float(reward), observation, bool(terminated or truncated))
        if render:
            env.render()
        total_reward += float(reward)
        step_count += 1
        done = bool(terminated or truncated)

    env.episode_stats["total_reward"] = total_reward
    metrics = compute_episode_summary_metrics(env.episode_stats, step_count)
    metrics["total_reward"] = total_reward
    metrics["steps"] = float(step_count)
    return metrics


def run_pettingzoo_episode(env: Any, policy_map: dict[str, Any]) -> dict[str, float]:
    """Run one episode for AEC environment."""
    env.reset(seed=42)
    total_reward = 0.0
    steps = 0
    cycle_terminal_agent = env.possible_agents[-1]
    for agent in env.agent_iter(max_iter=100000):
        obs = env.observe(agent)
        if env.terminations.get(agent, False) or env.truncations.get(agent, False):
            action = None
        else:
            action = policy_map[agent].act(obs) if hasattr(policy_map[agent], "act") else env.action_space(agent).sample()
        env.step(action)
        if agent == cycle_terminal_agent:
            total_reward += float(env.rewards.get(agent, 0.0)) * float(len(env.possible_agents))
            steps += 1
        if all(env.terminations.values()) or all(env.truncations.values()):
            break
    return {"total_reward": total_reward, "steps": float(steps)}
