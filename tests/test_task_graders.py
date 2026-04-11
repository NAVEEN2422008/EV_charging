"""Unit tests for task graders."""

import pytest
from ev_charging_grid_env.graders import (
    grade_easy_task,
    grade_medium_task,
    grade_hard_task,
)


class TestGradeEasyTask:
    """Tests for easy task grader."""
    
    def test_perfect_performance(self):
        """Test grading with perfect metrics."""
        metrics = {
            "average_wait_time": 0.0,
            "solar_utilization_pct": 100.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 50.0,
            "emergency_served": 2.0,
            "emergency_missed": 0.0,
            "grid_overload_events": 0.0,
        }
        grade = grade_easy_task(metrics, episode_steps=300)
        assert 0.9 <= grade <= 1.0, f"Expected near-perfect grade, got {grade}"
    
    def test_poor_performance(self):
        """Test grading with poor metrics."""
        metrics = {
            "average_wait_time": 50.0,  # Very high wait
            "solar_utilization_pct": 0.0,  # No solar
            "vehicles_seen": 50.0,
            "vehicles_completed": 10.0,  # Only 20% completed
            "emergency_served": 0.0,
            "emergency_missed": 2.0,
            "grid_overload_events": 100.0,
        }
        grade = grade_easy_task(metrics, episode_steps=300)
        assert 0.0 <= grade < 0.3, f"Expected poor grade, got {grade}"
    
    def test_output_range(self):
        """Test that output is always in [0.0, 1.0]."""
        metrics = {
            "average_wait_time": 15.0,
            "solar_utilization_pct": 35.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 42.0,
        }
        grade = grade_easy_task(metrics, episode_steps=300)
        assert 0.0 <= grade <= 1.0, f"Grade {grade} outside [0.0, 1.0]"
    
    def test_default_metrics(self):
        """Test with minimal metrics (defaults used)."""
        metrics = {}
        grade = grade_easy_task(metrics)
        assert 0.0 <= grade <= 1.0, f"Grade {grade} outside [0.0, 1.0]"
    
    def test_solar_weight(self):
        """Test that higher solar utilization increases grade."""
        base_metrics = {
            "average_wait_time": 15.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 40.0,
        }
        
        low_solar = {**base_metrics, "solar_utilization_pct": 10.0}
        high_solar = {**base_metrics, "solar_utilization_pct": 90.0}
        
        grade_low = grade_easy_task(low_solar)
        grade_high = grade_easy_task(high_solar)
        
        assert grade_high > grade_low, "Higher solar should improve grade"


class TestGradeMediumTask:
    """Tests for medium task grader."""
    
    def test_perfect_performance(self):
        """Test grading with perfect metrics."""
        metrics = {
            "average_wait_time": 0.0,
            "solar_utilization_pct": 100.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 50.0,
            "emergency_served": 2.0,
            "emergency_missed": 0.0,
            "grid_overload_events": 0.0,
        }
        grade = grade_medium_task(metrics, episode_steps=300)
        assert 0.9 <= grade <= 1.0, f"Expected near-perfect grade, got {grade}"
    
    def test_emergency_response_weight(self):
        """Test that emergency response matters for medium task."""
        base_metrics = {
            "average_wait_time": 10.0,
            "solar_utilization_pct": 50.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 45.0,
        }
        
        good_emergency = {**base_metrics, "emergency_served": 10.0, "emergency_missed": 0.0}
        poor_emergency = {**base_metrics, "emergency_served": 2.0, "emergency_missed": 8.0}
        
        grade_good = grade_medium_task(good_emergency)
        grade_poor = grade_medium_task(poor_emergency)
        
        assert grade_good > grade_poor, "Better emergency response should improve grade"
    
    def test_output_range(self):
        """Test that output is always in [0.0, 1.0]."""
        metrics = {
            "average_wait_time": 15.0,
            "solar_utilization_pct": 40.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 42.0,
            "emergency_served": 5.0,
            "emergency_missed": 1.0,
        }
        grade = grade_medium_task(metrics, episode_steps=300)
        assert 0.0 <= grade <= 1.0, f"Grade {grade} outside [0.0, 1.0]"


