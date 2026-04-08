# 🚀 Comprehensive Deployment Guide

**Multi-Agent EV Charging Grid Optimizer** — Production-ready deployment for local development, Docker, and cloud platforms.

---

## 📋 Table of Contents

1. [Environment Setup](#environment-setup)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [OpenEnv Validation](#openenv-validation)
5. [Training & Inference](#training--inference)
6. [Testing & CI/CD](#testing--cicd)
7. [Troubleshooting](#troubleshooting)
8. [Performance Tuning](#performance-tuning)

---

## Environment Setup

### Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Git** with GitHub & HuggingFace remotes configured
- **Docker** (optional, for containerized deployment)
- **pip** or **conda** (for package management)

### 1. Clone Repository

```bash
# GitHub
git clone https://github.com/NAVEEN2422008/EV_charging.git
cd EV_charging

# Or HuggingFace Spaces
git clone https://huggingface.co/spaces/NAVEENKUMAR24022008/EV
cd EV
```

### 2. Create Virtual Environment

```bash
# Using venv (recommended)
python -m venv .venv

# Activate:
# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install package in editable mode with all dependencies
pip install -e .

# Or manually install from requirements
pip install -r requirements.txt

# For development (includes testing tools)
pip install pytest pytest-cov pytest-mock black flake8
```

### 4. Verify Installation

```bash
# Run quick verification
python -c "
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
env = MultiAgentEVChargingGridEnv()
obs, _ = env.reset(seed=42)
print('✅ Installation successful!')
print(f'Environment has {env.num_stations} stations')
"
```

---

## Local Development

### Running the Streamlit Dashboard

The interactive dashboard is the recommended way to interact with the environment.

```bash
# Start dashboard
streamlit run app.py

# Dashboard will open at http://localhost:8501
```

**Dashboard Features:**
- **Live Ops Tab**: Real-time simulation with agent control
- **Analytics Tab**: Performance metrics and historical data
- **Compare Policies Tab**: Head-to-head agent performance
- **Training Tab**: Train new models with adjustable hyperparameters

### Running Python Scripts

#### Basic Environment Test
```python
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

env = MultiAgentEVChargingGridEnv(config={
    "num_stations": 3,
    "episode_length": 300,
    "base_arrival_rate": 6.0
})

obs, _ = env.reset(seed=42)
total_reward = 0.0

for step in range(100):
    # Random action for demo
    action = {
        "coordinator_action": {
            "price_deltas": [1] * env.num_stations,
            "emergency_target_station": 0
        },
        "station_actions": [0] * env.num_stations
    }
    
    obs, reward, terminated, truncated, info = env.step(action)
    total_reward += reward
    
    if terminated or truncated:
        break

print(f"Total Reward: {total_reward}")
print(f"Episode Stats: {env.episode_stats}")
```

#### Run Training Examples
```bash
# Train with PPO
python -m ev_charging_grid_env.examples.run_training_sweep

# Run rule-based agent
python -m ev_charging_grid_env.examples.run_rule_based_agent

# Evaluate trained agents
python -m ev_charging_grid_env.examples.evaluate_agents
```

### Debugging Tips

**Enable Verbose Output:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Check Environment State:**
```python
env = MultiAgentEVChargingGridEnv()
obs, _ = env.reset()

# Print observation structure
print("Observation keys:", obs.keys())
print("Station features shape:", obs["station_features"].shape)
print("Queue lengths:", obs["queue_lengths"])
```

**Profile Performance:**
```bash
# Using cProfile
python -m cProfile -s cumulative -m ev_charging_grid_env.examples.run_random_agent

# Using line_profiler
kernprof -l -v script.py
```

---

## Docker Deployment

### Building Docker Image

```bash
# Build image
docker build -t ev-charging-grid:latest .

# With build args
docker build -t ev-charging-grid:v1.0 \
  --build-arg PYTHON_VERSION=3.11 \
  .
```

### Running Docker Container

#### Local Development
```bash
# Mount source for live code changes
docker run -it \
  -p 8501:8501 \
  -v $(pwd):/workspace \
  ev-charging-grid:latest

# Access at http://localhost:8501
```

#### Production Mode
```bash
# Run with resource limits
docker run -d \
  --name ev-charging \
  -p 8501:8501 \
  --memory="2g" \
  --cpus="2" \
  ev-charging-grid:latest

# View logs
docker logs -f ev-charging

# Stop container
docker stop ev-charging
```

### Using Docker Compose

```bash
# Start all services
docker-compose up --build

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down

# Clean up (remove volumes)
docker-compose down -v
```

#### docker-compose.yml
```yaml
version: '3.8'

services:
  app:
    build: .
    container_name: ev-charging-grid
    ports:
      - "8501:8501"
    environment:
      - PYTHONUNBUFFERED=1
    volumes:
      - ./:/workspace
    networks:
      - ev-network

  # Optional: PostgreSQL for logging
  db:
    image: postgres:15
    container_name: ev-charging-db
    environment:
      POSTGRES_DB: ev_charging
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    networks:
      - ev-network

networks:
  ev-network:
    driver: bridge
```

---

## OpenEnv Validation

### Overview

The project includes full [OpenEnv](https://github.com/opendeep/openenv) compliance specification for benchmark standardization.

### Files

- **openenv.yaml**: Full OpenEnv specification with entrypoint, tasks, and grading config
- **inference.py**: Production inference script with LLM proxy integration
- **validate_openenv.py**: Automated compliance checker

### Running Validation

```bash
# Run OpenEnv compliance checker
python validate_openenv.py

# Expected output:
# ✅ PASS     Environment Entrypoint
# ✅ PASS     Gym API Compliance
# ✅ PASS     Inference Script
# ✅ PASS     LLM Proxy Integration
# ✅ PASS     openenv.yaml
```

### Inference via LLM Proxy

```bash
# Set environment variables for LLM proxy
export API_BASE_URL="https://your-proxy.com/v1"
export API_KEY="your-api-key"

# Run inference
python inference.py

# Output: JSON with simulation results and LLM analysis
```

**inference.py Features:**
- Runs 300-step simulation with heuristic agents
- Integrates LLM via proxy for analysis (optional)
- Returns validated JSON output
- Full error handling and graceful degradation

### OpenEnv Tasks

**Easy Task**: Basic heuristic agent operation
- Fixed pricing policy
- Simple FIFO queue management
- Deterministic agent behavior

**Medium Task**: Dynamic pricing and queue optimization
- Learn optimal price deltas
- Balance queue lengths across stations
- Maintain grid stability

**Hard Task**: Multi-objective optimization
- Maximize solar utilization
- Prioritize emergency vehicles
- Minimize grid overloads while meeting demand

---

## Training & Inference

### Training New Models

#### Via Dashboard
1. Navigate to **Training Tab**
2. Configure hyperparameters:
   - Algorithm: PPO or MAPPO
   - Learning rate: default 5e-4
   - Entropy coefficient: default 0.01
   - Batch size: default 256
3. Click "Start Training"
4. Monitor progress in real-time
5. Download trained model

#### Via CLI

```bash
# Train with configuration file
python -m ev_charging_grid_env.training.experiment_runner \
  --config ev_charging_grid_env/config/training/ppo.yaml

# Custom parameters
python -m ev_charging_grid_env.training.experiment_runner \
  --algorithm ppo \
  --learning-rate 5e-4 \
  --num-updates 500 \
  --batch-size 256
```

#### Configuration (ppo.yaml)
```yaml
algorithm: ppo
hyperparameters:
  learning_rate: 5e-4
  entropy_coef: 0.01
  value_loss_coef: 0.5
  max_grad_norm: 0.5
  clip_param: 0.2
  num_mini_batches: 4

training:
  total_timesteps: 1000000
  num_updates: 500
  batch_size: 256
  rollout_steps: 2048

checkpoint:
  save_interval: 50
  save_dir: ./checkpoints
```

### Model Inference

```python
import torch
from ev_charging_grid_env.training.models.actor_critic import ActorCriticPolicy

# Load trained model
model = ActorCriticPolicy.load("./checkpoints/model_100.pt")

# Run inference
env = MultiAgentEVChargingGridEnv()
obs, _ = env.reset()

for step in range(300):
    action = model.act(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    
    if terminated or truncated:
        break
```

### Benchmarking

```bash
# Run comprehensive benchmark
python -m ev_charging_grid_env.examples.run_training_sweep

# Compare multiple algorithms
python -c "
from ev_charging_grid_env.examples.evaluate_agents import benchmark_all
results = benchmark_all(
    algorithms=['heuristic', 'random', 'ppo', 'mappo'],
    num_episodes=50
)
print(results)
"
```

---

## Testing & CI/CD

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_env_api.py -v

# Run with coverage
pytest tests/ --cov=ev_charging_grid_env --cov-report=html

# Run OpenEnv validation tests
pytest tests/test_openenv_validation.py -v
```

### Test Structure

```
tests/
├── test_env_api.py              # Gym API compliance
├── test_pettingzoo_api.py       # PettingZoo AEC compliance
├── test_openenv_validation.py   # OpenEnv specification tests
├── test_reward_logic.py         # Reward function validation
├── test_dynamics_constraints.py # Physics and constraints
├── test_edge_cases.py           # Boundary conditions
└── test_training_sanity.py      # Training pipeline checks
```

### GitHub Actions CI/CD

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov
      
      - name: Run tests
        run: pytest tests/ --cov
      
      - name: Run OpenEnv validation
        run: python validate_openenv.py
```

---

## File Structure Reference

### Core Environment
```
ev_charging_grid_env/
├── envs/
│   ├── ev_charging_env.py          # Main Gym environment
│   ├── pettingzoo_ev_env.py        # PettingZoo AEC wrapper
│   ├── dynamics.py                 # Physics simulation
│   ├── reward_functions.py         # Reward calculations
│   └── communication.py            # Agent communication
│
├── agents/
│   ├── coordinator_agent.py        # Central coordinator
│   ├── station_agent.py            # Local station agents
│   └── hierarchical_controller.py  # Hierarchical control
│
├── training/
│   ├── algorithms/
│   │   ├── ppo_trainer.py         # PPO implementation
│   │   └── mappo_trainer.py       # MAPPO implementation
│   ├── models/
│   │   └── actor_critic.py        # Actor-critic policy
│   └── utils/
│       ├── action_utils.py
│       ├── preprocessing.py
│       └── rollout_buffer.py
│
├── dashboard/
│   ├── plots.py                    # Plotly visualizations
│   ├── policies.py                 # Policy factory
│   ├── simulator.py                # Simulation wrapper
│   └── __init__.py
│
└── examples/
    ├── run_random_agent.py
    ├── run_rule_based_agent.py
    ├── run_training_sweep.py
    └── evaluate_agents.py

app.py                               # Streamlit dashboard
inference.py                         # LLM inference with validation
validate_openenv.py                  # OpenEnv compliance checker
openenv.yaml                         # OpenEnv specification
```

---

## Troubleshooting

### Common Issues

#### ImportError: No module named 'gymnasium'
```bash
pip install gymnasium pettingzoo
```

#### CUDA/GPU Not Found
```bash
# Check GPU availability
python -c "import torch; print(torch.cuda.is_available())"

# Force CPU
export CUDA_VISIBLE_DEVICES="-1"
python script.py
```

#### Memory Issues
```bash
# Reduce batch size and simulation length
env = MultiAgentEVChargingGridEnv(config={
    "episode_length": 100,  # Reduced from 300
    "num_stations": 2       # Reduced from default
})

# Or limit container memory
docker run -m 1g app:latest
```

#### Streamlit Port Already in Use
```bash
# Use different port
streamlit run app.py --server.port 8502

# Find and kill process on port 8501
# Windows:
netstat -ano | findstr 8501
taskkill /PID <PID> /F

# macOS/Linux:
lsof -i :8501
kill -9 <PID>
```

#### PettingZoo Compatibility
The code includes a custom `AgentSelector` class for pettingzoo 1.24.3+ compatibility. If issues persist:

```python
# Check pettingzoo version
import pettingzoo
print(pettingzoo.__version__)

# Update if needed
pip install --upgrade pettingzoo
```

---

## Performance Tuning

### Environment Optimization

```python
# Use compiled observation space (faster)
config = {
    "use_compiled_spaces": True,
    "precompute_distances": True
}
env = MultiAgentEVChargingGridEnv(config=config)
```

### Training Optimization

```yaml
# In ppo.yaml for faster convergence
hyperparameters:
  learning_rate: 1e-3          # Higher LR, learn faster
  entropy_coef: 0.05           # More exploration
  clip_param: 0.3              # More aggressive clipping
  
training:
  num_mini_batches: 8          # More gradient updates per step
  rollout_steps: 4096          # Gather more experience per update
```

### Dashboard Optimization

```bash
# Streamlit caching (in config.toml)
[client]
showErrorDetails = false

[logger]
level = "warning"

[cache]
maxEntries = 1000
maxAge = 3600
```

### GPU Acceleration

```python
import torch
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

model = ActorCriticPolicy(state_dim, action_dim).to(device)
```

---

## Support & Contributing

- **Issues**: Report bugs at [GitHub Issues](https://github.com/NAVEEN2422008/EV_charging/issues)
- **Discussions**: Share ideas at [GitHub Discussions](https://github.com/NAVEEN2422008/EV_charging/discussions)
- **Contributing**: See CONTRIBUTING.md for guidelines

---

**Last Updated**: 2024-01-15  
**Maintained By**: Team  
**License**: MIT
