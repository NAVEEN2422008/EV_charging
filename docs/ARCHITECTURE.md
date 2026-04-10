# ARCHITECTURE.md - System Design & Components

## Overview Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    MULTI-AGENT EV CHARGING OPTIMIZER            │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                           │
├──────────────────────────────────────────────────────────────────┤
│ • Streamlit Dashboard (Web UI)                                   │
│ • Python API (Gymnasium-compatible)                              │
│ • PettingZoo Wrapper (Multi-agent training)                      │
│ • CLI Tools (Training scripts, evaluation)                       │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                           │
├──────────────────────────────────────────────────────────────────┤
│ • Inference Script (inference.py)                                │
│ • Validation Framework (validate_openenv.py)                     │
│ • Environment Manager                                            │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                      CORE ENVIRONMENT                            │
│                (ev_charging_grid_env/envs/)                      │
├──────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ MultiAgentEVChargingGridEnv (Main Gym Interface)          │  │
│ │ • reset() → observations                                   │  │
│ │ • step() → next state + reward                             │  │
│ │ • Numerical safety checks                                  │  │
│ └────────────────────────────────────────────────────────────┘  │
│                              ↓                                   │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ SIMULATION ENGINE                                          │  │
│ ├────────────────────────────────────────────────────────────┤  │
│ │ • Dynamics (state transitions)                             │  │
│ │ • Vehicle arrival generation                               │  │
│ │ • Charging simulation                                       │  │
│ │ • Grid physics                                              │  │
│ │ • Weather sampling                                          │  │
│ └────────────────────────────────────────────────────────────┘  │
│                              ↓                                   │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ REWARD COMPUTATION                                         │  │
│ │ • Multi-objective optimization                             │  │
│ │ • Solar utilization tracking                               │  │
│ │ • Emergency priority handling                              │  │
│ │ • Grid load management                                     │  │
│ └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                     TRAINING LAYER                               │
│            (ev_charging_grid_env/training/)                      │
├──────────────────────────────────────────────────────────────────┤
│ • PPO Trainer                                                    │
│ • MAPPO Trainer (Multi-agent)                                    │
│ • Rollout Buffer                                                 │
│ • Model Checkpoint Manager                                       │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                   DASHBOARD & MONITORING                         │
│                      (Streamlit)                                 │
├──────────────────────────────────────────────────────────────────┤
│ • Real-time visualization                                         │
│ • Performance metrics                                             │
│ • Training progress                                               │
│ • Policy comparison                                               │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Environment Core

#### Main Gym Environment
**File**: `ev_charging_grid_env/envs/ev_charging_env.py`

```python
class MultiAgentEVChargingGridEnv(gym.Env):
    def __init__(self, config: dict = None)
    def reset(seed: int = None) -> (dict, dict)
    def step(action: dict) -> (dict, float, bool, bool, dict)
    def _build_observation() -> dict
    def _mean_wait() -> float
```

**Responsibilities**:
- State management
- Action validation
- Reward computation
- Episode statistics tracking
- Numerical safety checks

#### Simulation Engine Components

**Dynamics** (`dynamics.py`):
```
initialize_episode()      # Create initial state
generate_arrivals()       # Sample new vehicles
enqueue_arrivals()        # Add to station queues
apply_coordinator_action() # Update prices, routing
apply_station_actions()   # Station-level decisions
progress_step()           # Time advance + charging
```

**State Objects** (`state.py`):
```
Vehicle: battery_level, wait_time, is_emergency
Station: queue, charging_vehicles, chargers, solar
Grid: power_usage, overload_count, dynamic_price
EpisodeState: stations, grid, time_step
```

**Spaces** (`spaces.py`):
```
build_observation_space()  # Defines obs structure
build_action_space()       # Defines action structure
build_station_observation_space()  # AEC wrapper needs per-agent obs
```

