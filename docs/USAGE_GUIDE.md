# USAGE_GUIDE.md - Complete Operation Manual

## Table of Contents
1. [Running Simulations](#running-simulations)
2. [Training Models](#training-models)
3. [Using the Dashboard](#dashboard)
4. [Advanced Operations](#advanced)
5. [Troubleshooting](#troubleshooting)
6. [FAQ](#faq)

---

## Running Simulations

### 1. Heuristic Agent (Baseline)
```bash
python -m ev_charging_grid_env.examples.run_rule_based_agent
```

**What it does**:
- Runs 10 episodes with fixed heuristic policies
- Reports statistics: avg reward, wait time, solar usage
- **Good for**: Baseline comparison

**Output**:
```
Episode 1: reward=950.2, wait_time=44.5, solar=20.1%
Episode 2: reward=962.1, wait_time=43.2, solar=21.3%
...
Average: reward=956.8, wait_time=44.9, solar=19.8%
```

### 2. Random Agent (Control)
```bash
python -m ev_charging_grid_env.examples.run_random_agent
```

**What it does**:
- Runs 10 episodes with random action selection
- Tests environment stability under random inputs
- **Good for**: Sanity check, verifying environment robustness

### 3. Trained Agent (Evaluation)
```bash
python -m ev_charging_grid_env.examples.evaluate_agents \
    --policy ppo \
    --episodes 5 \
    --checkpoint ./checkpoints/ppo_best.pt
```

**What it does**:
- Loads trained PPO model
- Runs evaluation episodes
- Shows performance vs baseline

**Available policies**:
- `ppo`: Proximal Policy Optimization
- `mappo`: Multi-Agent MAPPO
- `heuristic`: Rule-based baseline

### 4. Custom Simulation
```python
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

env = MultiAgentEVChargingGridEnv()
obs, _ = env.reset(seed=42)

for step in range(300):
    # Choose action (e.g., random)
    action = env.action_space.sample()
    
    obs, reward, terminated, truncated, info = env.step(action)
    
    print(f"Step {step}: reward={reward:.2f}, wait_time={info.get('events', {}).get('mean_wait', 0):.1f}")
    
    if terminated or truncated:
        break

print(f"Total episodes reward: {env.episode_stats['total_reward']:.2f}")
```

---

## Training Models

### Train PPO Agent
```bash
python -m ev_charging_grid_env.training.experiment_runner \
    --algo ppo \
    --total-timesteps 100000 \
    --num-envs 4 \
    --learning-rate 3e-4 \
    --checkpoint-freq 10
```

**PPO Configuration**:
- **n_steps**: 2048 (rollout buffer size)
- **batch_size**: 64
- **n_epochs**: 10 (policy updates per batch)
- **clip_range**: 0.2 (clipping parameter ε)

**Output**:
```
Timestep 10000: episode_reward=980.5, episode_length=300
Timestep 20000: episode_reward=1050.2, episode_length=300
...
Saved checkpoint: ./checkpoints/ppo_10000.pt
```

### Train MAPPO Agent
```bash
python -m ev_charging_grid_env.training.experiment_runner \
    --algo mappo \
    --total-timesteps 100000 \
    --num-envs 4 \
    --learning-rate 5e-4 \
    --agents 3  # Coordinator + 2 stations
```

**MAPPO Configuration**:
- **Centralized training**: Both agents share replay buffer
- **Decentralized execution**: Each agent acts independently
- **Value function**: Shared critic for better signals

### Monitor Training with TensorBoard
```bash
# Terminal 1: Start training
python -m ev_charging_grid_env.training.experiment_runner \
    --algo ppo \
    --total-timesteps 100000

# Terminal 2: Monitor
tensorboard --logdir ./logs
```

Then visit: **http://localhost:6006**

### Hyperparameter Tuning
```bash
python -m ev_charging_grid_env.examples.run_training_sweep \
    --config config/training/ppo_sweep_a.yaml
```

**Sweep parameters** (from config files):
- Learning rates: [1e-4, 3e-4, 5e-4]
- Batch sizes: [32, 64, 128]
- Gamma (discount): [0.99, 0.999]

---

## Dashboard

### Launch
```bash
streamlit run app.py
```

Then open: **http://localhost:8501**

### Tab 1: Live Ops (Real-time Control)

**Controls**:
- **Start/Pause**: Toggle simulation
- **Episode Length**: Adjust simulation length (50-500 steps)
- **Base Arrival Rate**: Change vehicle arrival frequency
- **Emergency Probability**: Adjust emergency vehicle percentage
- **Reset**: Restart simulation

**Visualizations**:
1. **Station Map**: 
   - Circles represent stations
   - Size = queue length
   - Color = charging activity
   
2. **Metrics Cards**:
   - Total Reward (cumulative)
   - Average Wait Time (minutes)
   - Solar Utilization (%)
   - Grid Overload Events

3. **Real-time Charts**:
   - Reward progression over time
   - Queue length history
   - Energy generation (solar vs grid)

### Tab 2: Analytics (Deep Insights)

**Charts**:

1. **Solar Breakdown Pie Chart**
   - % of energy from solar
   - % of energy from grid
   
2. **Emergency Timeline**
   - When emergencies arrived
   - When they were served
   - Response time distribution
   
3. **Distribution Charts**
   - Wait time distribution (histogram)
   - Reward distribution
   
4. **Heatmap**
   - Grid utilization by station and time

### Tab 3: Compare (Policy Comparison)

**Available Policies**:
- Heuristic (rule-based)
- Random (baseline)
- PPO (trained)
- MAPPO (multi-agent trained)

**Comparison Metrics**:
- Average reward
- Reward std-dev
- 95th percentile wait time
- Solar utilization
- Grid overload count

**Visualization**: Side-by-side bar charts

### Tab 4: Train AI (Model Training)

**Options**:
1. **Algorithm**: PPO or MAPPO
2. **Training Steps**: 10k - 1M
3. **Learning Rate**: 1e-4 to 1e-3
4. **Batch Size**: 32, 64, 128

**Progress**:
- Live episode reward curve
- Episode length tracking
- Estimated time remaining

**Export**: Download trained model as `.pt` file

---

## Advanced Operations

### 1. Multi-Scenario Evaluation
```python
import pandas as pd
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

scenarios = [
    {"base_arrival_rate": 4.0, "emergency_prob": 0.02},
    {"base_arrival_rate": 8.0, "emergency_prob": 0.04},
    {"base_arrival_rate": 12.0, "emergency_prob": 0.06},
]

results = []
for scenario in scenarios:
    env = MultiAgentEVChargingGridEnv(config=scenario)
    obs, _ = env.reset()
    
    total_reward = 0
    for _ in range(300):
        action = env.action_space.sample()
        obs, reward, done, _, _ = env.step(action)
        total_reward += reward
        if done:
            break
    
    results.append({
        "arrival_rate": scenario["base_arrival_rate"],
        "total_reward": total_reward,
        "avg_wait": env.episode_stats["total_wait_time"] / env.episode_stats["vehicles_seen"]
    })

df = pd.DataFrame(results)
print(df)
```

### 2. Custom Agent Implementation
```python
class MyCustomAgent:
    def __init__(self, num_stations):
        self.num_stations = num_stations
    
    def act(self, observation: dict) -> dict:
        """Your custom decision logic"""
        
        # Extract observation
        queue_lengths = observation["queue_lengths"]
        station_features = observation["station_features"]
        
        # Your logic here
        price_deltas = [1] * self.num_stations  # Example: increase all prices by $0.01
        emergency_target = queue_lengths.argmax()  # Direct emergencies to longest queue
        
        return {
            "coordinator_action": {
                "price_deltas": price_deltas,
                "emergency_target_station": emergency_target
            },
            "station_actions": [0] * self.num_stations  # 0 = hold, 1 = accept, etc.
        }

# Use it
agent = MyCustomAgent(num_stations=2)
env = MultiAgentEVChargingGridEnv()
obs, _ = env.reset()

for _ in range(300):
    action = agent.act(obs)
    obs, reward, done, _, _ = env.step(action)
    if done:
        break
```

### 3. A/B Testing Framework
```python
from ev_charging_grid_env.training.algorithms.ppo_trainer import PPOTrainer

# Train two models
model_a = PPOTrainer(config=config_a)
model_a.train(total_timesteps=100000)
model_a_performance = model_a.evaluate(num_episodes=20)

model_b = PPOTrainer(config=config_b)
model_b.train(total_timesteps=100000)
model_b_performance = model_b.evaluate(num_episodes=20)

# Statistical comparison
from scipy import stats
t_stat, p_value = stats.ttest_ind(
    model_a_performance,
    model_b_performance
)

print(f"Model A: {model_a_performance.mean():.2f} ± {model_a_performance.std():.2f}")
print(f"Model B: {model_b_performance.mean():.2f} ± {model_b_performance.std():.2f}")
print(f"p-value: {p_value:.4f} (significant: {p_value < 0.05})")
```

---

## Troubleshooting

### "Environment crashes after N steps"
Check for:
1. Invalid action format
2. NaN/Inf rewards (now protected by safety layer)
3. Out-of-bounds array access

**Fix**: Run test suite
```bash
pytest tests/test_stability_and_robustness.py -v
```

### "Training reward doesn't improve"
Possible causes:
- Learning rate too high/low: try 3e-4 to 5e-4
- Batch size too small: try 64 or 128
- Episode length too short: ensure >= 100 steps
- Reward signal too weak: check reward_functions.py

**Debug**:
```bash
tensorboard --logdir ./logs
# Look at reward curve, gradient norms
```

### "Dashboard is slow"
- Close other applications
- Reduce number of live-plot points (in app.py)
- Use `--logger.level=warning` to reduce logging

### "LLM integration fails"
Expected behavior - LLM is optional.

To debug:
```bash
python -c "from inference import setup_llm_client; client = setup_llm_client(); print('OK')"
```

---

## FAQ

### Q: What's the difference between heuristic, PPO, and MAPPO?

| Agent | Type | Training | Speed | Performance |
|-------|------|----------|-------|-------------|
| Heuristic | Rule-based | None | Instant | Baseline |
| PPO | RL (centralized) | 100k steps | ~30 min | Good |
| MAPPO | RL (decentralized) | 100k steps | ~45 min | Better |

### Q: How many episodes should I train?

- **Quick test**: 1000 timesteps
- **Development**: 50k timesteps (takes ~10 min)
- **Production**: 500k+ timesteps (takes ~2 hours)

### Q: Can I use my own environment config?

Yes:
```python
custom_config = {
    "base_arrival_rate": 10.0,
    "num_stations": 5,
    "episode_length": 500
}
env = MultiAgentEVChargingGridEnv(config=custom_config)
```

### Q: How do I save/load trained models?

```bash
# Saves to ./checkpoints/
python -m ev_charging_grid_env.training.experiment_runner --algo ppo

# Load and evaluate
python -m ev_charging_grid_env.examples.evaluate_agents \
    --policy ppo \
    --checkpoint ./checkpoints/ppo_best.pt
```

### Q: What if I get "CUDA out of memory"?

The environment runs on CPU by default. If using GPU training:
```python
# In trainer config
device = "cpu"  # or "cuda"
```

### Q: Can I run multiple environments in parallel?

Yes - native support in training:
```bash
python -m ev_charging_grid_env.training.experiment_runner \
    --algo ppo \
    --num-envs 8  # Use 8 parallel environments
```

---

**Next**: Read [API_REFERENCE.md](API_REFERENCE.md) for environment API details.
