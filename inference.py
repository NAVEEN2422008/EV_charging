import os
from openai import OpenAI
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

# ENV VARIABLES (STRICT REQUIREMENTS)
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.getenv("HF_TOKEN")  # NO default
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

# LLM CLIENT (PROXY REQUIRED)
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=os.getenv("API_KEY")
)


def call_llm(prompt):
    """Make LLM call through proxy."""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def run():
    """Main inference entry point - EXACT BRACKETED LOG FORMAT."""
    print("[START]")

    env = MultiAgentEVChargingGridEnv()
    obs, _ = env.reset()

    total_reward = 0

    for step in range(50):
        # Simple action policy
        action = {
            "coordinator_action": {
                "price_deltas": [1] * env.num_stations,
                "emergency_target_station": 0,
            },
            "station_actions": [0] * env.num_stations,
        }
        
        obs, reward, done, _, _ = env.step(action)
        total_reward += reward

        # EXACT FORMAT: [STEP] step=X reward=Y
        print(f"[STEP] step={step} reward={reward}")

    # REQUIRED: LLM call
    summary = call_llm(f"Total reward: {total_reward}. Explain performance.")

    print("[END]")

    return {
        "total_reward": float(total_reward),
        "summary": summary
    }


if __name__ == "__main__":
    print(run())
