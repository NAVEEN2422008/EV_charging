#!/usr/bin/env python3
"""
Professional Interactive Dashboard for EV Charging Grid Optimizer
Hackathon-Grade UI with Real-Time Simulation, AI Explainability & Analytics
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from plotly.subplots import make_subplots

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
from ev_charging_grid_env.agents import CoordinatorAgent, StationAgent
from ev_charging_grid_env.graders import grade_episode

# ============================================================================
# PAGE CONFIG & STYLING
# ============================================================================

st.set_page_config(
    page_title="EV Charging Grid Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark theme CSS
st.markdown(
    """
    <style>
    :root {
        --primary: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --neutral: #6b7280;
        --light: #f3f4f6;
        --dark: #1f2937;
    }

    .metric-card {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border-left: 4px solid #10b981;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 10px;
    }

    .metric-label {
        color: #9ca3af;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }

    .metric-value {
        color: #f3f4f6;
        font-size: 2rem;
        font-weight: 700;
    }

    .status-ok {
        color: #10b981;
    }

    .status-warning {
        color: #f59e0b;
    }

    .status-danger {
        color: #ef4444;
    }

    .station-card {
        background: linear-gradient(135deg, #374151 0%, #1f2937 100%);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 4px solid #10b981;
    }

    .header-title {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

if "env" not in st.session_state:
    st.session_state.env = None
    st.session_state.observation = None
    st.session_state.info = None
    st.session_state.episode_history = {
        "steps": [],
        "rewards": [],
        "vehicles_served": [],
        "avg_wait": [],
        "solar_usage": [],
        "grid_usage": [],
    }
    st.session_state.running = False
    st.session_state.step_count = 0
    st.session_state.total_reward = 0.0

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def init_environment(task_id: str, seed: int) -> None:
    """Initialize the environment."""
    st.session_state.env = MultiAgentEVChargingGridEnv({"task_id": task_id})
    st.session_state.observation, st.session_state.info = st.session_state.env.reset(
        seed=seed
    )
    st.session_state.step_count = 0
    st.session_state.total_reward = 0.0
    st.session_state.episode_history = {
        "steps": [],
        "rewards": [],
        "vehicles_served": [],
        "avg_wait": [],
        "solar_usage": [],
        "grid_usage": [],
    }
    st.session_state.running = False


def get_station_status(station_features: list) -> str:
    """Determine station status based on features."""
    queue = station_features[0]
    charging = station_features[1]
    free_chargers = station_features[6]

    if queue > 8 or charging >= 4:
        return "danger"
    elif queue > 4 or charging >= 3:
        return "warning"
    return "ok"


def build_joint_action(observation: dict[str, Any]) -> dict[str, Any]:
    """Get action from heuristic agents."""
    coordinator = CoordinatorAgent()
    station_agent = StationAgent()

    coord_action = coordinator.act(observation)
    station_actions: list[int] = []

    station_features = observation["station_features"]
    for row in station_features:
        action = station_agent.act(
            {
                "queue_length": int(row[0]),
                "free_chargers": int(row[6]),
                "emergency_queue": int(row[5]),
            }
        )
        station_actions.append(action)

    return {
        "coordinator_action": coord_action,
        "station_actions": station_actions,
    }


def explain_decision(
    station_idx: int, action_code: int, features: list, solar_available: float
) -> str:
    """Generate explanation for station action."""
    queue = features[0]
    charging = features[1]
    solar_kw = features[2]
    price = features[4]
    emergency = features[5]
    free = features[6]

    explanations = {
        0: f"Holding: No available chargers (charging {int(charging)}/{int(charging)+int(free)})",
        1: f"Charging (FIFO): Queue {int(queue)} vehicles, solar {solar_kw:.1f}kW available",
        2: f"Emergency Priority: {int(emergency)} emergency vehicles in queue",
        3: f"Redirecting: Queue overloaded ({int(queue)} > threshold), solar low ({solar_kw:.1f}kW)",
    }

    return explanations.get(action_code, "Unknown action")


# ============================================================================
# MAIN PAGE LAYOUT
# ============================================================================

# Header
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    st.markdown(
        '<h1 class="header-title">⚡ EV Charging Grid Optimizer</h1>',
        unsafe_allow_html=True,
    )

with col2:
    task_display = st.session_state.env.task.id if st.session_state.env else "None"
    st.markdown(f"**Current Task:** `{task_display.upper()}`")

with col3:
    status_text = "▶ Running" if st.session_state.running else "⏸ Paused"
    st.markdown(f"**Status:** {status_text}")

st.divider()

# ============================================================================
# LEFT SIDEBAR - CONTROLS
# ============================================================================

with st.sidebar:
    st.markdown("### ⚙️ Simulation Controls")

    # Task selection
    task_id = st.selectbox(
        "Select Task Difficulty",
        ["easy", "medium", "hard"],
        help="Easy: low traffic | Medium: balanced | Hard: congested",
    )

    seed = st.number_input("Random Seed", value=42, min_value=0, max_value=1000)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎬 Start Simulation", use_container_width=True):
            init_environment(task_id, seed)
            st.session_state.running = True
            st.rerun()

    with col2:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.running = False
            init_environment(task_id, seed)
            st.rerun()

    st.divider()

    # Speed control
    st.markdown("### ⏱️ Simulation Speed")
    speed = st.slider(
        "Steps per update", min_value=1, max_value=10, value=1, help="Steps executed per page load"
    )

    # Update simulation
    if st.session_state.running and st.session_state.env is not None:
        for _ in range(speed):
            obs = st.session_state.observation
            action = build_joint_action(obs)
            obs, reward, terminated, truncated, info = st.session_state.env.step(action)

            st.session_state.observation = obs
            st.session_state.total_reward += reward
            st.session_state.step_count += 1
            st.session_state.episode_history["steps"].append(st.session_state.step_count)
            st.session_state.episode_history["rewards"].append(float(reward))

            if "events" in info:
                st.session_state.episode_history["vehicles_served"].append(
                    info["events"].get("vehicles_served", 0)
                )

            if "reward_components" in info:
                st.session_state.episode_history["avg_wait"].append(
                    info["reward_components"].get("avg_wait_time", 0)
                )
                st.session_state.episode_history["solar_usage"].append(
                    info["reward_components"].get("solar_kwh_used", 0)
                )
                st.session_state.episode_history["grid_usage"].append(
                    info["reward_components"].get("grid_overload", 0)
                )

            if terminated or truncated:
                st.session_state.running = False
                break

        st.rerun()

    st.divider()

    st.markdown("### 📊 Task Info")
    if st.session_state.env:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Max Steps", st.session_state.env.task.episode_length)
        with col2:
            st.metric("Current Step", st.session_state.step_count)

        st.metric("Total Reward", f"{st.session_state.total_reward:.4f}")

        if st.session_state.step_count > 0:
            mean_reward = np.mean(st.session_state.episode_history["rewards"])
            st.metric("Mean Reward/Step", f"{mean_reward:.4f}")

# ============================================================================
# MAIN CONTENT - TOP METRICS
# ============================================================================

if st.session_state.env is None:
    st.info("👈 Select a task in the sidebar to start")
else:
    # Key metrics row
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Current Reward</div>
                <div class="metric-value status-ok">{st.session_state.episode_history['rewards'][-1] if st.session_state.episode_history['rewards'] else 0:.4f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        avg_wait = (
            np.mean(st.session_state.episode_history["avg_wait"])
            if st.session_state.episode_history["avg_wait"]
            else 0
        )
        status_class = "status-ok" if avg_wait < 10 else "status-warning" if avg_wait < 15 else "status-danger"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Avg Wait Time</div>
                <div class="metric-value {status_class}">{avg_wait:.1f}s</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        total_served = (
            sum(st.session_state.episode_history["vehicles_served"])
            if st.session_state.episode_history["vehicles_served"]
            else 0
        )
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Vehicles Served</div>
                <div class="metric-value status-ok">{int(total_served)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        solar_total = (
            sum(st.session_state.episode_history["solar_usage"])
            if st.session_state.episode_history["solar_usage"]
            else 0
        )
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Solar Used</div>
                <div class="metric-value status-ok">{solar_total:.1f}kWh</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col5:
        if st.session_state.observation:
            total_queue = int(sum(st.session_state.observation["queue_lengths"]))
            status_class = "status-ok" if total_queue < 20 else "status-warning" if total_queue < 40 else "status-danger"
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">Total Queue</div>
                    <div class="metric-value {status_class}">{total_queue}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # ========================================================================
    # MAIN VISUALIZATION ROWS
    # ========================================================================

    # Row 1: Station Grid + Energy Panel
    col_stations, col_energy = st.columns([2, 1])

    with col_stations:
        st.markdown("### 🏗️ Charging Stations Status")

        station_features = st.session_state.observation["station_features"]
        queue_lengths = st.session_state.observation["queue_lengths"]

        # Create station cards in a grid
        station_cols = st.columns(5)
        for i in range(10):
            col_idx = i % 5
            features = station_features[i]

            status = get_station_status(features)
            status_emoji = {"ok": "🟢", "warning": "🟡", "danger": "🔴"}[status]
            status_color = {"ok": "#10b981", "warning": "#f59e0b", "danger": "#ef4444"}[
                status
            ]

            queue = features[0]
            charging = features[1]
            solar = features[2]
            grid = features[3]
            price = features[4]
            emergency = features[5]
            free = features[6]

            with station_cols[col_idx]:
                st.markdown(
                    f"""
                    <div style="background: #1f2937; border-left: 4px solid {status_color};
                                padding: 12px; border-radius: 6px; margin-bottom: 8px;">
                        <div style="color: #9ca3af; font-size: 0.75rem; font-weight: 600;">Station {i}</div>
                        <div style="color: #f3f4f6; font-size: 1.2rem; font-weight: 700; margin: 4px 0;">
                            {status_emoji}
                        </div>
                        <div style="font-size: 0.8rem; color: #d1d5db; line-height: 1.4;">
                            Queue: <span style="color: #f3f4f6; font-weight: 600;">{int(queue)}</span><br>
                            Charging: <span style="color: #f3f4f6; font-weight: 600;">{int(charging)}/{int(charging)+int(free)}</span><br>
                            ☀️ {solar:.1f}kW<br>
                            💵 {price:.2f}x
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with col_energy:
        st.markdown("### ⚡ Energy Balance")

        if st.session_state.episode_history["solar_usage"] and st.session_state.episode_history["grid_usage"]:
            total_solar = sum(st.session_state.episode_history["solar_usage"])
            total_grid = sum(st.session_state.episode_history["grid_usage"])

            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=["Solar", "Grid"],
                        values=[total_solar, total_grid],
                        marker=dict(colors=["#10b981", "#ef4444"]),
                        textinfo="label+percent",
                    )
                ]
            )
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Row 2: Charts
    col_reward, col_wait, col_served = st.columns(3)

    with col_reward:
        st.markdown("### 📈 Reward Trend")
        if st.session_state.episode_history["rewards"]:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    y=st.session_state.episode_history["rewards"],
                    mode="lines+markers",
                    name="Reward",
                    line=dict(color="#10b981", width=2),
                    marker=dict(size=4),
                    fill="tozeroy",
                    fillcolor="rgba(16, 185, 129, 0.1)",
                )
            )
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis_title="Step",
                yaxis_title="Reward",
                hovermode="x unified",
                template="plotly_dark",
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_wait:
        st.markdown("### ⏱️ Average Wait Time")
        if st.session_state.episode_history["avg_wait"]:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    y=st.session_state.episode_history["avg_wait"],
                    mode="lines+markers",
                    name="Wait Time",
                    line=dict(color="#f59e0b", width=2),
                    marker=dict(size=4),
                    fill="tozeroy",
                    fillcolor="rgba(245, 158, 11, 0.1)",
                )
            )
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis_title="Step",
                yaxis_title="Avg Wait (steps)",
                hovermode="x unified",
                template="plotly_dark",
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_served:
        st.markdown("### 🚗 Vehicles Served")
        if st.session_state.episode_history["vehicles_served"]:
            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    y=st.session_state.episode_history["vehicles_served"],
                    name="Served",
                    marker=dict(color="#10b981"),
                )
            )
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis_title="Step",
                yaxis_title="Vehicles",
                hovermode="x unified",
                template="plotly_dark",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Row 3: AI Explainability
    st.markdown("### 🧠 AI Decision Explainability")

    col_explainer_left, col_explainer_right = st.columns([1, 1])

    with col_explainer_left:
        st.markdown("#### Coordinator Decisions (Pricing Strategy)")

        if st.session_state.observation:
            station_features = st.session_state.observation["station_features"]

            explanations = []
            for i, features in enumerate(station_features):
                queue = features[0]
                solar = features[2]
                mean_queue = np.mean(station_features[:, 0])

                if queue > mean_queue + 2:
                    reason = (
                        f"Station {i}: 📈 HIGH QUEUE ({int(queue)}) → Increase price to reduce demand"
                    )
                elif solar > np.mean(station_features[:, 2]) and queue <= mean_queue:
                    reason = f"Station {i}: ☀️ ABUNDANT SOLAR ({solar:.1f}kW) → Lower price to attract vehicles"
                else:
                    reason = f"Station {i}: ⚖️ BALANCED → Neutral pricing"

                explanations.append(reason)

            for exp in explanations[:5]:
                st.caption(exp)

    with col_explainer_right:
        st.markdown("#### Station Actions (Queue Management)")

        if st.session_state.observation:
            station_features = st.session_state.observation["station_features"]

            for i in range(5):
                features = station_features[i]
                queue = features[0]
                emergency = features[5]
                free = features[6]

                if emergency > 0:
                    action_str = "🚨 Emergency prioritization"
                elif queue > 6 and free == 0:
                    action_str = "↔️ Redirect overflow"
                elif free > 0 and queue > 0:
                    action_str = "🔋 Queue charging"
                else:
                    action_str = "⏸ Hold"

                st.caption(f"Station {i}: {action_str}")

    st.divider()

    # Row 4: Final Stats
    st.markdown("### 📊 Episode Summary")

    if st.session_state.step_count > 0:
        metrics_data = st.session_state.env._metrics_snapshot()
        score = grade_episode(metrics_data)

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            served_ratio = metrics_data.get("served_ratio", 0) * 100
            st.metric("Service Ratio", f"{served_ratio:.1f}%")

        with col2:
            solar_ratio = metrics_data.get("solar_usage_ratio", 0) * 100
            st.metric("Solar Usage", f"{solar_ratio:.1f}%")

        with col3:
            emergency_seen = metrics_data.get("emergency_seen", 0)
            emergency_served = metrics_data.get("emergency_served", 0)
            if emergency_seen > 0:
                emergency_ratio = (emergency_served / emergency_seen) * 100
                st.metric("Emergency Service", f"{emergency_ratio:.1f}%")
            else:
                st.metric("Emergency Service", "N/A")

        with col4:
            overload_events = int(metrics_data.get("grid_overload_events", 0))
            st.metric("Grid Overloads", overload_events)

        with col5:
            st.metric("Overall Score", f"{score:.4f}", delta=None)

st.divider()

# Footer
st.markdown(
    """
    <div style='text-align: center; color: #9ca3af; font-size: 0.875rem; margin-top: 2rem;'>
        <p>🚀 Multi-Agent EV Charging Grid Optimizer | OpenEnv Compliant | Hackathon Ready</p>
    </div>
    """,
    unsafe_allow_html=True,
)
