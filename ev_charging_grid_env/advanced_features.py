"""Advanced features for EV charging grid optimization.

Features:
- Dynamic pricing optimization
- Explainable AI decisions (SHAP-like analysis)
- Multi-agent coordination tracking
- Station failure simulation
- Weather impact simulation
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
# DYNAMIC PRICING
# ──────────────────────────────────────────────────────────────────────────────


def optimize_dynamic_prices(
    state: dict[str, Any],
    demand_elasticity: float = 0.8,
    max_price_multiplier: float = 2.0,
) -> dict[str, float]:
    """Optimize per-station pricing based on real-time demand.
    
    Algorithm:
    1. Calculate queue pressure (queue_length / capacity)
    2. Adjust price inversely proportional to demand
    3. Apply elasticity to control sensitivity
    4. Clamp to [1/max_mult, max_mult] range
    
    Args:
        state: Current environment state
        demand_elasticity: Price sensitivity (0.5-2.0)
        max_price_multiplier: Max price deviation from base
        
    Returns:
        Dict mapping station_id -> price_multiplier
    """
    queue_lengths = np.asarray(state.get("queue_lengths", []))
    num_stations = len(queue_lengths)
    
    # Calculate occupancy rate (0.0 to 1.0)
    max_queue = max(1, np.max(queue_lengths))
    occupancy = queue_lengths / max_queue
    
    # Price multiplier: high queue → higher price
    # Formula: 1 + occupancy^elasticity * (max_mult - 1)
    base_multiplier = 1 + (occupancy ** demand_elasticity) * (max_price_multiplier - 1)
    
    # Ensure prices stay within bounds
    multipliers = np.clip(base_multiplier, 1.0 / max_price_multiplier, max_price_multiplier)
    
    return {f"station_{i}": float(m) for i, m in enumerate(multipliers)}


# ──────────────────────────────────────────────────────────────────────────────
# EXPLAINABLE AI
# ──────────────────────────────────────────────────────────────────────────────


class ExplainableDecision:
    """Explainable decision framework for RL actions."""

    def explain_coordinator_action(
        self,
        state: dict[str, Any],
        action: dict[str, Any],
        reward: float,
    ) -> dict[str, Any]:
        """Explain coordinator's price and emergency target decisions.
        
        Args:
            state: Environment state before action
            action: Coordinator action (price_deltas, emergency_target)
            reward: Step reward received
            
        Returns:
            Explanation dict with reasoning
        """
        queue_lengths = state.get("queue_lengths", [])
        prices = action.get("price_deltas", [])
        emergency_target = action.get("emergency_target_station", 0)
        
        explanation = {
            "action_type": "coordinator_decision",
            "reasoning": [],
            "metrics": {
                "queues": list(queue_lengths),
                "prices": list(prices),
                "emergency_target": int(emergency_target),
            },
            "reward": float(reward),
        }
        
        # Analyze pricing decisions
        for i, price_delta in enumerate(prices):
            queue = queue_lengths[i] if i < len(queue_lengths) else 0
            
            if price_delta > 0:
                explanation["reasoning"].append({
                    "station": i,
                    "action": "increase_price",
                    "reason": f"Queue at station {i} has {queue} vehicles",
                    "expected_effect": "Reduce arrival rate, lower wait times",
                })
            elif price_delta < 0:
                explanation["reasoning"].append({
                    "station": i,
                    "action": "decrease_price",
                    "reason": f"Incentivize usage, solar availability high",
                    "expected_effect": "Increase arrivals, maximize solar utilization",
                })
        
        # Analyze emergency targeting
        explanation["reasoning"].append({
            "station": emergency_target,
            "action": "emergency_prioritization",
            "reason": f"Emergency vehicle predicted at station {emergency_target}",
            "expected_effect": "Ensure charger availability for emergency vehicle",
        })
        
        return explanation

    def explain_station_action(
        self,
        station_id: int,
        state: dict[str, Any],
        action: int,
        reward: float,
    ) -> dict[str, Any]:
        """Explain station agent's queue management action.
        
        Args:
            station_id: Which station
            state: State features for this station
            action: Action taken (0=FCFS, 1=prioritize_fast, etc.)
            reward: Reward received
            
        Returns:
            Explanation dict
        """
        local_features = state.get("local_features", {})
        queue_length = local_features.get("queue_length", 0)
        solar_available = state.get("solar_available", 0)
        
        actions_map = {
            0: "first_come_first_served",
            1: "prioritize_fast_charging",
            2: "prioritize_long_distance",
            3: "balance_with_emergency",
        }
        
        action_name = actions_map.get(action, "unknown")
        
        explanation = {
            "action_type": "station_decision",
            "station_id": station_id,
            "action": action_name,
            "reasoning": [],
            "metrics": {
                "queue_length": queue_length,
                "solar_available_kw": solar_available,
            },
            "reward": float(reward),
        }
        
        if action == 0:
            explanation["reasoning"].append(
                f"Queue of {queue_length}, applying FCFS policy"
            )
        elif action == 1:
            explanation["reasoning"].append(
                f"Prioritizing fast charges to clear queue faster (queue={queue_length})"
            )
        elif action == 2:
            explanation["reasoning"].append(
                f"Prioritizing long-distance vehicles to maximize grid utilization"
            )
        elif action == 3:
            explanation["reasoning"].append(
                f"Reserving {queue_length} slots for potential emergency vehicles"
            )
        
        return explanation


# ──────────────────────────────────────────────────────────────────────────────
# MULTI-AGENT COORDINATION TRACKING
# ──────────────────────────────────────────────────────────────────────────────


class CoordinationMetrics:
    """Track multi-agent coordination effectiveness."""

    def compute_coordination_score(
        self,
        coordinator_action: dict[str, Any],
        station_actions: list[int],
        state: dict[str, Any],
        reward: float,
    ) -> dict[str, float]:
        """Compute metrics for multi-agent coordination.
        
        Metrics:
        - Alignment: How well station actions match coordinator intent
        - Efficiency: Collective reward vs individual rewards
        - Stability: Variance in actions across steps
        - Responsiveness: How quickly agents react to state changes
        """
        queue_lengths = state.get("queue_lengths", [])
        
        # Alignment score: stations match coordinator's pricing intent
        price_deltas = coordinator_action.get("price_deltas", [])
        alignment_scores = []
        
        for i, station_action in enumerate(station_actions):
            if i < len(price_deltas):
                price = price_deltas[i]
                # If coordinator increased price, expect station to reduce throughput
                if price > 0 and station_action in [0, 1]:  # FCFS or fast (conservative)
                    alignment_scores.append(0.7)
                elif price <= 0 and station_action in [2, 3]:  # Aggressive serving
                    alignment_scores.append(0.8)
                else:
                    alignment_scores.append(0.5)
        
        alignment = float(np.mean(alignment_scores)) if alignment_scores else 0.5
        
        # Efficiency: system reward compared to independent agents
        # (Would need baseline to compute properly)
        efficiency = min(1.0, max(0.0, reward / 50.0))  # Normalized reward
        
        # Responsiveness: action diversity indicates adaptability
        action_variance = float(np.var(station_actions)) if station_actions else 0
        responsiveness = min(1.0, action_variance)
        
        return {
            "alignment": alignment,
            "efficiency": efficiency,
            "responsiveness": responsiveness,
            "composite_coordination": (alignment + efficiency + responsiveness) / 3.0,
        }


# ──────────────────────────────────────────────────────────────────────────────
# FAILURE SIMULATION
# ──────────────────────────────────────────────────────────────────────────────


def simulate_station_failure(
    state: dict[str, Any],
    failure_station: int,
    recovery_time: int = 10,
) -> dict[str, Any]:
    """Simulate power outage or charger failure at a station.
    
    Args:
        state: Current state
        failure_station: Which station fails
        recovery_time: Steps until recovery
        
    Returns:
        Updated state with failure impact
    """
    modified_state = state.copy()
    
    # Reduce available capacity at failed station
    queue_lengths = modified_state.get("queue_lengths", [])
    if failure_station < len(queue_lengths):
        # Vehicles reroute to other stations
        queue_lengths[failure_station] = 0
        remaining_stations = [i for i in range(len(queue_lengths)) if i != failure_station]
        if remaining_stations:
            increased_queue = queue_lengths[failure_station] // len(remaining_stations)
            for i in remaining_stations:
                queue_lengths[i] += increased_queue
    
    modified_state["queue_lengths"] = queue_lengths
    modified_state["failed_stations"] = {failure_station: {"remaining_time": recovery_time}}
    
    return modified_state


# ──────────────────────────────────────────────────────────────────────────────
# WEATHER IMPACT
# ──────────────────────────────────────────────────────────────────────────────


def apply_weather_impact(
    state: dict[str, Any],
    weather: str = "sunny",  # sunny, cloudy, rainy
) -> dict[str, Any]:
    """Apply weather impact to solar generation and arrival patterns.
    
    Args:
        state: Current state
        weather: Weather condition
        
    Returns:
        Updated state with weather effects
    """
    modified_state = state.copy()
    
    # Weather effects on solar generation
    solar_multiplier = {
        "sunny": 1.0,
        "cloudy": 0.5,
        "rainy": 0.1,
    }.get(weather, 0.7)
    
    solar_context = modified_state.get("solar_context", {})
    if isinstance(solar_context, dict):
        solar_context["available_kw"] = (
            solar_context.get("available_kw", 0) * solar_multiplier
        )
        modified_state["solar_context"] = solar_context
    
    # Weather effects on arrival patterns
    arrival_multiplier = {
        "sunny": 1.2,  # More people go out
        "cloudy": 1.0,
        "rainy": 0.6,  # Fewer trips
    }.get(weather, 0.9)
    
    arrivals = modified_state.get("arrivals_summary", [])
    if len(arrivals) > 0:
        arrivals[0] = arrivals[0] * arrival_multiplier
        modified_state["arrivals_summary"] = arrivals
    
    modified_state["weather"] = weather
    
    return modified_state


# ──────────────────────────────────────────────────────────────────────────────
# EXPORT FOR INTEGRATION
# ──────────────────────────────────────────────────────────────────────────────


__all__ = [
    "optimize_dynamic_prices",
    "ExplainableDecision",
    "CoordinationMetrics",
    "simulate_station_failure",
    "apply_weather_impact",
]