**Reward Functions** (`reward_functions.py`):
```
compute_step_reward():
  - Vehicle service reward
  - Solar preference bonus
  - Emergency priority bonus
  - Wait time penalty
  - Grid load penalty
```

**Task Generator** (`task_generator.py`):
```
TaskConfig: Difficulty levels, parameters
generate_task(): Create episode configuration
```

### 2. Agent Layer

#### Agents
**File**: `ev_charging_grid_env/agents/`

```
HeuristicCoordinatorAgent:
  - Fixed rule-based pricing
  - Static emergency routing
  
HeuristicStationAgent:
  - FIFO queue management
  - Local charging decisions
```

**Usage**: Baseline for comparison with learned policies

#### Communication
**File**: `ev_charging_grid_env/envs/communication.py`

```
coordinator_broadcast(): Send coord decisions to stations
```

Handles multi-agent information flow.

### 3. Training Layer

#### PPO Trainer
**File**: `ev_charging_grid_env/training/algorithms/ppo_trainer.py`

```python
class PPOTrainer:
    def __init__(self, config: dict)
    def train(total_timesteps: int)
    def evaluate(num_episodes: int) -> list[float]
    def save_checkpoint(path: str)
    def load_checkpoint(path: str)
```

**Algorithm**:
- Rollout collection (n_steps per batch)
- Advantage computation (GAE)
- Policy gradient updates (clipped surrogate loss)
- Value function optimization

**Key Parameters**:
- `n_steps`: 2048 (rollout length)
- `batch_size`: 64
- `n_epochs`: 10
- `lr`: 3e-4
- `gamma`: 0.99

#### MAPPO Trainer
**File**: `ev_charging_grid_env/training/algorithms/mappo_trainer.py`

**Multi-Agent Variant**:
- Centralized training (shared experience buffer)
- Decentralized execution (per-agent policies)
- Shared value function
- Independent policy networks

#### Model Architecture
**File**: `ev_charging_grid_env/training/models/actor_critic.py`

```python
class ActorCritic(nn.Module):
    def __init__(self, obs_size, action_size)
    def forward(obs) -> (action_logits, value)
```

**Architecture**:
- Actor: 2-layer MLP → action distribution
- Critic: 2-layer MLP → scalar value estimate
- Shared feature extraction

#### Rollout Buffer
**File**: `ev_charging_grid_env/training/utils/rollout_buffer.py`

```python
class RolloutBuffer:
    def add()
    def get_batches()
    def reset()
```

Stores transitions for batch updates.

### 4. Experiment Management

#### Experiment Runner
**File**: `ev_charging_grid_env/training/experiment_runner.py`

```
run_training():
  - Create environment(s)
  - Initialize trainer
  - Collect rollouts
  - Update policy
  - Save checkpoints
  - Log metrics
```

#### Dataset Logger
**File**: `ev_charging_grid_env/simulation/dataset_logger.py`

```
EpisodeLogger:
  - Record states
  - Record actions
  - Record rewards
  - Save as pickle/HDF5
```

For offline analysis and model training.

#### Episode Runner
**File**: `ev_charging_grid_env/simulation/episode_runner.py`

```
run_episode():
  - Initialize environment
  - Execute steps with policy
  - Collect transitions
  - Return trajectory
```

### 5. Dashboard & Visualization

#### Streamlit App
**File**: `app.py`

```
run_simulator():
  - Initialize environment
  - Execute steps
  - Render charts
  - Track metrics

build_policy_bundle():
  - Load trained models
  - Prepare for comparison

UI Tabs:
  - Live Ops: Control + real-time
  - Analytics: Deep dive metrics
  - Compare: Policy comparison
  - Train AI: Train new models
```

#### Plotting Module
**File**: `ev_charging_grid_env/dashboard/plots.py`

