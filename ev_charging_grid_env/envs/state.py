"""Shared typed state used by both Gym and PettingZoo wrappers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class VehicleState:
    id: int
    required_kwh: float
    remaining_kwh: float
    battery_level: float
    is_emergency: bool
    urgency: int
    max_wait_timesteps: int
    green_preference: float
    price_sensitivity: float
    location_xy: tuple[float, float]
    preferred_station: int
    assigned_station: int
    wait_time: int = 0
    travel_time_left: int = 0
    travel_distance_km: float = 0.0
    charging: bool = False


@dataclass(slots=True)
class StationState:
    station_id: int
    max_slots: int
    has_solar: bool
    base_solar_capacity_kw: float
    solar_forecast_kw: float
    solar_actual_kw: float
    grid_capacity_kw: float
    dynamic_price: float
    location_xy: tuple[float, float]
    charger_type: str
    outage_probability: float
    outage_time_left: int = 0
    queue: deque[VehicleState] = field(default_factory=deque)
    charging_vehicles: list[VehicleState] = field(default_factory=list)
    grid_kw_used: float = 0.0
    solar_kw_used: float = 0.0


@dataclass(slots=True)
class GridState:
    global_limit_kw: float
    total_grid_kw_used: float = 0.0
    overload_events: int = 0


@dataclass(slots=True)
class EpisodeState:
    time_step: int
    weather: str
    stations: list[StationState]
    grid: GridState
    next_vehicle_id: int
    episode_length: int
