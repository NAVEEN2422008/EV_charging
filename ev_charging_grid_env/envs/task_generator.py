"""Task and scenario generation for EV charging episodes."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(slots=True)
class StationConfig:
    """Static station configuration for an episode."""

    station_id: int
    max_slots: int
    has_solar: bool
    grid_capacity_kw: float
    base_solar_capacity_kw: float
    base_price_per_kwh: float
    location_xy: tuple[float, float]
    charger_type: str
    outage_probability: float


@dataclass(slots=True)
class ArrivalProcessConfig:
    """Stochastic vehicle arrival process settings."""

    base_arrival_rate: float
    rush_hour_multiplier: float
    emergency_arrival_prob: float
    required_kwh_min: float
    required_kwh_max: float
    max_wait_timesteps: int


@dataclass(slots=True)
class TaskConfig:
    """Generated episode task definition."""

    station_configs: list[StationConfig]
    arrival_process: ArrivalProcessConfig
    episode_length: int
    grid_limit_kw: float
    weather_probs: dict[str, float]
    scenario_name: str
    station_distance_km: list[list[float]]


def _compute_distance_matrix(stations: list[StationConfig]) -> list[list[float]]:
    matrix: list[list[float]] = []
    for src in stations:
        row: list[float] = []
        for dst in stations:
            dx = src.location_xy[0] - dst.location_xy[0]
            dy = src.location_xy[1] - dst.location_xy[1]
            row.append(float((dx * dx + dy * dy) ** 0.5))
        matrix.append(row)
    return matrix


def _validate_weather_probs(raw: dict[str, Any]) -> dict[str, float]:
    allowed = {"sunny", "cloudy", "rainy"}
    if not raw:
        raise ValueError("weather_probs must be a non-empty mapping")
    probs: dict[str, float] = {}
    for key, value in raw.items():
        if key not in allowed:
            raise ValueError(f"Unsupported weather key: {key}")
        prob = float(value)
        if prob < 0.0:
            raise ValueError("weather probabilities must be non-negative")
        probs[key] = prob
    total = sum(probs.values())
    if total <= 0.0:
        raise ValueError("weather probabilities must sum to > 0")
    return {k: v / total for k, v in probs.items()}


def generate_task(config: dict[str, Any]) -> TaskConfig:
    """Generate a scenario task object from configuration."""
    num_stations = int(config.get("num_stations", 10))
    if num_stations <= 0:
        raise ValueError(f"num_stations must be > 0, got {num_stations}")
    
    max_slots = int(config.get("max_slots_per_station", 4))
    if max_slots <= 0:
        raise ValueError(f"max_slots_per_station must be > 0, got {max_slots}")
    
    solar_station_ratio = float(config.get("solar_station_ratio", 0.5))
    if not (0.0 <= solar_station_ratio <= 1.0):
        raise ValueError(f"solar_station_ratio must be in [0.0, 1.0], got {solar_station_ratio}")
    
    solar_count = max(1, min(num_stations, round(num_stations * solar_station_ratio)))

    scenario = str(config.get("traffic_pattern", config.get("task_id", "mixed")))
    rush_multiplier = 2.0 if scenario == "rush_hour" or scenario == "hard" else 1.0
    if scenario == "off_peak":
        rush_multiplier = 0.7

    station_configs: list[StationConfig] = []
    city_radius_km = float(config.get("city_radius_km", 12.0))
    for station_id in range(num_stations):
        has_solar = station_id < solar_count
        angle = (2.0 * 3.141592653589793 * station_id) / max(1, num_stations)
        radius = city_radius_km * (0.35 + 0.65 * ((station_id % 3) / 2.0))
        location_xy = (radius * float(math.cos(angle)), radius * float(math.sin(angle)))
        station_configs.append(
            StationConfig(
                station_id=station_id,
                max_slots=max_slots,
                has_solar=has_solar,
                grid_capacity_kw=float(config.get("grid_capacity_kw_per_station", 250.0)),
                base_solar_capacity_kw=float(config.get("base_solar_capacity_kw", 120.0)) if has_solar else 0.0,
                base_price_per_kwh=float(config.get("base_price_per_kwh", 0.35)),
                location_xy=location_xy,
                charger_type="fast" if station_id % 2 == 0 else "slow",
                outage_probability=float(config.get("station_outage_probability", 0.005)),
            )
        )

    arrival_process = ArrivalProcessConfig(
        base_arrival_rate=float(config.get("base_arrival_rate", 0.6)),
        rush_hour_multiplier=rush_multiplier,
        emergency_arrival_prob=float(config.get("emergency_arrival_prob", 0.04)),
        required_kwh_min=float(config.get("required_kwh_min", 8.0)),
        required_kwh_max=float(config.get("required_kwh_max", 65.0)),
        max_wait_timesteps=int(config.get("max_wait_timesteps", 45)),
    )

    return TaskConfig(
        station_configs=station_configs,
        arrival_process=arrival_process,
        episode_length=int(config.get("episode_length", 300)),
        grid_limit_kw=float(config.get("grid_limit_kw", 2400.0)),
        weather_probs=_validate_weather_probs(
            dict(config.get("weather_probs", {"sunny": 0.5, "cloudy": 0.3, "rainy": 0.2}))
        ),
        scenario_name=scenario,
        station_distance_km=_compute_distance_matrix(station_configs),
    )