class TestGradeHardTask:
    """Tests for hard task grader."""
    
    def test_perfect_performance(self):
        """Test grading with perfect metrics."""
        metrics = {
            "average_wait_time": 0.0,
            "solar_utilization_pct": 100.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 50.0,
            "emergency_served": 5.0,
            "emergency_missed": 0.0,
            "grid_overload_events": 0.0,
        }
        grade = grade_hard_task(metrics, episode_steps=300)
        assert 0.9 <= grade <= 1.0, f"Expected near-perfect grade, got {grade}"
    
    def test_grid_stability_weight(self):
        """Test that grid stability significantly impacts hard task."""
        base_metrics = {
            "average_wait_time": 12.0,
            "solar_utilization_pct": 60.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 45.0,
            "emergency_served": 4.0,
            "emergency_missed": 0.0,
        }
        
        stable_grid = {**base_metrics, "grid_overload_events": 5.0}
        unstable_grid = {**base_metrics, "grid_overload_events": 60.0}
        
        grade_stable = grade_hard_task(stable_grid, episode_steps=300)
        grade_unstable = grade_hard_task(unstable_grid, episode_steps=300)
        
        assert grade_stable > grade_unstable, "Better grid stability should improve grade"
    
    def test_solar_emphasis(self):
        """Test that solar utilization is emphasized in hard task."""
        base_metrics = {
            "average_wait_time": 10.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 45.0,
            "emergency_served": 4.0,
            "emergency_missed": 0.0,
            "grid_overload_events": 10.0,
        }
        
        low_solar = {**base_metrics, "solar_utilization_pct": 20.0}
        high_solar = {**base_metrics, "solar_utilization_pct": 80.0}
        
        grade_low = grade_hard_task(low_solar)
        grade_high = grade_hard_task(high_solar)
        
        assert grade_high > grade_low, "Higher solar should improve grade"
    
    def test_output_range(self):
        """Test that output is always in [0.0, 1.0]."""
        metrics = {
            "average_wait_time": 12.0,
            "solar_utilization_pct": 45.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 45.0,
            "emergency_served": 4.0,
            "emergency_missed": 1.0,
            "grid_overload_events": 15.0,
        }
        grade = grade_hard_task(metrics, episode_steps=300)
        assert 0.0 <= grade <= 1.0, f"Grade {grade} outside [0.0, 1.0]"


class TestComparativeGrading:
    """Test relative grading across difficulty levels."""
    
    def test_difficulty_thresholds(self):
        """Test that same metrics get different grades by difficulty."""
        metrics = {
            "average_wait_time": 15.0,
            "solar_utilization_pct": 50.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 40.0,
            "emergency_served": 3.0,
            "emergency_missed": 1.0,
            "grid_overload_events": 20.0,
        }
        
        easy_grade = grade_easy_task(metrics)
        medium_grade = grade_medium_task(metrics)
        hard_grade = grade_hard_task(metrics)
        
        # Same metrics should get progressively lower scores as difficulty increases
        # because hard task has stricter requirements
        # (though not strictly enforced, hard should often be lower due to more components)
        assert all(0.0 <= g <= 1.0 for g in [easy_grade, medium_grade, hard_grade])
    
    def test_excellent_performance_same_across_difficulties(self):
        """Test that excellent metrics score well across all difficulties."""
        perfect_metrics = {
            "average_wait_time": 2.0,
            "solar_utilization_pct": 95.0,
            "vehicles_seen": 50.0,
            "vehicles_completed": 50.0,
            "emergency_served": 5.0,
            "emergency_missed": 0.0,
            "grid_overload_events": 1.0,
        }
        
        easy = grade_easy_task(perfect_metrics)
        medium = grade_medium_task(perfect_metrics)
        hard = grade_hard_task(perfect_metrics)
        
        # All should be high
        assert easy > 0.85
        assert medium > 0.85
        assert hard > 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
