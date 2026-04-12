"""Modern Streamlit dashboard for the EV charging RL system."""

from __future__ import annotations

import time
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ev_charging_grid_env.agents import CoordinatorAgent, StationAgent
from ev_charging_grid_env.config import get_task_profile
from ev_charging_grid_env.envs import MultiAgentEVChargingGridEnv
from ui.components import (
    inject_theme,
    metric_card,
    render_energy_panel,
    render_explainer,
    render_header,
    render_reward_chart,
    render_station_grid,
    render_training_preview,
    render_vehicle_flow,
)

st.set_page_config(
    page_title="EV Charging Grid Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_theme()

TASK_LABELS = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
AGENT_MODES = ("Heuristic", "Random", "RL (PPO/MAPPO demo)")
WEATHER_OPTIONS = ("dynamic", "sunny", "cloudy", "rainy")


def build_env_config(task_id: str, traffic_scale: float, emergency_scale: float, solar_scale: float, weather_mode: str) -> dict[str, Any]:
    """Map dashboard controls into environment overrides."""

    task = get_task_profile(task_id)
    return {
        "task_id": task_id,
        "arrival_lambda": max(0.5, task.arrival_lambda * traffic_scale),
        "emergency_probability": min(0.45, task.emergency_probability * emergency_scale),
        "solar_multiplier": max(0.2, task.solar_multiplier * solar_scale),
        "grid_capacity_kw": task.grid_capacity_kw,
        "weather_mode": None if weather_mode == "dynamic" else weather_mode,
    }


def sample_to_action(sample: dict[str, Any]) -> dict[str, Any]:
    """Convert a Gymnasium sampled action into plain Python types."""

    return {
        "coordinator_action": {
            "price_deltas": sample["coordinator_action"]["price_deltas"].tolist(),
            "emergency_target_station": int(sample["coordinator_action"]["emergency_target_station"]),
        },
        "station_actions": sample["station_actions"].tolist(),
    }


def build_heuristic_action(observation: dict[str, Any]) -> dict[str, Any]:
    """Use the repo's coordinator and station heuristics."""

    coordinator = CoordinatorAgent()
    station_agent = StationAgent()
    coordinator_action = coordinator.act(observation)
    station_actions: list[int] = []

    for row in observation["station_features"]:
        station_actions.append(
            station_agent.act(
                {
                    "queue_length": int(row[0]),
                    "free_chargers": int(row[6]),
                    "emergency_queue": int(row[5]),
                }
            )
        )

    return {
        "coordinator_action": coordinator_action,
        "station_actions": station_actions,
    }


def build_rl_demo_action(observation: dict[str, Any]) -> dict[str, Any]:
    """A more assertive policy-style controller for demo purposes."""

    action = build_heuristic_action(observation)
    queue_lengths = observation["queue_lengths"].tolist()
    solar_kw = observation["station_features"][:, 2].tolist()

    tuned_prices: list[int] = []
    for queue_len, solar in zip(queue_lengths, solar_kw):
        if queue_len >= 7:
            tuned_prices.append(3)
        elif solar >= max(solar_kw) * 0.85 and queue_len <= 2:
            tuned_prices.append(-2)
        else:
            tuned_prices.append(0)
    action["coordinator_action"]["price_deltas"] = tuned_prices

    station_actions: list[int] = []
    for queue_len, solar, row in zip(queue_lengths, solar_kw, observation["station_features"]):
        emergency_queue = int(row[5])
        free_chargers = int(row[6])
        if emergency_queue > 0:
            station_actions.append(2)
        elif queue_len > 8 and solar < max(10.0, max(solar_kw) * 0.45):
            station_actions.append(3)
        elif free_chargers > 0:
            station_actions.append(1)
        else:
            station_actions.append(0)
    action["station_actions"] = station_actions
    return action


def build_action(agent_mode: str, env: MultiAgentEVChargingGridEnv, observation: dict[str, Any]) -> dict[str, Any]:
    if agent_mode == "Random":
        return sample_to_action(env.action_space.sample())
    if agent_mode == "RL (PPO/MAPPO demo)":
        return build_rl_demo_action(observation)
    return build_heuristic_action(observation)


def station_payload(env: MultiAgentEVChargingGridEnv, observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Create UI-friendly station summaries."""

    payload: list[dict[str, Any]] = []
    max_station_grid = max(1.0, env._grid_capacity_kw() / env.num_stations)
    for station, row in zip(env.stations, observation["station_features"]):
        used_slots = len(station.charging)
        queue_length = len(station.queue)
        solar_kw = float(row[2])
        grid_kw = float(row[3])
        emergency_queue = int(row[5])

        if grid_kw > max_station_grid * 0.95 or queue_length >= 8:
            tone = "bad"
            status = "Overloaded"
        elif used_slots >= station.charger_count or queue_length >= 4:
            tone = "warn"
            status = "Busy"
        else:
            tone = "good"
            status = "Free"

        payload.append(
            {
                "station_id": station.station_id + 1,
                "used_slots": used_slots,
                "total_slots": station.charger_count,
                "queue_length": queue_length,
                "emergency_queue": emergency_queue,
                "solar_kw": solar_kw,
                "grid_kw": grid_kw,
                "price": float(row[4]),
                "status": status,
                "tone": tone,
            }
        )
    return payload


def build_explanations(
    env: MultiAgentEVChargingGridEnv,
    observation: dict[str, Any],
    action: dict[str, Any] | None,
    info: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    """Generate readable AI explanations from the latest action."""

    if not action or not info:
        return ["Start the simulation to see live reasoning from the coordinator and station agents."], []

    explanations: list[str] = []
    critical_notes: list[str] = []

    queue_lengths = observation["queue_lengths"].tolist()
    solar_kw = observation["station_features"][:, 2].tolist()
    price_deltas = action["coordinator_action"]["price_deltas"]
    target_station = action["coordinator_action"]["emergency_target_station"] + 1

    explanations.append(
        f"Coordinator targeted Station {target_station} for emergency intake to shorten response distance and keep high-priority vehicles moving."
    )

    for index, delta in enumerate(price_deltas):
        if delta < 0:
            explanations.append(
                f"Coordinator lowered price at Station {index + 1} -> underutilized queue ({queue_lengths[index]}) and strong solar supply ({solar_kw[index]:.1f} kW)."
            )
        elif delta > 0:
            explanations.append(
                f"Coordinator raised price at Station {index + 1} -> queue pressure is high ({queue_lengths[index]}) and demand needs to shift elsewhere."
            )

    for index, action_code in enumerate(action["station_actions"]):
        if action_code == 3:
            explanations.append(
                f"Station {index + 1} redirected vehicles -> high queue ({queue_lengths[index]}) with limited local energy headroom."
            )
        elif action_code == 2:
            explanations.append(
                f"Station {index + 1} prioritized emergencies -> urgent vehicles are waiting and should bypass normal queue order."
            )
        elif action_code == 1 and queue_lengths[index] > 0:
            explanations.append(
                f"Station {index + 1} accepted vehicles -> chargers are available and queue pressure can be reduced immediately."
            )

    metrics = info.get("episode_metrics", {})
    if metrics.get("grid_overload_events", 0.0) > 0:
        critical_notes.append(
            f"Critical: grid overload has occurred {int(metrics['grid_overload_events'])} time(s). The coordinator should shift demand toward solar-rich stations."
        )
    if metrics.get("emergency_missed", 0.0) > 0:
        critical_notes.append(
            f"Critical: {int(metrics['emergency_missed'])} emergency vehicle(s) exceeded the service target."
        )
    if metrics.get("average_wait_time", 0.0) > env.task.wait_normalizer:
        critical_notes.append(
            f"Warning: average wait time is {metrics['average_wait_time']:.1f} steps, which is above the comfort threshold for this task."
        )

    return explanations[:8], critical_notes


def history_record(env: MultiAgentEVChargingGridEnv, reward: float, info: dict[str, Any]) -> dict[str, Any]:
    """Capture a single step for charts and replay."""

    events = info.get("events", {})
    metrics = info.get("episode_metrics", {})
    return {
        "step": env.current_step,
        "reward": reward,
        "arrivals": float(events.get("arrivals", 0.0)),
        "served": float(events.get("vehicles_served", 0.0)),
        "emergencies": float(env.last_arrivals_summary[1]) if hasattr(env, "last_arrivals_summary") else 0.0,
        "avg_wait": float(events.get("avg_wait_time", 0.0)),
        "solar": float(events.get("solar_kwh_used", 0.0)),
        "grid": float(events.get("grid_kwh_used", 0.0)),
        "score": float(info.get("score", 0.0)),
        "metrics": metrics,
    }


def snapshot_payload(
    env: MultiAgentEVChargingGridEnv,
    observation: dict[str, Any],
    info: dict[str, Any] | None,
    action: dict[str, Any] | None,
    status_label: str,
    agent_mode: str,
) -> dict[str, Any]:
    metrics = info.get("episode_metrics", {}) if info else env._metrics_snapshot()
    explanations, critical_notes = build_explanations(env, observation, action, info)
    status_tone = "good"
    if status_label == "Paused":
        status_tone = "warn"
    if status_label == "Completed" or critical_notes:
        status_tone = "bad" if critical_notes else "accent"

    return {
        "task_label": TASK_LABELS.get(env.task_id, env.task_id.title()),
        "status_label": status_label,
        "status_tone": status_tone,
        "step": env.current_step,
        "agent_label": agent_mode,
        "stations": station_payload(env, observation),
        "metrics": metrics,
        "explanations": explanations,
        "critical_notes": critical_notes,
    }


def initialize_state() -> None:
    """Seed Streamlit session state once."""

    defaults = {
        "task_choice": "medium",
        "agent_mode": "Heuristic",
        "traffic_scale": 1.0,
        "emergency_scale": 1.0,
        "solar_scale": 1.0,
        "weather_mode": "dynamic",
        "refresh_interval": 0.8,
        "explain_mode": True,
        "replay_mode": False,
        "replay_index": 0,
        "training_curve": [],
        "training_labels": [],
        "running": False,
        "status_label": "Paused",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    if "env" not in st.session_state:
        reset_simulation()


def reset_simulation() -> None:
    """Create a new environment from the control panel configuration."""

    config = build_env_config(
        st.session_state.task_choice,
        st.session_state.traffic_scale,
        st.session_state.emergency_scale,
        st.session_state.solar_scale,
        st.session_state.weather_mode,
    )
    env = MultiAgentEVChargingGridEnv(config)
    observation, info = env.reset(seed=42, options=config)

    st.session_state.env = env
    st.session_state.observation = observation
    st.session_state.last_info = {
        "events": {
            "arrivals": 0.0,
            "vehicles_served": 0.0,
            "solar_kwh_used": 0.0,
            "grid_kwh_used": 0.0,
            "avg_wait_time": 0.0,
            "queue_length": 0.0,
            "grid_overload": 0.0,
            "emergency_served": 0.0,
        },
        "episode_metrics": env._metrics_snapshot(),
        "score": 0.0,
    }
    st.session_state.last_action = None
    st.session_state.history = []
    st.session_state.snapshots = [
        snapshot_payload(
            env,
            observation,
            st.session_state.last_info,
            None,
            "Paused",
            st.session_state.agent_mode,
        )
    ]
    st.session_state.replay_index = 0
    st.session_state.running = False
    st.session_state.status_label = "Paused"


def step_simulation() -> None:
    """Advance the live environment by one step and store history."""

    env: MultiAgentEVChargingGridEnv = st.session_state.env
    observation = st.session_state.observation
    action = build_action(st.session_state.agent_mode, env, observation)
    next_observation, reward, terminated, truncated, info = env.step(action)

    st.session_state.observation = next_observation
    st.session_state.last_action = action
    st.session_state.last_info = info
    st.session_state.history.append(history_record(env, reward, info))
    st.session_state.snapshots.append(
        snapshot_payload(
            env,
            next_observation,
            info,
            action,
            "Running",
            st.session_state.agent_mode,
        )
    )
    st.session_state.replay_index = len(st.session_state.snapshots) - 1

    if terminated or truncated:
        st.session_state.running = False
        st.session_state.status_label = "Completed"
    else:
        st.session_state.status_label = "Running"


def run_training_preview() -> None:
    """Generate a reward curve across a few short benchmark episodes."""

    labels: list[str] = []
    curve: list[float] = []
    config = build_env_config(
        st.session_state.task_choice,
        st.session_state.traffic_scale,
        st.session_state.emergency_scale,
        st.session_state.solar_scale,
        st.session_state.weather_mode,
    )

    for episode in range(1, 9):
        env = MultiAgentEVChargingGridEnv(config)
        observation, _ = env.reset(seed=42 + episode, options=config)
        total_reward = 0.0
        for _ in range(min(36, env.task.episode_length)):
            action = build_action(st.session_state.agent_mode, env, observation)
            observation, reward, terminated, truncated, _ = env.step(action)
            total_reward += reward
            if terminated or truncated:
                break
        labels.append(f"Ep {episode}")
        curve.append(round(total_reward, 2))

    st.session_state.training_curve = curve
    st.session_state.training_labels = labels


def current_snapshot() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Choose between live and replay state."""

    if st.session_state.replay_mode and st.session_state.snapshots:
        index = min(st.session_state.replay_index, len(st.session_state.snapshots) - 1)
        return st.session_state.snapshots[index], st.session_state.history[:index]

    snapshot = snapshot_payload(
        st.session_state.env,
        st.session_state.observation,
        st.session_state.last_info,
        st.session_state.last_action,
        st.session_state.status_label,
        st.session_state.agent_mode,
    )
    return snapshot, st.session_state.history


def render_control_panel() -> None:
    """Render controls and apply state changes."""

    st.markdown('<div class="panel-title">Control Panel</div>', unsafe_allow_html=True)
    st.selectbox("Task", options=["easy", "medium", "hard"], key="task_choice", format_func=lambda value: TASK_LABELS[value])
    st.selectbox("Agent Type", options=AGENT_MODES, key="agent_mode")

    start_col, pause_col, reset_col = st.columns(3)
    if start_col.button("Start", use_container_width=True):
        st.session_state.running = True
        st.session_state.status_label = "Running"
    if pause_col.button("Pause", use_container_width=True):
        st.session_state.running = False
        st.session_state.status_label = "Paused"
    if reset_col.button("Reset", use_container_width=True):
        reset_simulation()

    st.slider("Traffic Level", 0.5, 2.0, key="traffic_scale", step=0.1)
    st.slider("Emergency Rate", 0.5, 3.0, key="emergency_scale", step=0.1)
    st.slider("Solar Availability", 0.4, 1.8, key="solar_scale", step=0.1)
    st.selectbox("Weather", options=WEATHER_OPTIONS, key="weather_mode")
    st.slider("Refresh (sec)", 0.5, 1.0, key="refresh_interval", step=0.1)
    st.toggle("Explainable AI Mode", key="explain_mode")
    st.toggle("Replay Mode", key="replay_mode")

    if st.session_state.replay_mode and st.session_state.snapshots:
        st.slider(
            "Replay Step",
            min_value=0,
            max_value=max(0, len(st.session_state.snapshots) - 1),
            key="replay_index",
            step=1,
        )

    if st.button("Apply Controls / Reset Simulation", use_container_width=True):
        reset_simulation()

    st.markdown(
        '<div class="control-tip">Use reset after changing traffic, emergency, solar, or weather controls so the new scenario is rebuilt cleanly.</div>',
        unsafe_allow_html=True,
    )


def render_side_panels(snapshot: dict[str, Any]) -> None:
    """Render emergency and training panels in the side rail."""

    metrics = snapshot["metrics"]
    st.markdown('<div class="panel-title" style="margin-top: 1rem;">Emergency Monitor</div>', unsafe_allow_html=True)
    emergency_col1, emergency_col2 = st.columns(2)
    with emergency_col1:
        metric_card(
            "Active Emergency",
            f"{int(metrics.get('emergency_seen', 0) - metrics.get('emergency_served', 0))}",
            "Vehicles still waiting for priority service",
            "bad" if metrics.get("emergency_missed", 0.0) > 0 else "warn",
        )
    with emergency_col2:
        metric_card(
            "Missed Emergencies",
            f"{int(metrics.get('emergency_missed', 0))}",
            "Critical when non-zero",
            "bad" if metrics.get("emergency_missed", 0.0) > 0 else "good",
        )

    metric_card(
        "Emergency Service Time",
        f"{metrics.get('average_wait_time', 0.0):.1f} steps",
        "Proxy for urgency response speed",
        "warn" if metrics.get("average_wait_time", 0.0) > st.session_state.env.task.wait_normalizer else "good",
    )

    st.markdown('<div class="panel-title" style="margin-top: 1rem;">Training Panel</div>', unsafe_allow_html=True)
    if st.button("Start Training Preview", use_container_width=True):
        run_training_preview()
    render_training_preview(st.session_state.training_curve, st.session_state.training_labels)


def main() -> None:
    initialize_state()

    main_col, side_col = st.columns([3.25, 1.2], gap="large")
    with side_col:
        render_control_panel()

    if st.session_state.running and not st.session_state.replay_mode:
        step_simulation()

    snapshot, history = current_snapshot()
    render_header(snapshot)

    metric_cols = st.columns(5)
    with metric_cols[0]:
        metric_card("Total Reward", f"{sum(item['reward'] for item in history):.1f}", "Cumulative reward signal", "accent")
    with metric_cols[1]:
        metric_card("Avg Wait", f"{snapshot['metrics'].get('average_wait_time', 0.0):.1f}", "Lower is better", "warn" if snapshot["metrics"].get("average_wait_time", 0.0) > 5 else "good")
    with metric_cols[2]:
        metric_card("Vehicles Served", f"{int(snapshot['metrics'].get('vehicles_served', 0))}", "Completed charging sessions", "good")
    with metric_cols[3]:
        metric_card("Solar Utilization", f"{snapshot['metrics'].get('solar_utilization_pct', 0.0):.1f}%", "Renewable share of energy", "good")
    with metric_cols[4]:
        metric_card("Grid Overloads", f"{int(snapshot['metrics'].get('grid_overload_events', 0))}", "Critical reliability signal", "bad" if snapshot["metrics"].get("grid_overload_events", 0.0) > 0 else "good")

    with main_col:
        render_station_grid(snapshot["stations"])
        top_row = st.columns([1.45, 1.05], gap="large")
        with top_row[0]:
            render_vehicle_flow(history)
        with top_row[1]:
            render_reward_chart(history)

        bottom_row = st.columns([1.35, 1.15], gap="large")
        with bottom_row[0]:
            render_energy_panel(history, snapshot["metrics"])
        with bottom_row[1]:
            render_explainer(snapshot["explanations"], snapshot["critical_notes"], st.session_state.explain_mode)

    with side_col:
        render_side_panels(snapshot)

    if st.session_state.running and not st.session_state.replay_mode:
        time.sleep(float(st.session_state.refresh_interval))
        st.rerun()


if __name__ == "__main__":
    main()
