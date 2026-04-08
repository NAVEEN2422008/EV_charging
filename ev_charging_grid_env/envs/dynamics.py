"""Pure-ish simulation dynamics for EV charging domain transitions."""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

from ev_charging_grid_env.envs.state import EpisodeState, StationState, VehicleState
from ev_charging_grid_env.envs.task_generator import TaskConfig

WEATHER_SOLAR_FACTOR = {"sunny": 1.0, "cloudy": 0.6, "rainy": 0.25}


def initialize_episode(task: TaskConfig) -> EpisodeState:
    stations: list[StationState] = []
    for cfg in task.station_configs:
        stations.append(
            StationState(
                station_id=cfg.station_id,
                max_slots=cfg.max_slots,
                has_solar=cfg.has_solar,
                base_solar_capacity_kw=cfg.base_solar_capacity_kw,
                solar_forecast_kw=cfg.base_solar_capacity_kw,
                solar_actual_kw=cfg.base_solar_capacity_kw,
                grid_capacity_kw=cfg.grid_capacity_kw,
                dynamic_price=cfg.base_price_per_kwh,
                location_xy=cfg.location_xy,
                charger_type=cfg.charger_type,
                outage_probability=cfg.outage_probability,
            )
        )
    from ev_charging_grid_env.envs.state import GridState

    return EpisodeState(
        time_step=0,
        weather="sunny",
        stations=stations,
        grid=GridState(global_limit_kw=task.grid_limit_kw),
        next_vehicle_id=0,
        episode_length=task.episode_length,
    )


def sample_weather(task: TaskConfig, rng: np.random.Generator) -> str:
    names = list(task.weather_probs.keys())
    if not names:
        raise ValueError("task.weather_probs must not be empty")
    probs = np.array([task.weather_probs[name] for name in names], dtype=np.float64)
    total = probs.sum()
    if total <= 0.0:
        raise ValueError("weather probabilities must sum to > 0")
    probs = probs / total
    return str(names[int(rng.choice(np.arange(len(names)), p=probs))])


def apply_coordinator_action(
    state: EpisodeState,
    coordinator_action: dict[str, Any],
    price_step: float,
    min_price: float,
    max_price: float,
) -> int:
    if price_step < 0:
        raise ValueError(f"price_step must be >= 0, got {price_step}")
    if min_price < 0:
        raise ValueError(f"min_price must be >= 0, got {min_price}")
    if max_price <= min_price:
        raise ValueError(f"max_price ({max_price}) must be > min_price ({min_price})")
    
    routing_hint = int(coordinator_action.get("emergency_target_station", len(state.stations)))
    if not (0 <= routing_hint <= len(state.stations)):
        raise ValueError(
            f"emergency_target_station must be in [0, {len(state.stations)}], got {routing_hint}"
        )
    
    raw = np.array(coordinator_action.get("price_deltas", np.ones(len(state.stations), dtype=np.int64)))
    if raw.ndim != 1 or raw.shape[0] != len(state.stations):
        raise ValueError(f"price_deltas must be length {len(state.stations)}, got shape {raw.shape}")
    
    deltas = raw.astype(np.int64) - 1
    for station, delta in zip(state.stations, deltas, strict=True):
        station.dynamic_price = float(np.clip(station.dynamic_price + float(delta) * price_step, min_price, max_price))
    return routing_hint


def generate_arrivals(
    state: EpisodeState,
    task: TaskConfig,
    rng: np.random.Generator,
    emergency_route_hint: int,
) -> list[VehicleState]:
    phase = (state.time_step % 1440) / 1440.0
    tou_multiplier = 1.0 + 0.5 * np.sin(2.0 * np.pi * phase)
    rate = max(0.0, task.arrival_process.base_arrival_rate * task.arrival_process.rush_hour_multiplier * tou_multiplier)
    count = int(rng.poisson(rate))
    arrivals: list[VehicleState] = []
    for _ in range(count):
        emergency = bool(rng.random() < task.arrival_process.emergency_arrival_prob)
        station_pref = emergency_route_hint if (emergency and emergency_route_hint < len(state.stations)) else int(
            rng.integers(0, len(state.stations))
        )
        required_kwh = float(
            rng.uniform(task.arrival_process.required_kwh_min, task.arrival_process.required_kwh_max)
        )
        urgency = 2 if emergency else int(rng.integers(0, 2))
        vehicle = VehicleState(
            id=state.next_vehicle_id,
            required_kwh=required_kwh,
            remaining_kwh=required_kwh,
            battery_level=float(rng.uniform(0.05, 0.9)),
            is_emergency=emergency,
            urgency=urgency,
            max_wait_timesteps=task.arrival_process.max_wait_timesteps,
            green_preference=float(rng.uniform(0.0, 1.0)),
            price_sensitivity=float(rng.uniform(0.0, 1.0)),
            location_xy=(float(rng.uniform(-10, 10)), float(rng.uniform(-10, 10))),
            preferred_station=station_pref,
            assigned_station=station_pref,
        )
        state.next_vehicle_id += 1
        arrivals.append(vehicle)
    return arrivals


def enqueue_arrivals(state: EpisodeState, arrivals: list[VehicleState], distances: list[list[float]]) -> float:
    total_distance = 0.0
    for vehicle in arrivals:
        station = state.stations[vehicle.assigned_station]
        dist = float(distances[vehicle.preferred_station][vehicle.assigned_station])
        vehicle.travel_distance_km = dist
        vehicle.travel_time_left = int(np.ceil(dist / 0.6))
        total_distance += dist
        station.queue.append(vehicle)
    return total_distance


