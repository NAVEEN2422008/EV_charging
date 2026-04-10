# Multi-Agent EV Charging Grid Optimizer — Documentation

> **Real-time multi-agent reinforcement learning for urban EV charging infrastructure optimization.**
> Agents learn to minimize wait times, prevent grid overload, maximize solar usage, and prioritize emergency vehicles.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Installation & Setup](#2-installation--setup)
3. [How to Run](#3-how-to-run)
4. [How to Test](#4-how-to-test)
5. [How to Train](#5-how-to-train)
6. [How to Use the Dashboard](#6-how-to-use-the-dashboard)
7. [File-by-File Explanation](#7-file-by-file-explanation)
8. [Execution Flow](#8-execution-flow)
9. [Simple Explanation (Beginner-Friendly)](#9-simple-explanation-beginner-friendly)
10. [Limitations](#10-limitations)
11. [Future Improvements](#11-future-improvements)

---

## 1. Project Overview

### What is this?

A **multi-agent reinforcement learning (MARL)** environment simulating an urban electric vehicle (EV) charging network. Multiple AI agents cooperate to manage 10 charging stations across a city grid.

### The Problem

EV charging stations face a complex optimization challenge every minute:
- Vehicles arrive randomly with different battery needs and urgency
- Solar energy is available but intermittent (weather-dependent)
- The city power grid has a hard capacity limit
- Emergency vehicles must be served immediately
- Prices must be set dynamically to balance demand

### The Solution

Two levels of AI agent:

| Agent | Role | Controls |
|-------|------|----------|
| **Coordinator** | City-level controller | Sets dynamic prices, routes emergency vehicles |
| **Station Agent** (×10) | Local station controller | Decides to accept, queue, or redirect each vehicle |

### Algorithms Implemented

- **PPO** (Proximal Policy Optimization) — centralized joint-action control
- **MAPPO** (Multi-Agent PPO) — decentralized station agents with shared policy
- **Heuristic** — rule-based baseline (best for demo)
- **Random** — random action baseline

---

## 2. Installation & Setup

### Requirements

- Python 3.11+
- Windows / Linux / macOS

### Steps

```bash
# 1. Clone or navigate to the project directory
cd path/to/meta

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 4. Install in editable mode (installs all dependencies)
pip install -e .

# Or install from requirements.txt:
pip install -r requirements.txt
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `gymnasium` | Standard RL environment interface |
| `pettingzoo` | Multi-agent environment interface |
| `numpy` | Numerical operations |
| `torch` | Neural network training (PPO/MAPPO) |
| `tensorboard` | Training metrics logging |
| `streamlit` | Interactive web dashboard |
| `plotly` | Interactive charts |
| `pandas` | Data handling |
| `pyyaml` | Configuration loading |

---

## 3. How to Run

### Launch the Dashboard (recommended)

```bash
streamlit run app.py
```

Opens at **http://localhost:8501** in your browser.

### Run a Quick Simulation (Python)

```python
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.agents.coordinator_agent import HeuristicCoordinatorAgent
from ev_charging_grid_env.agents.station_agent import HeuristicStationAgent

env = MultiAgentEVChargingGridEnv()
obs, _ = env.reset(seed=42)

coordinator = HeuristicCoordinatorAgent()
stations = [HeuristicStationAgent() for _ in range(env.num_stations)]

for step in range(100):
    coord_action = coordinator.act(obs)
    station_actions = [s.act(i, obs, coord_action) for i, s in enumerate(stations)]
    action = {"coordinator_action": coord_action, "station_actions": station_actions}
    obs, reward, terminated, truncated, info = env.step(action)
    if truncated:
        break

print(f"Episode stats: {env.episode_stats}")
```

### Run with PettingZoo interface

```python
from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv

env = PettingZooEVChargingEnv()
env.reset(seed=42)

for agent in env.agent_iter():
    obs = env.observe(agent)
    action = env.action_space(agent).sample()
    env.step(action)
    if all(env.truncations.values()):
        break
```

---

## 4. How to Test

### Run All Tests

```bash
pytest ev_charging_grid_env/tests/ -v
```

### Run Specific Test Files

```bash
# Environment API tests
pytest ev_charging_grid_env/tests/test_env_api.py -v

# Reward logic tests
pytest ev_charging_grid_env/tests/test_reward_logic.py -v

# Advanced tests (new comprehensive suite)
pytest ev_charging_grid_env/tests/test_advanced.py -v

# Quick sanity only
pytest ev_charging_grid_env/tests/test_training_sanity.py -v
```

### Expected Output

```
90 passed in ~140s
```

All 90 tests must pass. The training tests (PPO/MAPPO tiny runs) take ~2 minutes.

### Test Coverage Areas

| Test File | What it Covers |
|-----------|---------------|
| `test_env_api.py` | Reset, step, observation shapes, truncation |
| `test_reward_logic.py` | Reward computation, emergency bonuses |
| `test_edge_cases.py` | Zero traffic, grid overload, outages |
| `test_pettingzoo_api.py` | PettingZoo API compliance |
| `test_agents_and_integration.py` | Heuristic/Random agent end-to-end |
| `test_fixes_and_robustness.py` | Action validation, solar distribution |
| `test_training_sanity.py` | PPO/MAPPO tiny training runs |
| `test_advanced.py` | Model save/load, single-station, space compliance, reward sensitivity |

---

## 5. How to Train

### Method 1: Via Dashboard (easiest)

1. Open dashboard with `streamlit run app.py`
2. Click **🤖 Train AI** tab
3. Select algorithm (PPO or MAPPO), steps, and hyperparameters
4. Click **Start Training**
5. Download the checkpoint when complete

### Method 2: Experiment Runner (CLI)

```bash
# Train PPO (single seed)
python -m ev_charging_grid_env.training.experiment_runner \
  --config ev_charging_grid_env/config/config.yaml \
  --algorithm ppo \
  --seeds 42 \
  --output runs/

# Train MAPPO (3 seeds for statistical significance)
python -m ev_charging_grid_env.training.experiment_runner \
  --config ev_charging_grid_env/config/config.yaml \
  --algorithm mappo \
  --seeds 42 43 44 \
  --output runs/
```

### Method 3: Python API

```python
from pathlib import Path
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.training.algorithms.ppo_trainer import PPOConfig, PPOTrainer

env = MultiAgentEVChargingGridEnv()
config = PPOConfig(
    total_steps=100_000,
    rollout_steps=512,
    epochs=4,
    lr=3e-4,
    gamma=0.99,
    seed=42,
)
trainer = PPOTrainer(env, config, run_dir=Path("runs/ppo_run1"))
results = trainer.train()
print(results)
```

### Hyperparameter Reference

| Parameter | Default | Effect |
|-----------|---------|--------|
| `total_steps` | 40,000 | Total environment interactions |
| `rollout_steps` | 512 | Steps per update batch |
| `epochs` | 4 | Policy update epochs per batch |
| `lr` | 3e-4 | Adam learning rate |
| `gamma` | 0.99 | Discount factor (future reward weight) |
| `gae_lambda` | 0.95 | GAE smoothing coefficient |
| `clip_coef` | 0.2 | PPO clipping epsilon |
| `entropy_coef` | 0.01 | Entropy regularization |
| `reward_norm` | True | Normalize rewards with running stats |

### Model Saving / Loading

```python
import torch

# Save
torch.save(trainer.model.state_dict(), "ppo_checkpoint.pt")

# Load
from ev_charging_grid_env.training.models.actor_critic import CentralizedActorCritic
model = CentralizedActorCritic(obs_dim=..., num_stations=10)
model.load_state_dict(torch.load("ppo_checkpoint.pt", weights_only=True))
```

### Monitoring with TensorBoard

```bash
tensorboard --logdir runs/
```

Opens at **http://localhost:6006** — shows reward, policy loss, value loss, entropy curves per update.

---

## 6. How to Use the Dashboard

### Start

```bash
streamlit run app.py
```

### Tabs

#### 🔴 Live Operations
The main simulation view. Controls at the top:

| Button | Action |
|--------|--------|
| ▶ Start | Auto-run simulation at set refresh rate |
| ⏸ Pause | Freeze simulation |
| ⏭ Step | Advance exactly 1 timestep |
| 🔄 Reset | Restart the episode |

**Charts:**
- **Station Map** — Bubble map of all stations. Size = queue length. Color = status (green=solar, blue=grid, red=outage). Diamonds = incoming vehicles.
- **Queue & Charging Load** — Stacked bar per station
- **Grid Utilization Gauge** — Real-time grid pressure %
- **Solar vs Grid Donut** — Energy mix at current step
- **Station Load Heatmap** — Compact view of queued/charging/kW

**AI Insights Panel** — Automatically generates color-coded observations about grid health, solar usage, emergency response, and wait times.

#### 📊 Analytics
Deep-dive metrics for the current episode:
- Solar utilization trend
- Emergency response timeline
- Step reward distribution histogram
- Episode summary table

#### ⚔️ Compare Policies
Benchmark multiple policies head-to-head:
1. Select policies (Random, Heuristic, PPO, MAPPO)
2. Set number of simulation steps
3. Click **Run Benchmark**
4. View bar chart + radar chart comparison
5. Download results as CSV

#### 🤖 Train AI
Launch training directly from the browser:
1. Choose algorithm (PPO / MAPPO)
2. Set steps, learning rate, discount factor
3. Click **Start Training** (runs in background thread)
4. Refresh log to see progress
5. Download checkpoint when complete

### Sidebar Controls

| Control | Effect |
|---------|--------|
| Traffic Intensity | Arrival rate of vehicles (Poisson λ) |
| Solar Capacity | Max solar power per solar-enabled station |
| Emergency Rate | Probability each vehicle is emergency |
| Grid Limit | Total city power draw cap |
| Episode Length | How many timesteps per episode |
| Policy | Which agent policy to use |
| Steps per Run | How many steps taken per refresh cycle |
| Refresh interval | Milliseconds between auto-refresh |

---

## 7. File-by-File Explanation

### Root

| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit dashboard — all 4 tabs, AI insights, training panel |
| `requirements.txt` | Package dependencies |
| `pyproject.toml` | Package build config, pytest settings |
| `Dockerfile` | Container definition for deployment |

### `ev_charging_grid_env/envs/`

#### `state.py`
Defines pure Python dataclasses (no logic):
- `VehicleState` — vehicle id, battery, urgency, position, wait time
- `StationState` — slots, queue, solar/grid power used, dynamic price
- `GridState` — global limit, total kW used, overload count
- `EpisodeState` — time step, weather, all stations, grid

Uses `@dataclass(slots=True)` for memory efficiency.

#### `task_generator.py`
Generates a `TaskConfig` for each episode:
- Calculates station positions (circular city layout)
- Assigns solar to a configurable fraction of stations
- Computes distance matrix between all station pairs
- Validates weather probabilities
- Key function: `generate_task(config: dict) -> TaskConfig`

#### `dynamics.py`
Pure simulation functions (no classes — stateless):

| Function | What it does |
|----------|-------------|
| `initialize_episode(task)` | Creates all station states at step 0 |
| `sample_weather(task, rng)` | Samples weather from probability distribution |
| `apply_coordinator_action(state, action, ...)` | Updates dynamic prices, returns routing hint |
| `generate_arrivals(state, task, rng, hint)` | Poisson-samples new vehicle arrivals |
| `enqueue_arrivals(state, arrivals, distances)` | Places vehicles in station queues |
| `apply_station_actions(state, actions, hint)` | Executes FIFO/emergency/redirect per station |
| `progress_step(state, task, ...)` | Charges vehicles, ages queues, records events |

#### `reward_functions.py`
Computes the scalar step reward from simulation events:

```
reward = 
  + completion_bonus × vehicles_completed
  + emergency_bonus × emergency_served
  + solar_weight × solar_kwh
  + fast_service × quick_service_score
  − wait_weight × mean_wait_time
  − timeout_weight × timed_out_count
  − overload_weight × overload_kw
  − emergency_bonus × 1.2 × emergency_missed
  − travel_weight × travel_distance
```
Clipped to `[-reward_clip, +reward_clip]`.

#### `spaces.py`
Builds Gymnasium observation and action spaces:
- `build_observation_space(n)` — Dict with station_features, arrivals_summary, time_context, weather, queue_lengths
- `build_action_space(n)` — Dict with coordinator_action (price_deltas + emergency_target) + station_actions

#### `ev_charging_env.py`
`MultiAgentEVChargingGridEnv(gym.Env)` — the centralized Gym environment:
- `reset(seed)` — reinitializes episode, returns observation
- `step(action)` — runs one simulation tick: coordinator action → arrivals → station actions → progress → reward
- `_build_observation()` — constructs the observation dict from current state
- Validates all actions on every step

#### `pettingzoo_ev_env.py`
`PettingZooEVChargingEnv(AECEnv)` — AEC multi-agent interface:
- 1 coordinator agent + 10 station agents take turns
- Coordinator acts first, stations act in order, then the joint action runs the gym env
- Each station gets a local+global partial observation with an action mask
- Reward is shared equally across all agents

#### `communication.py`
Lightweight multi-agent communication:
- `coordinator_broadcast(obs, target)` — sends emergency routing hint to all stations
- `build_station_tokens(obs)` — compact queue/solar/price token for message passing

### `ev_charging_grid_env/agents/`

#### `coordinator_agent.py`
- `HeuristicCoordinatorAgent` — raises prices for busy stations, lowers for solar-capable idle ones, routes emergencies to best station
- `RandomCoordinatorAgent` — random baseline
- `CoordinatorWithCommunication` — heuristic + broadcast priority flag

#### `station_agent.py`
- `HeuristicStationAgent` — prioritizes emergencies, accepts FIFO if queue short, redirects if overloaded
- `RandomStationAgent` — random baseline

#### `hierarchical_controller.py`
`HierarchicalCoordinator` — maps high-level intent (prioritize_emergency, green_mode, congestion_relief) to concrete coordinator actions. Demonstrates hierarchical control structure.

### `ev_charging_grid_env/training/`

#### `models/actor_critic.py`
Three neural network classes:
- `MLP(in, hidden, out)` — 3-layer ReLU network
- `CentralizedActorCritic` — backbone → factorized heads for price_deltas, emergency_target, station_actions, value
- `MAPPOStationPolicy` — shared actor (local obs → action logits) + critic (global obs → value)

#### `utils/preprocessing.py`
- `flatten_observation(obs) -> np.ndarray` — concatenates all dict keys into a single float32 vector
- `RunningNorm` — Welford online normalizer for stable observation scaling

#### `utils/rollout_buffer.py`
`RolloutBuffer` — stores transitions for one rollout:
- `clear()` — reset for new rollout
- `compute_returns_and_advantages(last_value)` — GAE-λ advantage estimation
- `as_arrays()` — returns numpy arrays for minibatch training

#### `utils/action_utils.py`
- `decode_joint_action(vec, n)` — converts flat int vector back to env action dict
- `build_station_action_mask(obs)` — extracts action mask from observation for masked policy

#### `algorithms/ppo_trainer.py`
`PPOTrainer` — centralized PPO for joint-action control:
1. Collects `rollout_steps` transitions using current policy
2. Computes GAE advantages
3. Runs `epochs` mini-batch updates with PPO clipping
4. Logs to TensorBoard
5. Returns training statistics

#### `algorithms/mappo_trainer.py`
`MAPPOTrainer` — multi-agent PPO on PettingZoo AEC interface:
- Shared station actor trained on all station observations
- Coordinator policy trained separately (simple MLP for emergency routing)
- Same PPO update algorithm applied to station policy buffer

#### `experiment_runner.py`
CLI tool for multi-seed training experiments:
- Loads config YAML (supports flat or nested env/training sections)
- Handles unknown config keys safely (filtered before dataclass construction)
- Saves checkpoint + result JSON per seed
- Aggregates results into summary JSON

### `ev_charging_grid_env/dashboard/`

#### `simulator.py`
`SimulationState` wrapper:
- Holds env, current observation, done flag, history list
- `step_with_policies(coordinator, stations)` — runs one step with given policies, records history
- `history_df()` — returns pandas DataFrame of episode history

`build_simulation(config, seed)` — convenience factory.
`load_default_config(path)` — loads YAML config file.

#### `policies.py`
`build_policy_bundle(name, n, checkpoint)` — factory for dashboard policy bundles:
- Returns `PolicyBundle(coordinator, stations, label, note)`
- PPO/MAPPO: uses stochastic fallback (checkpoint inference not yet wired)

#### `plots.py`
All Plotly chart functions with consistent dark theme:

| Function | Chart Type | Purpose |
|----------|-----------|---------|
| `station_map_figure(env)` | Scatter map | Live station positions, queue bubbles, vehicle markers |
| `queue_line_figure(env)` | Stacked bar | Queue + charging per station |
| `history_figures(df)` | Line charts | Reward, grid usage, travel distance over time |
| `comparison_bar(df)` | Grouped bars | Multi-metric policy comparison |
| `station_load_heatmap(env)` | Heatmap | Queue/charging/kW grid |
| `grid_utilization_gauge(used, limit)` | Gauge | Real-time grid pressure % |
| `solar_breakdown_chart(env)` | Donut | Solar vs grid energy mix |
| `emergency_timeline_chart(df)` | Area chart | Emergency served/missed over episode |
| `reward_distribution_chart(df)` | Histogram | Step reward distribution |
| `policy_radar_chart(df)` | Polar/radar | Multi-metric policy comparison |

### `ev_charging_grid_env/config/`

#### `config.yaml`
Environment hyperparameters:

```yaml
num_stations: 10          # Number of charging stations
max_slots_per_station: 4  # Charging slots per station
episode_length: 300       # Steps per episode
base_arrival_rate: 6.0    # Mean vehicles per step (Poisson λ)
grid_limit_kw: 1800.0     # City power cap
base_solar_capacity_kw: 120.0  # Solar panel rating per station
emergency_arrival_prob: 0.04   # Fraction of arrivals that are emergency
```

---

## 8. Execution Flow

### Episode Lifecycle

```
env.reset(seed)
  └── generate_task(config)        # Build station layout, distances
  └── initialize_episode(task)     # Create all StationState objects
  └── _build_observation()         # Return initial observation dict

for each step:
  action = policy.act(obs)
  env.step(action)
    ├── sample_weather(...)         # Randomly change weather
    ├── apply_coordinator_action()  # Update dynamic prices
    ├── generate_arrivals(...)      # Sample new vehicles (Poisson)
    ├── enqueue_arrivals(...)       # Place vehicles in station queues
    ├── apply_station_actions()     # Accept/redirect vehicles
    ├── progress_step(...)          # Charge vehicles, age queues, compute usage
    ├── compute_step_reward(...)    # Scalar reward
    └── _build_observation()       # Build next obs

until truncated (time_step >= episode_length)
```

### Training Loop (PPO)

```
PPOTrainer.train()
  for each update:
    collect rollout_steps transitions  →  RolloutBuffer
    compute_returns_and_advantages()   (GAE-λ)
    
    for each epoch:
      shuffle buffer
      for each mini-batch:
        forward pass model → logits, value
        compute PPO ratio, clipped loss
        optimize (Adam + grad clip)
    
    log to TensorBoard
    step LR scheduler
```

### Agent Decision Chain

```
observation dict
  ├── CoordinatorAgent.act(obs)
  │     → price_deltas (per station)
  │     → emergency_target_station
  │
  └── StationAgent.act(i, obs, coord_action)  [× num_stations]
        → 0: hold
        → 1: accept FIFO (queue head)
        → 2: accept emergency first
        → 3: redirect to another station
```

---

## 9. Simple Explanation (Beginner-Friendly)

### The Big Picture

Imagine you're managing 10 EV charging stations across a city. Every minute, electric cars show up wanting to charge. Some of them are emergencies (ambulances, etc.) that need charging RIGHT NOW.

Your job is to:
1. Decide which cars to charge at which station
2. Set prices that attract cars to stations that aren't busy
3. Use solar energy when it's sunny (it's free + green)
4. Never overload the city's power grid

This is hard because: cars arrive randomly, solar is unpredictable, and you have 10 stations with different capacities.

### Enter Reinforcement Learning

Instead of writing hand-crafted rules, we let AI agents **learn** the best strategy by trial and error:

- **The agent** tries different actions (charge this car, redirect that one, raise the price here)
- **The environment** gives a reward signal (positive for good choices like serving emergencies quickly, negative for bad choices like overloading the grid)
- **Over many episodes**, the agent learns what actions lead to more reward

This is how AlphaGo learned to play Go — by playing millions of games and getting a score at the end.

### Why Multi-Agent?

Real charging networks have many stations that need to coordinate. We train:
- One **Coordinator** to see the whole city and make high-level decisions
- Ten **Station Agents** (one per station) to handle local decisions

This mirrors how real infrastructure works: a central controller + local operators.

---

## 10. Limitations

| Limitation | Detail |
|-----------|--------|
| **PPO checkpoint inference not wired** | Dashboard uses stochastic fallback for PPO/MAPPO (full inference requires saved obs normalizer state) |
| **No persistent model across sessions** | Dashboard resets state on browser refresh |
| **Training blocks one CPU thread** | Background thread may slow dashboard responsiveness during training |
| **Simplified charging physics** | Charge rate is constant kW, no battery state-of-charge curve |
| **No real map data** | Station positions are a synthetic circular layout |
| **Single city** | No multi-city or hierarchical routing across cities |
| **No vehicle-to-grid (V2G)** | EVs only consume power, never feed back |
| **Weather is step-independent** | Weather sampled freshly each step; no persistence |
| **MAPPO coordinator is simplified** | Only learns emergency routing; price deltas are fixed to neutral |

---

## 11. Future Improvements

### Near-Term
- ✅ Wire PPO checkpoint inference into dashboard policy adapter
- Persist observation normalizer alongside checkpoint for correct inference
- Add multi-seed training comparison in the UI
- Implement proper MAPPO price-delta learning (not just routing)

### Medium-Term
- Real-time OCPP data integration (live charging station protocol)
- Vehicle-specific battery models (state-of-charge curves, different vehicle types)
- Weather persistence model (Markov chain or real forecasts)
- Geographic map background (OpenStreetMap tile overlay)

### Long-Term
- Fleet management integration (predict arrival patterns)
- Vehicle-to-grid (V2G) bidirectional charging
- Multi-city hierarchical control
- Demand response integration with utility grid
- Sim-to-real transfer to physical charging networks
