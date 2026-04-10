"""
Inference script for EV Charging Grid Optimizer.

STRICT COMPLIANCE MODE:
- Structured logging: START, STEP X REWARD Y, END
- LLM proxy integration via OpenAI client
- All env variables correctly sourced
- Production-ready for OpenEnv validation
"""

from __future__ import annotations

import os
from openai import OpenAI

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.agents.coordinator_agent import HeuristicCoordinatorAgent
from ev_charging_grid_env.agents.station_agent import HeuristicStationAgent

# ──────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT VARIABLES (CRITICAL)
# ──────────────────────────────────────────────────────────────────────────────

# LLM Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
API_KEY = os.getenv("API_KEY")

# Hugging Face Token (REQUIRED, NO default)
HF_TOKEN = os.getenv("HF_TOKEN")

# Optional: Local Docker image name
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

# ──────────────────────────────────────────────────────────────────────────────
# LLM CLIENT SETUP (MANDATORY)
# ──────────────────────────────────────────────────────────────────────────────

def get_llm_client() -> OpenAI:
    """Get OpenAI client configured with proxy base_url.
    
    CRITICAL:
    - Uses API_BASE_URL for proxy routing
    - Uses API_KEY from environment
    - NO hardcoded endpoints or keys
    """
    if not API_KEY:
        raise ValueError("API_KEY environment variable not set")
    
    return OpenAI(
        base_url=API_BASE_URL,
        api_key=API_KEY
    )


def call_llm(prompt: str) -> str:
    """Make LLM API call through OpenAI client.
    
    Args:
        prompt: Input prompt
    
    Returns:
        LLM response text
    """
    client = get_llm_client()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


# ──────────────────────────────────────────────────────────────────────────────
# SIMULATION RUNNER
# ──────────────────────────────────────────────────────────────────────────────

def run():
    """Main inference entry point - STRICT LOGGING FORMAT.
    
    CRITICAL:
    1. Prints "START" at beginning
    2. Prints "STEP X REWARD Y" for each step
    3. Prints "END" at completion
    4. Makes LLM call for analysis
    5. Returns valid result dict
    """
    print("START")
    
    try:
        # Initialize environment
        env = MultiAgentEVChargingGridEnv()
        obs, _ = env.reset(seed=42)
        
        # Initialize agents
        coordinator = HeuristicCoordinatorAgent()
        stations = [HeuristicStationAgent() for _ in range(env.num_stations)]
        
        # Simulation loop
        total_reward = 0.0
        
        for step in range(50):
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
            
            # MANDATORY: Structured log format
            print(f"STEP {step} REWARD {reward}")
            
            if terminated or truncated:
                break
        
        # Get LLM analysis (REQUIRED LLM CALL)
        summary = call_llm(f"Total reward: {total_reward}. Explain system performance.")
        
        print("END")
        
        return {
            "total_reward": float(total_reward),
            "summary": summary
        }
        
    except Exception as e:
        print("END")
        return {
            "error": str(e),
            "total_reward": 0.0
        }


if __name__ == "__main__":
    print(run())