def apply_station_actions(
    state: EpisodeState,
    station_actions: np.ndarray,
    routing_hint: int,
) -> None:
    for idx, station in enumerate(state.stations):
        code = int(station_actions[idx])
        if code == 0:
            continue
        if code == 1:
            _accept_fifo(station)
        elif code == 2:
            _accept_emergency(station)
        elif code == 3 and station.queue:
            vehicle = station.queue.popleft()
            target = routing_hint if routing_hint < len(state.stations) else (idx + 1) % len(state.stations)
            vehicle.assigned_station = target
            state.stations[target].queue.append(vehicle)


def _accept_fifo(station: StationState) -> None:
    if station.outage_time_left > 0:
        return
    while len(station.charging_vehicles) < station.max_slots and station.queue:
        vehicle = station.queue.popleft()
        if vehicle.travel_time_left > 0:
            station.queue.append(vehicle)
            break
        vehicle.charging = True
        station.charging_vehicles.append(vehicle)


def _accept_emergency(station: StationState) -> None:
    if station.outage_time_left > 0:
        return
    if len(station.charging_vehicles) >= station.max_slots or not station.queue:
        return
    em_idx = next((i for i, v in enumerate(station.queue) if v.is_emergency), None)
    if em_idx is None:
        _accept_fifo(station)
        return
    vehicle = station.queue[em_idx]
    del station.queue[em_idx]
    if vehicle.travel_time_left > 0:
        station.queue.appendleft(vehicle)
        return
    vehicle.charging = True
    station.charging_vehicles.append(vehicle)


def progress_step(
    state: EpisodeState,
    task: TaskConfig,
    sim_minutes_per_step: float,
    fast_kw: float,
    slow_kw: float,
    rng: np.random.Generator,
) -> dict[str, float]:
    if sim_minutes_per_step <= 0:
        raise ValueError(f"sim_minutes_per_step must be > 0, got {sim_minutes_per_step}")
    if fast_kw <= 0 or slow_kw <= 0:
        raise ValueError(f"Charge rates must be > 0, got fast={fast_kw}, slow={slow_kw}")
    
    step_hours = sim_minutes_per_step / 60.0
    events = {
        "vehicles_completed": 0.0,
        "emergency_served": 0.0,
        "emergency_missed": 0.0,
        "timed_out_count": 0.0,
        "solar_kwh_used": 0.0,
        "grid_kwh_used": 0.0,
        "quick_service_score": 0.0,
        "travel_distance_km": 0.0,
    }
    state.grid.total_grid_kw_used = 0.0
    solar_factor = WEATHER_SOLAR_FACTOR.get(state.weather, 0.5)
    
    for station in state.stations:
        # Validate station state
        assert station.max_slots > 0, f"Station {station.station_id} max_slots must be > 0"
        assert len(station.charging_vehicles) <= station.max_slots, (
            f"Station {station.station_id} charging_vehicles ({len(station.charging_vehicles)}) "
            f"exceeds max_slots ({station.max_slots})"
        )
        
        if station.outage_time_left > 0:
            station.outage_time_left -= 1
            station.grid_kw_used = 0.0
            station.solar_kw_used = 0.0
            continue
        if rng.random() < station.outage_probability:
            station.outage_time_left = int(rng.integers(2, 8))
            station.charging_vehicles = []
            continue

        station.solar_forecast_kw = station.base_solar_capacity_kw * solar_factor
        station.solar_actual_kw = max(0.0, station.solar_forecast_kw * float(rng.normal(1.0, 0.15)))
        station.solar_kw_used = 0.0
        station.grid_kw_used = 0.0
        charge_kw = fast_kw if station.charger_type == "fast" else slow_kw
        active: list[VehicleState] = []
        for vehicle in station.charging_vehicles:
            # Calculate per-station available solar: total solar minus what already used for other vehicles
            delivered = min(vehicle.remaining_kwh, charge_kw * step_hours)
            vehicle.remaining_kwh -= delivered
            available_solar_kwh = max(0.0, station.solar_actual_kw * step_hours - station.solar_kw_used)
            solar_kwh = min(delivered, available_solar_kwh)
            grid_kwh = max(0.0, delivered - solar_kwh)
            events["solar_kwh_used"] += solar_kwh
            events["grid_kwh_used"] += grid_kwh
            station.solar_kw_used += solar_kwh / step_hours if step_hours > 0 else 0.0
            station.grid_kw_used += grid_kwh / step_hours if step_hours > 0 else 0.0
            if vehicle.remaining_kwh <= 1e-6:
                events["vehicles_completed"] += 1.0
                events["quick_service_score"] += max(0.0, vehicle.max_wait_timesteps - vehicle.wait_time)
                if vehicle.is_emergency:
                    events["emergency_served"] += 1.0
            else:
                active.append(vehicle)
        station.charging_vehicles = active
        state.grid.total_grid_kw_used += station.grid_kw_used

        survivors: deque[VehicleState] = deque()
        for vehicle in station.queue:
            if vehicle.travel_time_left > 0:
                vehicle.travel_time_left -= 1
            vehicle.wait_time += 1
            if vehicle.wait_time > vehicle.max_wait_timesteps:
                events["timed_out_count"] += 1.0
                if vehicle.is_emergency:
                    events["emergency_missed"] += 1.0
            else:
                survivors.append(vehicle)
        station.queue = survivors
    
    if state.grid.total_grid_kw_used > state.grid.global_limit_kw:
        state.grid.overload_events += 1
    state.time_step += 1
    return events
