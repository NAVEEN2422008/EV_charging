# API_REFERENCE.md - Environment API Documentation

## Table of Contents
1. [MultiAgentEVChargingGridEnv](#multiagentevcharginggridenv)
2. [Action Space](#action-space)
3. [Observation Space](#observation-space)
4. [Reward Function](#reward-function)
5. [Episode Info](#episode-info)
6. [PettingZoo Wrapper](#pettingzoo-wrapper)
7. [Configuration Parameters](#configuration-parameters)

---

## MultiAgentEVChargingGridEnv

### Class Definition

```python
from gymnasium import Env

class MultiAgentEVChargingGridEnv(Env):
    """Centralized multi-agent EV charging grid environment.
    
    A gymnasium-compatible environment for optimizing vehicle charging
    across a network of stations with renewable energy constraints.
    """
```

### Constructor

```python
def __init__(self, config: dict[str, Any] | None = None):
    """Initialize the environment.
    
    Args:
        config: Optional configuration dictionary. See Configuration Parameters.
                If None, uses defaults from openenv.yaml
    
    Attributes:
        num_stations: Number of charging stations (int)
        episode_state: Current episode state (EpisodeState)
        observation_space: Space of observations (gymnasium.spaces.Dict)
        action_space: Space of actions (gymnasium.spaces.Dict)
    """
```

### Methods

#### reset()

```python
def reset(
    seed: int | None = None,
    options: dict[str, Any] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reset environment to initial state.
    
    Args:
        seed: Random seed for reproducibility
        options: Optional configuration overrides for this episode
    
    Returns:
        observation: Initial observation dict
        info: Info dict with episode metadata
    
    Example:
        >>> env = MultiAgentEVChargingGridEnv()
        >>> obs, info = env.reset(seed=42)
        >>> print(obs.keys())
        dict_keys(['station_features', 'queue_lengths', 'time_context', 'weather', 'arrivals_summary'])
    """
```

#### step()

```python
def step(
    action: dict[str, Any]
) -> tuple[
    dict[str, Any],  # observation
    float,           # reward
    bool,            # terminated
    bool,            # truncated
    dict[str, Any]   # info
]:
    """Execute one step of the environment.
    
    Args:
        action: Action dict with structure:
            {
                "coordinator_action": {
                    "price_deltas": array of int64[num_stations],
                    "emergency_target_station": int in [0, num_stations]
                },
                "station_actions": array of int64[num_stations]
                    where each element in {0, 1, 2, 3}
            }
    
    Returns:
        observation: Next observation dict
        reward: Scalar reward (float)
        terminated: Whether episode ended (episode reached max length)
        truncated: Whether episode was truncated (custom termination)
        info: Dict with episode statistics and event details
    
    Raises:
        TypeError: If action is not a dict
        ValueError: If action structure is invalid
    
    Example:
        >>> obs, _ = env.reset()
        >>> action = {
        ...     "coordinator_action": {
        ...         "price_deltas": [1, 1],
        ...         "emergency_target_station": 0
        ...     },
        ...     "station_actions": [1, 0]
        ... }
        >>> obs, reward, terminated, truncated, info = env.step(action)
        >>> print(f"Reward: {reward:.2f}, Done: {terminated or truncated}")
    """
```

#### render()

```python
def render(mode: str = "human") -> None:
    """Render the environment (if supported).
    
    Current implementation: No-op (visualization via Streamlit dashboard)
    """
```

---

## Action Space

### Structure

```python
@property
def action_space(self) -> gymnasium.spaces.Dict:
    """Returns the action space.
    
    Returns a gymnasium Dict space with two sub-spaces:
    """
```

### Coordinator Action

```python
"coordinator_action": Dict({
    "price_deltas": Box(
        shape=(num_stations,),
        dtype=int64,
        low=-10,      # Max price decrease ($0.10/kWh)
        high=10       # Max price increase ($0.10/kWh)
    ),
    "emergency_target_station": Discrete(num_stations + 1)
})
```

**Purpose**: Centralized coordination for:
- Dynamic pricing (influence vehicle routing)
- Emergency routing (direct EVs needing quick charge)

**Examples**:
```python
# Increase prices at station 0 by $0.05, keep station 1 same
price_deltas = [5, 0]

# Direct emergencies to station 1
emergency_target_station = 1
```

### Station Actions

```python
"station_actions": Box(
    shape=(num_stations,),
    dtype=int64,
    low=0,
    high=3
)
```

**Action Meanings** (per station):
- `0`: **HOLD** - Don't accept vehicles, wait
- `1`: **ACCEPT_FIFO** - Accept next vehicle (first-in-first-out)
- `2`: **ACCEPT_EMERGENCY** - Prioritize emergency vehicles
- `3`: **REDIRECT** - Send vehicles to other stations

**Example**:
```python
station_actions = [1, 2]  # Station 0: normal queue, Station 1: emergency priority
```

---

## Observation Space

### Structure

```python
observation_space: gymnasi.spaces.Dict({
    "station_features": Box(shape=(num_stations, 7), dtype=float32),
    "arrivals_summary": Box(shape=(3,), dtype=float32),
    "queue_lengths": Box(shape=(num_stations,), dtype=int64),
    "time_context": Box(shape=(2,), dtype=float32),
    "weather": Discrete(3)
})
```

### Station Features

```python
"station_features": array of shape (num_stations, 7)

Each row: [
    queue_length,        # Vehicles waiting (int → float)
    charging_vehicles,   # Vehicles currently charging (int → float)
    avg_wait_time,       # Average wait time in queue (minutes, float)
    has_solar,           # 1.0 if solar available, 0.0 otherwise (bool → float)
    solar_actual_kw,     # Current solar generation capacity (float)
    grid_remaining_kw,   # Remaining grid capacity (float)
    dynamic_price        # Current price per kWh (float, $)
]
```

**Example**:
```python
station_features = np.array([
    [3, 2, 12.5, 1.0, 85.0, 500.0, 0.25],  # Station 0
    [5, 1, 18.2, 0.0, 0.0, 400.0, 0.28]    # Station 1
])
```

### Arrivals Summary

```python
"arrivals_summary": [
    normal_vehicles,     # Number of regular EVs arrived this step (float)
    emergency_vehicles,  # Number of emergency EVs arrived this step (float)
    total_required_kwh   # Total battery capacity needed this step (float)
]
```

### Queue Lengths

```python
"queue_lengths": [queue_at_station_0, queue_at_station_1, ...]
```

Integer array of vehicles waiting at each station.

### Time Context

```python
"time_context": [sin(hour), cos(hour)]
```

Cyclic encoding of time-of-day (0-24h):
- `sin(2π * hour / 24)` - Sine component
- `cos(2π * hour / 24)` - Cosine component

Enables agent to learn time-dependent policies (e.g., peak pricing at 6pm).

### Weather

```python
"weather": int in {0, 1, 2}

0: sunny   → 100% solar capacity
1: cloudy  → 30% solar capacity
2: rainy   → 5% solar capacity
```

---

## Reward Function

### Computation

```python
def compute_step_reward(reward_state, events, config) -> float:
    """Multi-objective reward combining:
    - Vehicle service (vehicles charged)
    - Solar utilization (renewable energy used)
    - Emergency priority (EV battery emergency handled)
    - Grid management (avoid overload)
    - Efficiency (minimize wait time)
    """
```

### Components

| Component | Weight | Range | Meaning |
|-----------|--------|-------|---------|
| Vehicles Served | +2.0 | [0, 30] | Reward for charging vehicles |
| Solar Used | +0.5 | [0, 100] | Prefer renewable energy |
| Emergencies Served | +5.0 | [0, 5] | High priority for low-battery EVs |
| Efficiency (Wait) | -0.5 | [-100, 0] | Penalize long waits |
| Queue Buildup | -0.1 | [-50, 0] | Penalize growing queues |
| Grid Overload | -2.0 | [-10, 0] | Penalize exceeding grid capacity |

### Formula

```python
reward = (
    2.0 * vehicles_served +
    0.5 * solar_energy_used_pct +
    5.0 * emergency_vehicles_served +
    (-0.5) * (mean_wait_time / 100) +
    (-0.1) * (total_queue_vehicles / 100) +
    (-2.0) * grid_overload_events
)

# Normalize to reasonable scale
reward = reward / 10.0
```

### Typical Range

- **Min**: ~-3 per step (everything goes wrong)
- **Typical**: 0-5 per step (mixed results)
- **Max**: ~20+ per step (optimal operation)
- **Episode Total** (300 steps): ~0-6000

---

## Episode Info

### Info Dict Structure

```python
info = {
    "events": {
        "vehicles_served": int,
        "emergency_served": int,
        "emergency_missed": int,
        "solar_kwh_used": float,
        "grid_kwh_used": float,
        "mean_wait_time": float,
        "grid_exceeded": bool
    },
    "episode_stats": {
        "vehicles_seen": float,
        "total_wait_time": float,
        "solar_energy_kwh": float,
        "total_energy_kwh": float,
        "emergency_served": float,
        "emergency_missed": float,
        "total_reward": float,
        "grid_overload_events": float
    },
    "reward_components": {
        "mean_wait_time": float,
        "total_grid_kw_used": float,
        "grid_limit_kw": float
    },
    "reward_clipped": bool,  # Set if reward was clamped for stability
    "station_X_cleaned": bool  # Set if observation had NaN/Inf cleaned
}
```

### Usage Example

```python
obs, reward, terminated, truncated, info = env.step(action)

# Access current step events
events = info["events"]
print(f"Served: {events['vehicles_served']}, Emergency: {events['emergency_served']}")

# Check cumulative episode stats
stats = info["episode_stats"]
print(f"Avg wait: {stats['total_wait_time'] / stats['vehicles_seen']:.1f} min")

# Monitor numerical safety
if info.get("reward_clipped"):
    print("⚠️ Reward was clipped for stability")
```

---

## PettingZoo Wrapper

### Usage

```python
from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv

env = PettingZooEVChargingEnv()
obs_dict = env.reset(seed=42)

# AEC API: one agent acts at a time
for _ in range(300):
    agent = env.agent_selection
    obs = env.observe(agent)
    action = env.action_space(agent).sample()
    env.step(action)
    if all(env.terminations.values()) or all(env.truncations.values()):
        break
```

### Key Differences from Gym Version

| Aspect | Gym | AEC (PettingZoo) |
|--------|-----|------------------|
| Action Space | Single global action | Per-agent actions |
| Reset Return | `(obs, info)` tuple | `{agent: obs}` dict |
| Agents Available | All together | Sequential (agent_selection) |
| Use Case | Centralized training | Decentralized execution |

### Agents

```python
env.possible_agents = ["coordinator", "station_0", "station_1", ...]
env.agents  # Currently active agents
env.agent_selection  # Current agent's turn
```

---

## Configuration Parameters

### Full Parameter List

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `base_arrival_rate` | float | 6.0 | [1, 20] | Vehicles/timestep |
| `emergency_arrival_prob` | float | 0.04 | [0, 0.1] | Probability each arrival is emergency |
| `episode_length` | int | 300 | [100, 1000] | Steps per episode |
| `num_stations` | int | 2 | [1, 10] | Number of charging stations |
| `station_chargers_per_station` | int | 4 | [1, 10] | Chargers per station |
| `base_solar_capacity_kw` | float | 120.0 | [50, 500] | Max solar generation |
| `grid_limit_kw` | float | 1800.0 | [500, 5000] | Grid power cap |
| `min_battery_needed_kwh` | float | 10.0 | [1, 20] | Min charge for emergency |
| `max_battery_capacity_kwh` | float | 100.0 | [50, 200] | Vehicle battery size |
| `charger_power_kw` | float | 7.0 | [5, 50] | Charger power output |
| `price_step` | float | 0.02 | [0.01, 0.10] | Price delta per step |
| `min_price_per_kwh` | float | 0.1 | [0.05, 0.5] | Floor price |
| `max_price_per_kwh` | float | 1.0 | [0.5, 2.0] | Ceiling price |

### Usage Example

```python
config = {
    "base_arrival_rate": 10.0,         # Busier station
    "emergency_arrival_prob": 0.06,    # More emergencies
    "episode_length": 500,             # Longer episodes
    "num_stations": 5,                 # More stations
    "grid_limit_kw": 2500.0            # Higher capacity
}

env = MultiAgentEVChargingGridEnv(config=config)
obs, _ = env.reset()
```

---

## Helper Functions

### Get Action Space Sample

```python
action = env.action_space.sample()
# Returns valid random action dict
```

### Get Observation Space Sample

```python
# Get format without values
sample_obs = env.observation_space.sample()
```

### Check if Environment is Done

```python
done = terminated or truncated

if done:
    obs, _ = env.reset()  # Start new episode
    total_episodes += 1
```

---

## Examples

### Minimal Training Loop

```python
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

env = MultiAgentEVChargingGridEnv()

for episode in range(10):
    obs, _ = env.reset(seed=42)
    total_reward = 0
    
    for step in range(300):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        
        if terminated or truncated:
            break
    
    print(f"Episode {episode}: reward={total_reward:.2f}")
```

### Using Info Dict

```python
obs, _ = env.reset()

for _ in range(100):
    action = env.action_space.sample()
    obs, reward, terminated, truncated, info = env.step(action)
    
    # Access events
    events = info["events"]
    if events["grid_exceeded"]:
        print("⚠️ Grid exceeded capacity!")
    
    # Access stats
    stats = info["episode_stats"]
    solar_pct = 100 * stats["solar_energy_kwh"] / stats["total_energy_kwh"]
    print(f"Solar utilization: {solar_pct:.1f}%")
```

---

**Next**: Check [ARCHITECTURE.md](ARCHITECTURE.md) for system design details.
