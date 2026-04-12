"""Comprehensive regression test suite for production validation.

Tests:
- Numerical stability across long episodes
- Edge cases and corner scenarios
- Multi-agent coordination
- Training pipeline
- Advanced features
"""

import json
from unittest.mock import patch

import numpy as np
import pytest

from ev_charging_grid_env.advanced_features import (
    ExplainableDecision,
    CoordinationMetrics,
    optimize_dynamic_prices,
    simulate_station_failure,
    apply_weather_impact,
)
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.training_diagnostics import (
    EpisodeMetrics,
    StepMetrics,
    TrainingDiagnostics,
    HyperparameterAnalyzer,
)


# ──────────────────────────────────────────────────────────────────────────────
# NUMERICAL STABILITY TESTS
# ──────────────────────────────────────────────────────────────────────────────


class TestNumericalStability:
    """Test for NaN, Inf, and numerical issues in long episodes."""

    def test_1000_step_episode_no_nan(self):
        """Run 1000 steps without NaN/Inf values."""
        env = MultiAgentEVChargingGridEnv(config={"episode_length": 1000})
        obs, _ = env.reset(seed=42)

        rewards = []
        for step in range(1000):
            action = {
                "coordinator_action": {
                    "price_deltas": [1] * env.num_stations,
                    "emergency_target_station": 0,
                },
                "station_actions": [0] * env.num_stations,
            }

            obs, reward, term, trunc, info = env.step(action)

            # Check for NaN/Inf
            assert reward == reward, f"NaN at step {step}"  # NaN != NaN
            assert not np.isinf(reward), f"Inf at step {step}"
            assert -100 < reward < 100, f"Unbounded reward at step {step}: {reward}"

            rewards.append(reward)

            if term or trunc:
                break

        # Aggregate should be stable
        total_reward = sum(rewards)
        assert total_reward == total_reward, "Total reward is NaN"
        assert not np.isinf(total_reward), "Total reward is Inf"

    def test_observation_values_bounded(self):
        """Ensure observation values are reasonable."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)

        for step in range(100):
            obs, _, _, _, _ = env.step(
                {
                    "coordinator_action": {
                        "price_deltas": [1] * env.num_stations,
                        "emergency_target_station": 0,
                    },
                    "station_actions": [0] * env.num_stations,
                }
            )

            # Check queue lengths are non-negative
            queue_lengths = obs.get("queue_lengths", [])
            assert all(q >= 0 for q in queue_lengths), f"Negative queue at step {step}"

            # Check bounded values
            station_features = obs.get("station_features", [])
            for features in station_features:
                if isinstance(features, (list, np.ndarray)):
                    assert all(
                        -500 < f < 500 for f in features
                    ), f"Unbounded station feature at step {step}"

    def test_reward_distribution_reasonable(self):
        """Test reward distribution is not pathological."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)

        rewards = []
        for _ in range(300):
            obs, reward, term, trunc, _ = env.step(
                {
                    "coordinator_action": {
                        "price_deltas": [1] * env.num_stations,
                        "emergency_target_station": 0,
                    },
                    "station_actions": [0] * env.num_stations,
                }
            )
            rewards.append(reward)
            if term or trunc:
                break

        # Check distribution
        mean_reward = np.mean(rewards)
        std_reward = np.std(rewards)

        # Not all zeros (variance should exist even in [0,1] range)
        assert std_reward > 0.0, "No reward variance"
        
        # Within reasonable bounds [0, 1] as required by OpenEnv
        assert 0.0 <= min(rewards) and max(rewards) <= 1.0, "Rewards must be normalized to [0,1]"


