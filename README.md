---
title: EV Charging Grid Optimizer
emoji: ⚡
colorFrom: purple
colorTo: blue
sdk: docker
app_file: api/server.py
pinned: false
---

# Multi-Agent EV Charging Grid Optimizer

[![OpenEnv](https://img.shields.io/badge/OpenEnv-Compliant-brightgreen)](https://github.com/openrlbenchmark/openenv)

A sophisticated multi-agent reinforcement learning environment for optimizing EV charging grid operations with solar usage, queue balancing, emergency prioritization, and grid constraints.

## Overview

This environment simulates a coordinated EV charging network with:
- **Multiple charging stations** with queues and limited chargers
- **Solar generation** with weather-dependent variability
- **Grid capacity constraints** with overload penalties
- **Emergency vehicle routing** with priority handling
- **Price-based demand management** to balance loads
- **Deterministic task-specific grading** for fair evaluation

## Key Features

✅ OpenEnv-compliant with structured logging  
✅ 3 difficulty levels (Easy, Medium, Hard)  
✅ Normalized reward in [0,1] range  
✅ Deterministic grader with [0,1] scoring  
✅ FastAPI server with REST endpoints  
✅ Docker support for HuggingFace Spaces  
✅ Gymnasium-compatible interface  

## Installation

```bash
# Clone and install
git clone <repo>
cd meta
pip install -r requirements.txt
```

## Quick Start

### Option 1: Run Inference

```bash
python inference.py
```

### Option 2: Run API Server

```bash
python api/server.py
# Server runs on 0.0.0.0:7860
```

In another terminal:

```bash
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "medium", "seed": 42}'

curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"action": {"coordinator_action": {"price_deltas": [0,1,-1,0,0,0,0,0,0,0], "emergency_target_station": 0}, "station_actions": [1,0,1,2,1,0,1,0,1,0]}}'
```

### Option 3: Docker

```bash
docker build -t ev-charging-grid .
docker run -p 7860:7860 ev-charging-grid
```

## Environment Specification

### Observation Space

```python
{
    "station_features": np.array(shape=(10, 7), dtype=float32),  # Per-station features
    "queue_lengths": np.array(shape=(10,), dtype=int64),         # Queue lengths
    "time_context": np.array(shape=(3,), dtype=float32),         # Day time features
    "arrivals_summary": np.array(shape=(3,), dtype=float32),     # Arrival statistics
    "weather": int in [0, 1, 2]                                  # 0=sunny, 1=cloudy, 2=rainy
}
```

**Station Features** (7 values per station):
- `queue_length`: Vehicles waiting (0-500)
- `charging_vehicles`: Currently charging (0-#chargers)
- `solar_kw`: Solar generation rate (kW)
- `grid_kw`: Grid usage rate (kW)
- `price_multiplier`: Current price adjustment (0.75-1.35)
- `emergency_queue`: Emergency vehicles waiting (0-500)
- `free_chargers`: Available charging slots

**Time Context**:
- `day_fraction`: Fraction of day [0, 1]
- `sin_component`: Sine of day angle
- `cos_component`: Cosine of day angle

**Arrivals Summary**:
- `total_arrivals`: Vehicles arrived this step
- `emergency_arrivals`: Emergency vehicles
- `mean_energy_kwh`: Average energy requirement

### Action Space

```python
{
    "coordinator_action": {
        "price_deltas": list[int] of length 10,     # [-3, 3] per station
        "emergency_target_station": int in [0, 9]   # Route emergencies here
    },
    "station_actions": list[int] of length 10       # [0, 1, 2, 3] per station
}
```

**Coordinator Action**:
- `price_deltas`: Adjusts prices to manage demand (-3 to +3)
- `emergency_target_station`: Directs emergency vehicles to specified station

**Station Actions** (per station):
- `0`: Hold (no charging)
- `1`: Charge (FIFO priority)
- `2`: Charge (emergency priority)
- `3`: Redirect overflow to other stations

### Reward

**Normalized to [0, 1]** using task-specific metrics:

```
Reward = 0.4 * served_ratio
       + 0.3 * solar_usage_ratio
       + 0.3 * (1.0 - normalized_wait_time)
```

Where:
- `served_ratio`: Vehicles served / vehicles seen
- `solar_usage_ratio`: Solar energy / total energy
- `normalized_wait_time`: avg_wait / task_wait_normalizer

## Tasks

### Easy Task
- **Episode Length**: 96 steps
- **Vehicle Arrivals**: ~3.5 vehicles/step
- **Emergency Rate**: 1%
- **Solar Multiplier**: 1.15x
- **Grid Capacity**: 1750 kW
- **Objective**: >85% service ratio, <8min wait
- **Weather**: 70% sunny, 20% cloudy, 10% rainy

### Medium Task
- **Episode Length**: 120 steps
- **Vehicle Arrivals**: ~7.0 vehicles/step
- **Emergency Rate**: 5%
- **Solar Multiplier**: 0.85x
- **Grid Capacity**: 1300 kW
- **Objective**: >70% service ratio, >50% solar, <12min wait
- **Weather**: 45% sunny, 35% cloudy, 20% rainy

### Hard Task
- **Episode Length**: 144 steps
- **Vehicle Arrivals**: ~11.0 vehicles/step
- **Emergency Rate**: 12%
- **Solar Multiplier**: 0.55x
- **Grid Capacity**: 950 kW
- **Objective**: >60% service ratio, >40% solar, 95% emergency service, <16min wait
- **Weather**: 25% sunny, 35% cloudy, 40% rainy

## Metrics & Grading

### Episode Metrics

```python
{
    "task_id": str,
    "vehicles_seen": float,                     # Total vehicles arrived
    "vehicles_served": float,                   # Vehicles fully charged
    "served_ratio": float,                      # served/seen
    "solar_kwh_used": float,                    # Solar energy consumed
    "grid_kwh_used": float,                     # Grid energy consumed
    "solar_usage_ratio": float,                 # solar/(solar+grid)
    "emergency_seen": float,                    # Emergency vehicles
    "emergency_served": float,                  # Emergency vehicles served
    "emergency_missed": float,                  # Unserved emergencies
    "average_wait_time": float,                 # Mean queue wait (steps)
    "normalized_wait_time": float,              # wait / wait_normalizer
    "grid_overload": float,                     # Total overload kWh
    "grid_overload_events": int,                # Number of overload steps
    "wait_timeout_departures": int              # Vehicles leaving due to timeout
}
```

### Grading

Each task has a deterministic grader returning score ∈ [0, 1]:

**Easy**: Base score + bonuses for >85% served, >40% solar, <8min wait  
**Medium**: Base score + bonuses for >70% served, >50% solar, <12min wait, 85% emergency  
**Hard**: Base score + critical emphasis on 95% emergency service + penalties for failure  

## API Endpoints

### POST `/reset`

Reset environment to initial state.

**Request**:
```json
{
    "task_id": "medium",
    "seed": 42,
    "config": {}
}
```

**Response**:
```json
{
    "observation": {...},
    "info": {"env_name": "...", "task_id": "medium", "episode_length": 120},
    "success": true
}
```

### POST `/step`

Execute one environment step.

**Request**:
```json
{
    "action": {
        "coordinator_action": {"price_deltas": [...], "emergency_target_station": 0},
        "station_actions": [...]
    }
}
```

**Response**:
```json
{
    "observation": {...},
    "reward": 0.65,
    "terminated": false,
    "truncated": false,
    "info": {...},
    "success": true
}
```

### GET `/state`

Get current environment state.

**Response**:
```json
{
    "observation": {...},
    "success": true
}
```

### GET `/health`

Health check.

**Response**:
```json
{
    "status": "ok",
    "task_id": "medium",
    "step": 42
}
```

## Environment Variables

```bash
# API Configuration
API_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
API_KEY=your-api-key

# Simulation
TASK_ID=medium
SIMULATION_STEPS=120
RANDOM_SEED=42

# HF Spaces
HF_TOKEN=your-hf-token
```

## Example Usage

```python
from ev_charging_grid_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.agents import CoordinatorAgent, StationAgent

# Initialize environment
env = MultiAgentEVChargingGridEnv({"task_id": "medium"})
obs, info = env.reset(seed=42)

# Setup agents
coordinator = CoordinatorAgent()
station_agent = StationAgent()

# Run episode
for step in range(100):
    # Get coordinator action
    coord_action = coordinator.act(obs)
    
    # Get station actions
    station_actions = []
    for i, row in enumerate(obs["station_features"]):
        action = station_agent.act({
            "queue_length": row[0],
            "free_chargers": row[6],
            "emergency_queue": row[5]
        })
        station_actions.append(action)
    
    # Execute step
    action = {
        "coordinator_action": coord_action,
        "station_actions": station_actions
    }
    obs, reward, terminated, truncated, info = env.step(action)
    
    print(f"Step {step}: reward={reward:.4f}, score={info['score']:.4f}")
    
    if terminated or truncated:
        break

metrics = env._metrics_snapshot()
print(f"Final Score: {metrics}")
```

## Performance Characteristics

- **Minimum Hardware**: 2 vCPU, 4GB RAM
- **Typical Episode Time**: <5 seconds (96-144 steps)
- **Max Inference Time**: <20 minutes for full validation
- **Memory Usage**: ~200MB per environment instance

## What Makes It OpenEnv-Compliant

✅ **Deterministic Grader**: `grade_episode()` always returns [0, 1]  
✅ **Valid Action/Observation**: Gymnasium-compatible spaces  
✅ **Proper Reset/Step**: Returns correct tuples  
✅ **Task Definitions**: Clear objectives per difficulty  
✅ **Structured Logging**: [START], [STEP], [END] format  
✅ **Environment Variables**: API_BASE_URL, MODEL_NAME, API_KEY  
✅ **Reproducible**: Seed support throughout  
✅ **Performance**: Runs within resource limits  

## Validation

Run the inference script to validate:

```bash
export API_KEY=your-key
export API_BASE_URL=https://api.openai.com/v1
export MODEL_NAME=gpt-4o-mini
export TASK_ID=medium

python inference.py
```

Expected output:
```
[START] task=medium env=MultiAgentEVChargingGridEnv model=gpt-4o-mini
[STEP] step=0 action="..." reward=0.4523 done=False error=None
[STEP] step=1 action="..." reward=0.5124 done=False error=None
...
[END] success=True steps=120 score=0.7234 rewards=[...]
```

## Contributing

Improvements welcome! Areas:
- Better heuristic agents
- Advanced reward shaping
- Performance optimizations
- Task difficulty calibration

## License

Open source for research and hackathon use.

## References

- [OpenEnv Specification](https://github.com/openrlbenchmark/openenv)
- [Gymnasium Documentation](https://gymnasium.farama.org/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
