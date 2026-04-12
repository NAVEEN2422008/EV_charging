"""Dashboard smoke tests."""

from __future__ import annotations

from ui.dashboard import build_env_config


def test_build_env_config_maps_controls() -> None:
    config = build_env_config("medium", 1.3, 1.5, 0.8, "sunny")
    assert config["task_id"] == "medium"
    assert config["arrival_lambda"] > 0
    assert config["emergency_probability"] > 0
    assert config["solar_multiplier"] > 0
    assert config["weather_mode"] == "sunny"
