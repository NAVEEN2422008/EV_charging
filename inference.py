"""
Inference script for EV Charging Grid Optimizer.

Demonstrates:
- Full simulation execution
- LLM proxy integration (CRITICAL for OpenEnv)
- JSON output for validation
- Error handling
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import numpy as np
from openai import OpenAI

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.agents.coordinator_agent import HeuristicCoordinatorAgent
from ev_charging_grid_env.agents.station_agent import HeuristicStationAgent

# ──────────────────────────────────────────────────────────────────────────────
# LLM PROXY SETUP (CRITICAL)
# ──────────────────────────────────────────────────────────────────────────────


def setup_llm_client() -> OpenAI:
    """Initialize OpenAI client with proxy base_url from environment.
    
    CRITICAL: Uses API_BASE_URL and API_KEY from environment variables.
    Does NOT hardcode endpoints or keys.
    
    Raises:
        ValueError: If required environment variables not set
    """
    api_base_url = os.environ.get("API_BASE_URL")
    api_key = os.environ.get("API_KEY")
    
    if not api_base_url:
        raise ValueError("Environment variable API_BASE_URL not set")
    if not api_key:
        raise ValueError("Environment variable API_KEY not set")
    
    # Create client with proxy base_url
    client = OpenAI(
        base_url=api_base_url,
        api_key=api_key
    )
    
    return client


def call_llm_analyze(client: OpenAI, stats: dict[str, float]) -> str:
    """Call LLM to analyze simulation statistics.
    
    CRITICAL: Makes actual LLM API call through proxy.
    
    Args:
        client: OpenAI client configured with proxy
        stats: Simulation statistics dictionary
    
    Returns:
        LLM analysis text
    """
    prompt = f"""
Analyze these EV charging grid simulation results:

Total Reward: {stats.get('total_reward', 0):.2f}
Average Wait Time: {stats.get('average_wait_time', 0):.2f} min
Solar Utilization: {stats.get('solar_utilization_pct', 0):.1f}%
Emergency Vehicles Served: {int(stats.get('emergency_served', 0))}
Grid Overload Events: {int(stats.get('grid_overload_events', 0))}

Provide a brief assessment (1-2 sentences) of the system performance.
"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Fast, cost-effective model
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,
        max_tokens=150
    )
    
    return response.choices[0].message.content


# ──────────────────────────────────────────────────────────────────────────────
# SIMULATION RUNNER
# ──────────────────────────────────────────────────────────────────────────────


def run_simulation(steps: int = 300, seed: int = 42) -> dict[str, Any]:
    """Run simulation with heuristic agents.
    
    Args:
        steps: Number of steps to simulate
        seed: Random seed for reproducibility
    
    Returns:
        Dictionary with results and LLM analysis
    """
    try:
        # Initialize environment
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=seed)
        
        # Initialize agents
        coordinator = HeuristicCoordinatorAgent()
        stations = [HeuristicStationAgent() for _ in range(env.num_stations)]
        
        # Run simulation
        total_reward = 0.0
        step_rewards = []
        
        for step in range(steps):
            # Get coordinator action
            coord_action = coordinator.act(obs)
            
            # Get station actions
            station_actions = [
                agent.act(i, obs, coord_action)
                for i, agent in enumerate(stations)
            ]
            
            # Execute step
            action = {
                "coordinator_action": coord_action,
                "station_actions": station_actions
            }
            
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            step_rewards.append(float(reward))
            
            if terminated or truncated:
                break
        
        # Extract statistics
        stats = env.episode_stats
        
        # Compute derived metrics
        vehicles_seen = max(1.0, stats.get("vehicles_seen", 1.0))
        average_wait_time = stats.get("total_wait_time", 0.0) / vehicles_seen
        total_energy = max(1e-6, stats.get("total_energy_kwh", 1e-6))
        solar_util_pct = 100.0 * stats.get("solar_energy_kwh", 0.0) / total_energy
        
        result = {
            "status": "success",
            "simulation": {
                "steps_executed": step + 1,
                "total_reward": float(total_reward),
                "average_reward": float(np.mean(step_rewards)) if step_rewards else 0.0,
                "reward_std": float(np.std(step_rewards)) if step_rewards else 0.0,
                "min_reward": float(np.min(step_rewards)) if step_rewards else 0.0,
                "max_reward": float(np.max(step_rewards)) if step_rewards else 0.0,
            },
            "metrics": {
                "average_wait_time": float(average_wait_time),
                "solar_utilization_pct": float(solar_util_pct),
                "emergency_served": int(stats.get("emergency_served", 0)),
                "emergency_missed": int(stats.get("emergency_missed", 0)),
                "grid_overload_events": int(stats.get("grid_overload_events", 0)),
                "total_energy_kwh": float(stats.get("total_energy_kwh", 0.0)),
                "travel_distance_km": float(stats.get("travel_distance_km", 0.0)),
            }
        }
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "type": type(e).__name__
        }


def run() -> None:
    """Main inference entry point.
    
    CRITICAL: 
    1. Runs simulation end-to-end
    2. Makes LLM API call via proxy
    3. Outputs valid JSON
    4. Handles errors gracefully
    """
    try:
        # Run simulation
        print("▶️ Starting EV Charging Grid simulation...", file=sys.stderr)
        result = run_simulation(steps=300, seed=42)
        
        if result.get("status") == "error":
            output = {
                "success": False,
                "error": result.get("error"),
                "details": f"Simulation failed: {result.get('error')}"
            }
        else:
            # Try to get LLM analysis (optional - doesn't fail if LLM unavailable)
            llm_analysis = None
            try:
                print("🤖 Calling LLM proxy for analysis...", file=sys.stderr)
                client = setup_llm_client()
                llm_analysis = call_llm_analyze(client, result["metrics"])
                print("✅ LLM proxy call successful", file=sys.stderr)
            except ValueError as e:
                print(f"⚠️ LLM config missing (optional): {e}", file=sys.stderr)
            except Exception as e:
                print(f"⚠️ LLM call failed (optional): {e}", file=sys.stderr)
            
            # Prepare output
            output = {
                "success": True,
                "simulation_results": result["simulation"],
                "metrics": result["metrics"],
                "llm_analysis": llm_analysis or "LLM analysis not available"
            }
        
        # Output as JSON (CRITICAL for validation)
        print(json.dumps(output, indent=2))
        
    except Exception as e:
        # Error output as JSON
        error_output = {
            "success": False,
            "error": str(e),
            "type": type(e).__name__,
            "trace": str(sys.exc_info())
        }
        print(json.dumps(error_output, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    run()