```
station_map_figure()        # Station topology
queue_line_figure()         # Queue history
solar_breakdown_chart()     # Energy mix
grid_utilization_gauge()    # Power usage
emergency_timeline_chart()  # Emergency events
station_load_heatmap()      # Load by station/time
policy_radar_chart()        # Multi-objective scores
reward_distribution_chart() # Reward histogram
```

### 6. Validation Framework

#### Core Validation Script
**File**: `validate_openenv.py`

```
Checks:
  1. Environment entrypoint importable
  2. Gym API compliance (reset/step signatures)
  3. PettingZoo AEC wrapper works
  4. Inference script runs
  5. LLM proxy integration correct
  6. openenv.yaml valid
```

#### Test Suite
**File**: `tests/test_openenv_validation.py`

```
20+ tests covering:
  - API compliance
  - Determinism
  - Edge cases
  - JSON output
  - LLM integration
```

**File**: `tests/test_stability_and_robustness.py` (NEW)

```
25+ tests covering:
  - Numerical stability (no NaN/Inf)
  - Reward bounds
  - Observation validity
  - Multi-step execution
  - Determinism with seeds
  - Early termination
```

### 7. Configuration & Specification

#### OpenEnv Specification
**File**: `openenv.yaml`

```yaml
name: ev-charging-grid-env
version: 0.1.0
entrypoint: ev_charging_grid_env.envs.ev_charging_env:MultiAgentEVChargingGridEnv
gym_api_version: "0.26"

tasks:
  easy:   # Basic scenario
  medium: # Dynamic pricing
  hard:   # Full optimization

config:
  base_arrival_rate: 6.0
  num_stations: 2
  episode_length: 300
  ...
```

#### Inference Script
**File**: `inference.py`

```python
run_simulation()       # Execute 300-step sim
setup_llm_client()     # Configure OpenAI proxy
call_llm_analyze()     # Generate LLM insights
run()                  # Main entry point
```

**Features**:
- LLM proxy integration (API_BASE_URL, API_KEY)
- Graceful error handling
- JSON output for validation

---

## Data Flow

### Episode Execution

```
1. reset()
   ├─ Initialize state
   ├─ Sample initial arrivals
   └─ Return first observation

2. For each step:
   ├─ Agent receives observation
   ├─ Agent selects action
   ├─ step(action)
   │  ├─ Validate action
   │  ├─ Apply dynamics
   │  ├─ Generate arrivals
   │  ├─ Progress charging
   │  ├─ Compute reward
   │  └─ Check termination
   ├─ Agent receives (obs, reward, done, info)
   └─ Update cumulative stats

3. Episode ends when:
   ├─ time_step >= episode_length, OR
   ├─ Manual termination
   └─ Return episode_stats
```

### Training Loop (PPO)

```
1. Initialize environment & policy
2. For each training step:
   ├─ Rollout phase (n_steps):
   │  ├─ For each step:
   │  │  ├─ Get observation
   │  │  ├─ Policy forward pass → action
   │  │  ├─ Environment step → reward
   │  │  └─ Store (s, a, r, s', v)
   │  └─ Compute advantages (GAE)
   ├─ Update phase (n_epochs):
   │  ├─ Shuffle data into mini-batches
   │  └─ For each batch:
   │     ├─ Compute loss
   │     ├─ Backward pass
   │     └─ Update weights
   ├─ Log metrics (reward curve, loss)
   └─ Checkpoint if improved
```

### Dashboard Refresh

```
1. User clicks "Start" button
2. Environment created
3. For each display update (100ms):
   ├─ Execute 1-5 steps
   ├─ Collect observations & rewards
   ├─ Update metric cards
   ├─ Refresh charts
   └─ Render in browser
```

---

## Key Design Decisions

### 1. Centralized Environment, Decentralized Agents

**Decision**: Single environment instance, multiple agents act per step.

**Rationale**:
- Cleaner observation (global state for coordinator)
- Easier debugging
- Standard Gym API
- Can wrap with AEC for AML research

