"""Simulation data models and OpenEnv-compliant type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from pydantic import BaseModel, Field, field_validator


@dataclass
class Vehicle:
    """Vehicle waiting for or receiving charge."""

    vehicle_id: str
    arrival_step: int
    required_kwh: float
    remaining_kwh: float
    battery_level: float
    max_wait_steps: int
    green_preference: float
    emergency: bool
    assigned_station: int
    wait_steps: int = 0


@dataclass
class Station:
    """Station state for a single simulation step."""

    station_id: int
    charger_count: int
    queue: list[Vehicle] = field(default_factory=list)
    charging: list[Vehicle] = field(default_factory=list)
    solar_kw: float = 0.0
    grid_kw: float = 0.0
    price_multiplier: float = 1.0
    served_this_step: int = 0
    emergency_served_this_step: int = 0
    redirected_this_step: int = 0


# OpenEnv Action Model
class CoordinatorActionModel(BaseModel):
    """Coordinator-level action for price and emergency routing."""

    price_deltas: list[int] = Field(
        ...,
        description="Price adjustment for each station [-3, 3]",
    )
    emergency_target_station: int = Field(
        ...,
        ge=0,
        description="Station index to route emergency vehicles",
    )

    @field_validator("price_deltas")
    @classmethod
    def validate_price_deltas(cls, v: list[int]) -> list[int]:
        if not isinstance(v, list):
            raise ValueError("price_deltas must be a list")
        for val in v:
            if not isinstance(val, int) or val < -3 or val > 3:
                raise ValueError("Each price_delta must be int in [-3, 3]")
        return v


class StationActionsModel(BaseModel):
    """Station-level actions as array of action codes."""

    actions: list[int] = Field(
        ...,
        description="Station actions: 0=hold, 1=charge(wait), 2=charge(emergency), 3=redirect",
    )

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, v: list[int]) -> list[int]:
        for action in v:
            if not isinstance(action, int) or action < 0 or action > 3:
                raise ValueError("Each action must be int in [0, 3]")
        return v


class ActionModel(BaseModel):
    """Full joint action combining coordinator and station actions."""

    coordinator_action: CoordinatorActionModel
    station_actions: list[int] = Field(
        ...,
        description="Station action codes [0, 1, 2, 3]",
    )

    @field_validator("station_actions")
    @classmethod
    def validate_station_actions(cls, v: list[int]) -> list[int]:
        for action in v:
            if not isinstance(action, int) or action < 0 or action > 3:
                raise ValueError("Each station action must be int in [0, 3]")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "coordinator_action": {
                    "price_deltas": [0, 1, -1, 0, 0, 0, 0, 0, 0, 0],
                    "emergency_target_station": 0,
                },
                "station_actions": [1, 0, 1, 2, 1, 0, 1, 0, 1, 0],
            }
        }


# OpenEnv Observation Model
class StationFeaturesModel(BaseModel):
    """Features for a single station at current step."""

    queue_length: float
    charging_vehicles: float
    solar_kw: float
    grid_kw: float
    price_multiplier: float
    emergency_queue: float
    free_chargers: float

    class Config:
        json_schema_extra = {
            "description": "Per-station observation features [7 values]",
        }


class TimeContextModel(BaseModel):
    """Time-of-day context features."""

    day_fraction: float = Field(..., ge=0.0, le=1.0, description="Fraction of day elapsed")
    sin_component: float = Field(..., description="Sine of day angle")
    cos_component: float = Field(..., description="Cosine of day angle")


class ArrivalsSummaryModel(BaseModel):
    """Summary of vehicle arrivals this step."""

    total_arrivals: float = Field(..., ge=0.0, description="Total vehicles arrived")
    emergency_arrivals: float = Field(..., ge=0.0, description="Emergency vehicles arrived")
    mean_energy_kwh: float = Field(..., ge=0.0, description="Mean energy requirement")


class WeatherModel(BaseModel):
    """Current weather state."""

    weather_condition: str = Field(..., description="sunny | cloudy | rainy")

    @field_validator("weather_condition")
    @classmethod
    def validate_weather(cls, v: str) -> str:
        if v not in ("sunny", "cloudy", "rainy"):
            raise ValueError("weather_condition must be sunny, cloudy, or rainy")
        return v


class ObservationModel(BaseModel):
    """Full observation from the environment."""

    station_features: list[list[float]] = Field(
        ...,
        description="Per-station features: [queue, charging, solar_kw, grid_kw, price, emergency, free_chargers]",
    )
    queue_lengths: list[int] = Field(..., description="Queue length per station")
    time_context: dict[str, float] = Field(..., description="Time features: day_fraction, sin, cos")
    arrivals_summary: dict[str, float] = Field(
        ..., description="Arrivals: total, emergency, mean_energy"
    )
    weather: str = Field(..., description="sunny | cloudy | rainy")

    class Config:
        json_schema_extra = {
            "description": "Complete environment observation at current step"
        }

