---
title: Multi-Agent EV Charging Grid Optimizer
emoji: ⚡
colorFrom: purple
colorTo: green
sdk: docker
app_file: app.py
pinned: false
---

# ⚡ Multi-Agent EV Charging Grid Optimizer

> **An AI-powered, multi-agent reinforcement learning environment for urban electric vehicle charging network optimization.**

![Status](https://img.shields.io/badge/Status-Production_Ready-success)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Tests](https://img.shields.io/badge/Tests-90/90_Passing-brightgreen)
![RL Framework](https://img.shields.io/badge/Core-PPO_%7C_MAPPO-purple)

This project simulates a real-time smart city charging grid where AI agents must dynamically balance vehicle queues, prioritize emergency vehicles, maximize solar energy utilization, and avoid catastrophic grid overloads.

---

## 🎯 Project Overview

EV infrastructure faces huge optimization challenges every minute: random vehicle arrivals, changing battery needs, intermittent weather-dependent solar energy, and hard grid caps. 

This repository leverages **Multi-Agent Reinforcement Learning (MARL)** to solve these dynamics in real-time. It contains:
- **A High-Performance Core Engine** built heavily on `gymnasium` and `pettingzoo`.
- **Hierarchical Agents**: A central `Coordinator` that routes traffic and sets token-prices, alongside independent `Station Agents` acting locally to minimize wait times.
- **State-of-the-Art RL Training**: Out of the box Proximal Policy Optimization (PPO) and Multi-Agent PPO (MAPPO) with built-in Generalized Advantage Estimation (GAE).
- **A Premium Web Dashboard**: A 4-tab Streamlit interface mimicking professional industrial control panels, featuring live maps, AI-detected insights, and real-time training controls.

---

## ✨ Key Features

- **Realistic Environment Dynamics**: Configurable Poisson arrival processes, fast/slow chargers, dynamic outage probabilities, and dynamic travel distances.
- **Robust Reward Architecture**: Scaled shaping capable of balancing severe queue penalties with massive completion rewards, calibrated using a Welford running norm.
- **In-Browser Training Pipeline**: Launch, monitor, and save new AI models purely via the local web app without touching python CLI scripts.
- **Advanced Plotly Visuals**: Live Scatter Maps charting the grid, Radar Benchmarks comparing heuristic models against neural networks, and live Heatmaps spanning grid load.
- **Comprehensive Test Suite**: Over 90 tests ensuring strict API adherence, numerical stability natively mitigating NaN explosions, and complex edge cases.

---

## 🚀 Quick Start

### 1. Installation

Clone the repository and install the framework (we recommend using a virtual environment).
```bash
python -m venv .venv
# Activate on Windows:
.venv\Scripts\activate
# Activate on Mac/Linux:
source .venv/bin/activate

# Install the library in editable mode
pip install -e .
```

### 2. Launch the Web Dashboard (Recommended)

The easiest way to interact with the project is via the interactive control panel.
```bash
streamlit run app.py
```
Open **http://localhost:8501** in your browser. From here you can run real-time benchmarks, test standard routing agents against RL models, and train new models in the background.

### 3. Run a Quick Python Simulation

```python
from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

# Load the realisticly scaled simulation environment
env = MultiAgentEVChargingGridEnv()
obs, _ = env.reset(seed=42)

for step in range(300):
    action = env.action_space.sample()  # Replace with trained policy
    obs, reward, terminated, truncated, info = env.step(action)
    if truncated:
        break

print(f"Total Reward: {env.episode_stats['total_reward']}")
```

---

## 📂 Project Structure

```text
├── app.py                      # Main Streamlit dashboard interface
├── pyproject.toml              # Build & dependency configuration
├── DOCUMENTATION.md            # Comprehensive Deep-Dive documentation
├── ev_charging_grid_env/
│   ├── envs/                   # Core RL engine (Gym & PettingZoo environments, logic, states)
│   ├── agents/                 # Action spaces (Coordinator & Station Agents)
│   ├── training/               # Torch training modules (PPO, MAPPO, GAE Buffers)
│   ├── dashboard/              # Plotly chart templates and UI Simulator bindings
│   └── config/                 # Default hyperparameters and grid boundary constants
└── tests/                      # Pytest suite tracking edge cases and numeric safety
```

---

## 🧠 Training Custom Agents

You can train agents via the UI (under the `Train AI` tab) or via the Command Line.

```bash
# Example: Train the centralized PPO model
python -m ev_charging_grid_env.training.experiment_runner \
  --config ev_charging_grid_env/config/config.yaml \
  --algorithm ppo \
  --seeds 42 \
  --output runs/
```

Results, checkpoints (`.pt`), and metric aggregations are automatically saved downstream.

---

## 🧪 Testing

The codebase enforces robust test-driven execution. To ensure environmental constraints aren't violated (i.e. grid limits overrun without penalty):

```bash
pytest ev_charging_grid_env/tests/ -v --tb=short
```

---

*For deeper technical details on algorithm specifics, execution flows, and system limitations, refer to the fully featured [DOCUMENTATION.md](./DOCUMENTATION.md) included in this repository.*