### 2. Dictionary-Based Observations

**Decision**: `dict` instead of flat `ndarray`.

**Rationale**:
- Self-documenting structure
- Easy to extend with new features
- Compatible with multi-agent APIs
- Reduces dimension explosion

### 3. Multi-Objective Reward

**Decision**: Single scalar combining 6 objectives.

**Rationale**:
- Simplified RL (single signal to optimize)
- Tunable weights for different priorities
- Easy to interpret
- Proven effective in simulations

### 4. Numerical Safety Layer

**Decision**: Detection and clamping of NaN/Inf.

**Rationale**:
- Prevents silent failures in production
- Logged in info dict for debugging
- Zero performance overhead
- Production-grade robustness

### 5. OpenEnv Compliance

**Decision**: Full Gymnasium API + OpenEnv spec.

**Rationale**:
- Interoperability with standard RL libraries
- Clear documentation
- Validation framework included
- Future-proof

---

## File Organization

```
ev_charging_grid_env/
├── __init__.py
├── agents/                    # Agent implementations
│   ├── coordinator_agent.py
│   └── station_agent.py
├── config/
│   ├── config.yaml           # Default config
│   └── training/
│       ├── ppo.yaml
│       └── mappo.yaml
├── dashboard/                 # UI components
│   ├── plots.py
│   ├── policies.py
│   └── simulator.py
├── envs/                      # Core environment
│   ├── ev_charging_env.py     # Main Gym env
│   ├── pettingzoo_ev_env.py   # AEC wrapper
│   ├── dynamics.py
│   ├── state.py
│   ├── spaces.py
│   ├── reward_functions.py
│   ├── task_generator.py
│   └── communication.py
├── examples/                  # Usage examples
│   ├── run_random_agent.py
│   ├── run_rule_based_agent.py
│   ├── evaluate_agents.py
│   └── run_training_sweep.py
├── simulation/
│   ├── curriculum.py
│   ├── dataset_logger.py
│   ├── episode_runner.py
│   └── visualization.py
├── training/                  # Training infrastructure
│   ├── experiment_runner.py
│   ├── algorithms/
│   │   ├── ppo_trainer.py
│   │   └── mappo_trainer.py
│   ├── models/
│   │   └── actor_critic.py
│   └── utils/
│       ├── action_utils.py
│       ├── preprocessing.py
│       └── rollout_buffer.py
└── tests/
    ├── test_env_api.py
    ├── test_openenv_validation.py
    └── test_stability_and_robustness.py

Root files:
├── app.py                     # Streamlit dashboard
├── inference.py               # OpenEnv entrypoint
├── validate_openenv.py        # Validation runner
├── openenv.yaml               # OpenEnv spec
├── requirements.txt
├── Dockerfile
├── QUICKSTART.md              # 5-min setup
├── USAGE_GUIDE.md             # Complete operations
├── API_REFERENCE.md           # Environment API
├── ARCHITECTURE.md            # This file
└── COMPREHENSIVE_OPENENV_AUDIT.md  # Full audit
```

---

## Testing Strategy

### Unit Tests
- Environment API (reset, step)
- Reward computation
- Space validity
- Agent behavior

### Integration Tests
- Full episode execution
- Multi-step stability
- Determinism with seeds
- Error handling

### Validation Tests
- OpenEnv specification compliance
- LLM proxy integration
- Inference script execution
- Docker containerization

### Stability Tests
- 1000-step runs without NaN/Inf
- Observation validity
- Reward bounds
- Edge cases

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Time per step | ~5-10ms |
| Episode (300 steps) | ~1.5-3 seconds |
| Training throughput (PPO) | ~10k steps/min with 4 envs |
| Memory per env | ~50MB |
| Model size (small) | ~2MB |
| Dashboard latency | <100ms |

---

**Next**: Read [API_REFERENCE.md](API_REFERENCE.md) for detailed method signatures.
