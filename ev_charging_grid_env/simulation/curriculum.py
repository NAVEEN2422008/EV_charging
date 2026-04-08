"""Curriculum schedule for progressively harder scenarios."""

from __future__ import annotations


def curriculum_stage_config(stage: int, base_config: dict) -> dict:
    """Return curriculum-adjusted config for a given stage."""
    updated = dict(base_config)
    if stage <= 0:
        updated["traffic_pattern"] = "off_peak"
        updated["station_outage_probability"] = 0.0
    elif stage == 1:
        updated["traffic_pattern"] = "mixed"
        updated["station_outage_probability"] = 0.002
    else:
        updated["traffic_pattern"] = "rush_hour"
        updated["station_outage_probability"] = 0.01
        updated["emergency_arrival_prob"] = float(base_config.get("emergency_arrival_prob", 0.04)) * 1.5
    return updated