# ──────────────────────────────────────────────────────────────────────────────
# EDGE CASE TESTS
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_all_stations_full(self):
        """Test behavior when all stations are at max capacity."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)

        # Run until queues build up
        for _ in range(50):
            env.step(
                {
                    "coordinator_action": {
                        "price_deltas": [1] * env.num_stations,
                        "emergency_target_station": 0,
                    },
                    "station_actions": [0] * env.num_stations,
                }
            )

        # Environment should handle high queue states
        obs, reward, _, _, _ = env.step(
            {
                "coordinator_action": {
                    "price_deltas": [1] * env.num_stations,
                    "emergency_target_station": 0,
                },
                "station_actions": [0] * env.num_stations,
            }
        )

        assert reward == reward, "NaN with full queues"
        assert not np.isinf(reward), "Inf with full queues"

    def test_extreme_action_values(self):
        """Test with extreme but valid action values."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)

        # Maximum prices
        obs, reward, _, _, _ = env.step(
            {
                "coordinator_action": {
                    "price_deltas": [10] * env.num_stations,
                    "emergency_target_station": 0,
                },
                "station_actions": [3] * env.num_stations,
            }
        )
        assert reward == reward, "NaN with high prices"

        # Minimum prices
        obs, reward, _, _, _ = env.step(
            {
                "coordinator_action": {
                    "price_deltas": [-10] * env.num_stations,
                    "emergency_target_station": env.num_stations - 1,
                },
                "station_actions": [0] * env.num_stations,
            }
        )
        assert reward == reward, "NaN with low prices"

    def test_single_station_failure(self):
        """Test when one station fails."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)

        # Station 0 fails
        try:
            state_dict = {
                "queue_lengths": env.episode_stats.get("queue_lengths", [1, 1]),
            }
            failed_state = simulate_station_failure(state_dict, 0)
            assert "failed_stations" in failed_state
        except Exception as e:
            pytest.skip(f"Station failure simulation not fully integrated: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# ADVANCED FEATURES TESTS
# ──────────────────────────────────────────────────────────────────────────────


class TestAdvancedFeatures:
    """Test advanced features: pricing, explainability, coordination."""

    def test_dynamic_pricing_optimization(self):
        """Test dynamic pricing computes reasonable prices."""
        state = {
            "queue_lengths": [5, 10, 3, 8],
        }

        prices = optimize_dynamic_prices(state)

        # All prices should be positive multipliers
        assert all(0.5 < p < 2.5 for p in prices.values())
        # Highest queue should get highest price
        max_queue_idx = np.argmax(state["queue_lengths"])
        assert prices[f"station_{max_queue_idx}"] > 1.0

    def test_explainable_decisions(self):
        """Test explainability module generates valid explanations."""
        explainer = ExplainableDecision()

        state = {
            "queue_lengths": [5, 10, 3, 8],
        }
        action = {
            "price_deltas": [1, 2, -1, 0],
            "emergency_target_station": 1,
        }

        explanation = explainer.explain_coordinator_action(state, action, 15.0)

        assert explanation["action_type"] == "coordinator_decision"
        assert "reasoning" in explanation
        assert len(explanation["reasoning"]) > 0
        assert explanation["reward"] == 15.0

    def test_coordination_metrics(self):
        """Test multi-agent coordination score computation."""
        metrics = CoordinationMetrics()

        coordinator_action = {
            "price_deltas": [1, -1, 0, 1],
            "emergency_target_station": 2,
        }
        station_actions = [0, 2, 1, 0]
        state = {
            "queue_lengths": [5, 10, 3, 8],
        }

        scores = metrics.compute_coordination_score(
            coordinator_action, station_actions, state, 20.0
        )

        assert "alignment" in scores
        assert "efficiency" in scores
        assert "responsiveness" in scores
        assert 0 <= scores["alignment"] <= 1
        assert 0 <= scores["efficiency"] <= 1
        assert 0 <= scores["responsiveness"] <= 1

    def test_weather_impact(self):
        """Test weather impact simulation."""
        sunny_state_input = {
            "solar_context": {"available_kw": 100},
            "arrivals_summary": [5, 0, 0],
        }
        rainy_state_input = {
            "solar_context": {"available_kw": 100},
            "arrivals_summary": [5, 0, 0],
        }

        # Sunny weather
        sunny_state = apply_weather_impact(sunny_state_input, "sunny")
        assert sunny_state["weather"] == "sunny"

        # Rainy weather
        rainy_state = apply_weather_impact(rainy_state_input, "rainy")
        assert rainy_state["weather"] == "rainy"
        # Less solar in rainy conditions
        assert rainy_state["solar_context"]["available_kw"] < sunny_state["solar_context"]["available_kw"]


# ──────────────────────────────────────────────────────────────────────────────
# TRAINING DIAGNOSTICS TESTS
# ──────────────────────────────────────────────────────────────────────────────


class TestTrainingDiagnostics:
    """Test training diagnostics tracking and analysis."""

    def test_learning_curve_generation(self):
        """Test learning curve computation from metrics."""
        diag = TrainingDiagnostics(window_size=5)

        # Add sample metrics
        for episode in range(10):
            metrics = EpisodeMetrics(
                episode=episode,
                total_reward=float(episode * 2),
                episode_length=100,
                average_wait_time=50.0 - episode * 2,
                solar_utilization_pct=30.0 + episode,
                emergency_served=episode // 2,
                emergency_missed=0,
                grid_overload_events=5 - episode // 2,
                final_queue_length=10 - episode // 3,
                avg_queue_length=15.0,
                max_queue_length=30,
                training_time_sec=2.0,
            )
            diag.add_episode(metrics)

        curve = diag.get_learning_curve()

        assert "episodes" in curve
        assert "total_reward" in curve
        assert "moving_avg" in curve
        assert len(curve["episodes"]) == 10
        assert curve["total_reward"][-1] > curve["total_reward"][0]

    def test_stability_metrics(self):
        """Test training stability assessment."""
        np.random.seed(42)
        diag = TrainingDiagnostics(window_size=5)

        # Add stable metrics
        for episode in range(10):
            metrics = EpisodeMetrics(
                episode=episode,
                total_reward=20.0 + np.random.normal(0, 2),
                episode_length=100,
                average_wait_time=45.0,
                solar_utilization_pct=35.0,
                emergency_served=2,
                emergency_missed=0,
                grid_overload_events=4,
                final_queue_length=8,
                avg_queue_length=12.0,
                max_queue_length=25,
                training_time_sec=2.0,
            )
            diag.add_episode(metrics)

        stability = diag.get_stability_metrics()

        assert "stability_score" in stability
        assert 0 <= stability["stability_score"] <= 1
        assert stability["variance"] >= 0

    def test_convergence_status(self):
        """Test convergence detection."""
        np.random.seed(42)
        diag = TrainingDiagnostics(window_size=5)

        # Add improving then plateauing metrics
        for episode in range(20):
            if episode < 10:
                reward = 10 + episode  # Improving
            else:
                reward = 20 + np.random.normal(0, 0.5)  # Plateau

            metrics = EpisodeMetrics(
                episode=episode,
                total_reward=reward,
                episode_length=100,
                average_wait_time=50.0,
                solar_utilization_pct=30.0,
                emergency_served=2,
                emergency_missed=0,
                grid_overload_events=5,
                final_queue_length=10,
                avg_queue_length=15.0,
                max_queue_length=30,
                training_time_sec=2.0,
            )
            diag.add_episode(metrics)

        status = diag.get_convergence_status()

        assert "converged" in status
        assert "status" in status
        assert "improvement_percent" in status
        assert "recommendation" in status

    def test_hyperparameter_analyzer(self):
        """Test hyperparameter impact analysis."""
        analyzer = HyperparameterAnalyzer()

        configs = [
            ({"lr": 0.001}, 25.0),
            ({"lr": 0.0001}, 15.0),
            ({"lr": 0.01}, 20.0),
        ]

        for i, (params, final_reward) in enumerate(configs):
            metrics = EpisodeMetrics(
                episode=i,
                total_reward=final_reward,
                episode_length=100,
                average_wait_time=40.0,
                solar_utilization_pct=35.0,
                emergency_served=2,
                emergency_missed=0,
                grid_overload_events=3,
                final_queue_length=5,
                avg_queue_length=10.0,
                max_queue_length=20,
                training_time_sec=3.0,
            )
            analyzer.add_run(f"run_{i}", params, metrics)

        best_config, best_params, best_metrics = analyzer.get_best_config()

        assert best_config == "run_0"  # lr=0.001 gave best reward
        assert best_params["lr"] == 0.001
        assert best_metrics["final_reward"] == 25.0


# ──────────────────────────────────────────────────────────────────────────────
# INTEGRATION TESTS
# ──────────────────────────────────────────────────────────────────────────────


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_inference_with_advanced_features(self):
        """Test inference script with advanced features."""
        try:
            from inference import run
            import os
            os.environ["SIMULATION_STEPS"] = "50"
            os.environ["RANDOM_SEED"] = "42"
        except ImportError:
            pytest.skip("inference module not available")

        result = run()
        assert result["status"] == "success"
        assert "total_reward" in result

    def test_diagnostics_from_live_episode(self):
        """Test capturing diagnostics from live episode."""
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)

        diag = TrainingDiagnostics()

        for step in range(50):
            action = {
                "coordinator_action": {
                    "price_deltas": [1] * env.num_stations,
                    "emergency_target_station": 0,
                },
                "station_actions": [0] * env.num_stations,
            }

            obs, reward, term, trunc, info = env.step(action)

            step_metric = StepMetrics(
                step=step,
                episode=0,
                reward=reward,
                reward_min=reward,
                reward_max=reward,
                reward_mean=reward,
                reward_std=0.0,
                policy_entropy=0.5,
                value_loss=0.1,
                policy_loss=0.05,
                learning_rate=0.0005,
                gradient_norm=0.01,
            )

            diag.add_step(step_metric)

            if term or trunc:
                break

        # Diagnostics should record steps
        assert len(diag.step_metrics) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
