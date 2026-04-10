"""RL training diagnostics and visualization support.

Provides:
- Learning curve tracking
- Reward component analysis
- Policy performance metrics
- Training stability diagnostics
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
# TRAINING METRICS
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class StepMetrics:
    """Single step metrics during training."""

    step: int
    episode: int
    reward: float
    reward_min: float
    reward_max: float
    reward_mean: float
    reward_std: float
    policy_entropy: float  # Action distribution entropy (exploration)
    value_loss: float
    policy_loss: float
    learning_rate: float
    gradient_norm: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class EpisodeMetrics:
    """Episode-level aggregated metrics."""

    episode: int
    total_reward: float
    episode_length: int
    average_wait_time: float
    solar_utilization_pct: float
    emergency_served: int
    emergency_missed: int
    grid_overload_events: int
    final_queue_length: int
    avg_queue_length: float
    max_queue_length: int
    training_time_sec: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────────────
# TRAINING DIAGNOSTICS
# ──────────────────────────────────────────────────────────────────────────────


class TrainingDiagnostics:
    """Track and diagnose training progress."""

    def __init__(self, window_size: int = 20):
        """Initialize diagnostics with rolling window for stability analysis.
        
        Args:
            window_size: Number of episodes for rolling average
        """
        self.window_size = window_size
        self.step_metrics: list[StepMetrics] = []
        self.episode_metrics: list[EpisodeMetrics] = []

    def add_step(self, metrics: StepMetrics) -> None:
        """Record step-level metrics."""
        self.step_metrics.append(metrics)

    def add_episode(self, metrics: EpisodeMetrics) -> None:
        """Record episode-level metrics."""
        self.episode_metrics.append(metrics)

    def get_learning_curve(self) -> dict[str, list[float]]:
        """Get learning curve data for plotting.
        
        Returns:
            Dict with episodes, rewards, moving_avg
        """
        if not self.episode_metrics:
            return {"episodes": [], "total_reward": [], "moving_avg": []}

        episodes = [m.episode for m in self.episode_metrics]
        rewards = [m.total_reward for m in self.episode_metrics]

        # Compute moving average
        moving_avg = []
        for i in range(len(rewards)):
            start = max(0, i - self.window_size)
            avg = float(np.mean(rewards[start : i + 1]))
            moving_avg.append(avg)

        return {
            "episodes": episodes,
            "total_reward": rewards,
            "moving_avg": moving_avg,
        }

    def get_stability_metrics(self) -> dict[str, float]:
        """Compute training stability indicators.
        
        Returns:
            Dict with stability_score, variance, divergence_risk
        """
        if len(self.episode_metrics) < self.window_size:
            return {
                "stability_score": 0.5,
                "variance": 0.0,
                "divergence_risk": 0.0,
            }

        recent = self.episode_metrics[-self.window_size :]
        rewards = [m.total_reward for m in recent]

        # Stability = inverse of coefficient of variation
        mean_reward = float(np.mean(rewards))
        std_reward = float(np.std(rewards))
        if mean_reward > 0:
            cv = std_reward / abs(mean_reward)
            stability_score = 1.0 / (1.0 + cv)  # [0, 1], higher is better
        else:
            stability_score = 0.5

        # Divergence risk: are rewards getting worse?
        if len(self.episode_metrics) > self.window_size:
            prev_mean = np.mean([m.total_reward for m in self.episode_metrics[-2*self.window_size:-self.window_size]])
            divergence_risk = max(0.0, (prev_mean - mean_reward) / abs(prev_mean + 1e-6))
        else:
            divergence_risk = 0.0

        return {
            "stability_score": float(stability_score),
            "variance": float(std_reward),
            "divergence_risk": float(divergence_risk),
        }

    def get_reward_breakdown(self) -> dict[str, float]:
        """Analyze components contributing to reward.
        
        Returns:
            Dict with average contributions from each component
        """
        if not self.episode_metrics:
            return {}

        recent = self.episode_metrics[-self.window_size :]

        return {
            "avg_total_reward": float(np.mean([m.total_reward for m in recent])),
            "avg_wait_time_penalty": float(
                np.mean([m.average_wait_time for m in recent])
            ),
            "avg_solar_utilization": float(
                np.mean([m.solar_utilization_pct for m in recent])
            ),
            "avg_emergency_served": float(np.mean([m.emergency_served for m in recent])),
            "avg_grid_overloads": float(
                np.mean([m.grid_overload_events for m in recent])
            ),
        }

    def get_convergence_status(self) -> dict[str, Any]:
        """Assess whether training has converged.
        
        Returns:
            Dict with convergence status and recommendations
        """
        if len(self.episode_metrics) < 2 * self.window_size:
            return {
                "converged": False,
                "status": "INSUFFICIENT_DATA",
                "recommendation": "Continue training, need more episodes",
            }

        recent_mean = np.mean(
            [m.total_reward for m in self.episode_metrics[-self.window_size :]]
        )
        old_mean = np.mean(
            [
                m.total_reward
                for m in self.episode_metrics[
                    -(2 * self.window_size) : -self.window_size
                ]
            ]
        )
        improvement = (recent_mean - old_mean) / (abs(old_mean) + 1e-6)

        if abs(improvement) < 0.02:  # Less than 2% improvement
            converged = True
            status = "CONVERGED"
            recommendation = "Training has plateaued, consider hyperparameter tuning or policy reset"
        elif improvement > 0.1:
            converged = False
            status = "IMPROVING"
            recommendation = "Training is progressing well, continue"
        else:
            converged = False
            status = "SLOW_IMPROVEMENT"
            recommendation = "Consider increasing learning rate or batch size"

        return {
            "converged": converged,
            "status": status,
            "improvement_percent": float(improvement * 100),
            "recommendation": recommendation,
        }

    def get_policy_analysis(self) -> dict[str, Any]:
        """Analyze policy exploration vs exploitation.
        
        Returns:
            Dict with policy behavior metrics
        """
        if not self.step_metrics:
            return {}

        recent_steps = self.step_metrics[-1000:]  # Last 1000 steps
        entropies = [s.policy_entropy for s in recent_steps]
        gradient_norms = [s.gradient_norm for s in recent_steps]

        return {
            "mean_entropy": float(np.mean(entropies)),
            "entropy_std": float(np.std(entropies)),
            "mean_gradient_norm": float(np.mean(gradient_norms)),
            "gradient_norm_std": float(np.std(gradient_norms)),
            "policy_stability": float(
                1.0 / (1.0 + np.std(gradient_norms))
            ) if gradient_norms else 0.5,
        }


# ──────────────────────────────────────────────────────────────────────────────
# HYPERPARAMETER IMPACT ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────


class HyperparameterAnalyzer:
    """Analyze impact of hyperparameters on training."""

    def __init__(self):
        """Initialize analyzer."""
        self.configs: dict[str, dict[str, Any]] = {}
        self.results: dict[str, dict[str, Any]] = {}

    def add_run(
        self,
        config_name: str,
        hyperparams: dict[str, Any],
        final_metrics: EpisodeMetrics,
    ) -> None:
        """Record a training run with specific hyperparameters.
        
        Args:
            config_name: Unique identifier for this configuration
            hyperparams: Dictionary of hyperparameters used
            final_metrics: Final episode metrics
        """
        self.configs[config_name] = hyperparams
        self.results[config_name] = {
            "final_reward": final_metrics.total_reward,
            "avg_wait_time": final_metrics.average_wait_time,
            "solar_util": final_metrics.solar_utilization_pct,
            "emergency_success_rate": (
                final_metrics.emergency_served
                / (final_metrics.emergency_served + final_metrics.emergency_missed + 1)
            ),
        }

    def get_best_config(self) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """Find hyperparameter configuration with best performance.
        
        Returns:
            Tuple of (config_name, hyperparams, metrics)
        """
        if not self.results:
            return "", {}, {}

        best_config = max(
            self.results.keys(), key=lambda k: self.results[k]["final_reward"]
        )

        return (best_config, self.configs[best_config], self.results[best_config])

    def get_sensitivity_analysis(
        self, param_name: str
    ) -> dict[str, list[tuple[Any, float]]]:
        """Analyze sensitivity of performance to one hyperparameter.
        
        Args:
            param_name: Name of hyperparameter to analyze
            
        Returns:
            Dict with parameter values and resulting rewards
        """
        param_values = []
        rewards = []

        for config_name, hyperparams in self.configs.items():
            if param_name in hyperparams:
                param_value = hyperparams[param_name]
                reward = self.results[config_name]["final_reward"]
                param_values.append(param_value)
                rewards.append(reward)

        if not param_values:
            return {}

        # Sort by parameter value
        sorted_pairs = sorted(zip(param_values, rewards), key=lambda x: x[0])

        return {param_name: sorted_pairs}


# ──────────────────────────────────────────────────────────────────────────────
# EXPORT FOR INTEGRATION
# ──────────────────────────────────────────────────────────────────────────────


__all__ = [
    "StepMetrics",
    "EpisodeMetrics",
    "TrainingDiagnostics",
    "HyperparameterAnalyzer",
]
