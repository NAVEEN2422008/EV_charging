"""Premium Streamlit dashboard for Multi-Agent EV Charging Grid Optimizer.

Tabs:
  Live Ops   — Real-time simulation controls, station map, metrics, charts
  Analytics  — Deep analytics: solar breakdown, emergency timeline, distributions
  Compare    — Policy comparison: Heuristic vs Random vs PPO vs MAPPO
  Train AI   — Launch PPO / MAPPO training run directly from the browser
"""

from __future__ import annotations

import io
import json
import tempfile
import time
import threading
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from ev_charging_grid_env.dashboard.plots import (
    comparison_bar,
    emergency_timeline_chart,
    grid_utilization_gauge,
    history_figures,
    policy_radar_chart,
    queue_line_figure,
    reward_distribution_chart,
    solar_breakdown_chart,
    station_load_heatmap,
    station_map_figure,
)
from ev_charging_grid_env.dashboard.policies import build_policy_bundle
from ev_charging_grid_env.dashboard.simulator import build_simulation, load_default_config

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EV Grid AI Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# PREMIUM CSS
# ──────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap');

    /* ── Base ── */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp {
        background: radial-gradient(ellipse at 10% 0%, #091828 0%, #060c14 55%, #020408 100%);
        color: #c9d8e8;
    }

    /* ── Animated gradient title ── */
    .main-title {
        background: linear-gradient(135deg, #00C2FF 0%, #00D084 40%, #7C4DFF 80%, #00C2FF 100%);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.5rem;
        font-weight: 900;
        letter-spacing: -1px;
        line-height: 1.1;
        animation: grad 6s ease-in-out infinite;
        margin-bottom: 0.15rem;
    }
    @keyframes grad {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .main-subtitle {
        color: #6b8ba4;
        font-size: 0.95rem;
        font-weight: 400;
        margin-bottom: 1.4rem;
        letter-spacing: 0.2px;
    }

    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg,
            rgba(0,194,255,0.07) 0%,
            rgba(124,77,255,0.04) 100%);
        border: 1px solid rgba(0,194,255,0.18);
        border-radius: 14px;
        padding: 14px 16px;
        backdrop-filter: blur(8px);
        transition: border-color 0.3s, box-shadow 0.3s, transform 0.2s;
    }
    [data-testid="stMetric"]:hover {
        border-color: rgba(0,194,255,0.45);
        box-shadow: 0 0 20px rgba(0,194,255,0.12);
        transform: translateY(-2px);
    }
    [data-testid="stMetricLabel"] { color: #6b8ba4 !important; font-size: 0.78rem !important; font-weight: 600 !important; }
    [data-testid="stMetricValue"] { color: #e8f4ff !important; font-size: 1.55rem !important; font-weight: 800 !important; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: rgba(255,255,255,0.02);
        border-radius: 12px;
        padding: 4px;
        border: 1px solid rgba(255,255,255,0.06);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 9px;
        font-weight: 600;
        font-size: 0.85rem;
        color: #6b8ba4;
        padding: 8px 18px;
        letter-spacing: 0.2px;
        transition: all 0.2s;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(0,194,255,0.2), rgba(0,208,132,0.12)) !important;
        color: #e8f4ff !important;
        border: 1px solid rgba(0,194,255,0.3) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { display: none; }

    /* ── Buttons ── */
    .stButton > button {
        border-radius: 10px;
        font-weight: 700;
        font-size: 0.83rem;
        transition: all 0.2s ease;
        border: 1px solid rgba(0,194,255,0.25);
        background: rgba(0,194,255,0.08);
        color: #c9d8e8;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        border-color: rgba(0,194,255,0.55);
        box-shadow: 0 4px 18px rgba(0,194,255,0.18);
        background: rgba(0,194,255,0.14);
    }

    /* ── Insight cards ── */
    .insight-card {
        background: linear-gradient(135deg,
            rgba(124,77,255,0.1) 0%,
            rgba(0,194,255,0.05) 100%);
        border: 1px solid rgba(124,77,255,0.22);
        border-radius: 12px;
        padding: 12px 16px;
        margin: 6px 0;
        font-size: 0.85rem;
        line-height: 1.5;
    }
    .insight-card.ok   { border-color: rgba(0,208,132,0.35); background: rgba(0,208,132,0.06); }
    .insight-card.warn { border-color: rgba(255,184,48,0.35); background: rgba(255,184,48,0.06); }
    .insight-card.bad  { border-color: rgba(255,75,75,0.35);  background: rgba(255,75,75,0.06);  }

    /* ── Section headers ── */
    .section-label {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: #4a6a80;
        margin: 14px 0 6px;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: rgba(4, 10, 20, 0.97) !important;
        border-right: 1px solid rgba(255,255,255,0.05) !important;
    }
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #00C2FF;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    /* ── Divider ── */
    .glow-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0,194,255,0.3), transparent);
        margin: 18px 0;
        border: none;
    }

    /* ── Running indicator ── */
    .running-badge {
        display: inline-block;
        background: rgba(0,208,132,0.15);
        border: 1px solid rgba(0,208,132,0.4);
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.75rem;
        font-weight: 700;
        color: #00D084;
        animation: pulse 1.5s ease-in-out infinite;
    }
    .paused-badge {
        display: inline-block;
        background: rgba(255,184,48,0.12);
        border: 1px solid rgba(255,184,48,0.35);
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.75rem;
        font-weight: 700;
        color: #FFB830;
    }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.55} }

    /* ── Log box ── */
    .train-log {
        background: rgba(0,0,0,0.4);
        border: 1px solid rgba(0,194,255,0.1);
        border-radius: 10px;
        padding: 12px;
        font-family: 'JetBrains Mono', 'Courier New', monospace;
        font-size: 0.76rem;
        color: #7FDBFF;
        max-height: 260px;
        overflow-y: auto;
        white-space: pre-wrap;
    }

    /* ── Sliders ── */
    .stSlider [data-baseweb="slider"] { margin-top: -4px; }

    /* ─── Hide default header decorations ── */
    header[data-testid="stHeader"] { background: transparent; }
    .block-container { padding-top: 1.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ──────────────────────────────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).resolve().parent / "ev_charging_grid_env" / "config" / "config.yaml"


def _ensure_state() -> None:
    if "sim_state" not in st.session_state:
        config = load_default_config(str(_CONFIG_PATH))
        st.session_state.config = config
        st.session_state.sim_state = build_simulation(config, seed=42)
        st.session_state.selected_policy = "Heuristic"
        st.session_state.running = False
        st.session_state.refresh_ms = 220
        st.session_state.train_log: list[str] = []
        st.session_state.train_results: dict[str, Any] = {}
        st.session_state.training_running = False


_ensure_state()

# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────────────────


def _sidebar() -> tuple[str, str | None, int]:
    with st.sidebar:
        st.markdown("### ⚡ EV Grid Optimizer")
        st.markdown('<div class="section-label">Environment</div>', unsafe_allow_html=True)

        cfg = st.session_state.config
        cfg["base_arrival_rate"] = st.slider("Traffic Intensity", 1.0, 12.0, float(cfg.get("base_arrival_rate", 6.0)), 0.5)
        cfg["base_solar_capacity_kw"] = st.slider("Solar Capacity (kW)", 20.0, 250.0, float(cfg.get("base_solar_capacity_kw", 120.0)), 10.0)
        cfg["emergency_arrival_prob"] = st.slider("Emergency Rate", 0.0, 0.20, float(cfg.get("emergency_arrival_prob", 0.04)), 0.01)
        cfg["grid_limit_kw"] = st.slider("Grid Limit (kW)", 500.0, 4000.0, float(cfg.get("grid_limit_kw", 1800.0)), 100.0)
        cfg["episode_length"] = int(st.slider("Episode Length", 50, 1000, int(cfg.get("episode_length", 300)), 50))

        st.markdown('<div class="section-label">Agent</div>', unsafe_allow_html=True)
        policy_name = st.selectbox("Policy", ["Random", "Heuristic", "PPO", "MAPPO"], index=1)
        checkpoint = st.text_input("Checkpoint path (PPO/MAPPO)", "", placeholder="Optional .pt file path")
        step_batch = int(st.slider("Steps per run", 1, 30, 5))
        refresh_ms = int(st.slider("Refresh (ms)", 80, 1200, 220, 20))
        st.session_state.refresh_ms = refresh_ms

        st.markdown('<div class="section-label">Status</div>', unsafe_allow_html=True)
        state = st.session_state.sim_state
        ts = state.env.episode_state.time_step
        ep_len = state.env.episode_state.episode_length
        progress = ts / max(1, ep_len)
        st.progress(progress, text=f"Step {ts} / {ep_len}")

        if st.session_state.running:
            st.markdown('<span class="running-badge">● RUNNING</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="paused-badge">⏸ PAUSED</span>', unsafe_allow_html=True)

        st.markdown("---")
        st.caption("Multi-Agent EV Charging Grid Optimizer · v2.0")

    return policy_name, (checkpoint.strip() or None), step_batch


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────


def _run_steps(policy_name: str, checkpoint: str | None, steps: int) -> None:
    sim = st.session_state.sim_state
    bundle = build_policy_bundle(policy_name, sim.env.num_stations, checkpoint_path=checkpoint)
    if bundle.note:
        st.info(bundle.note, icon="ℹ️")
    for _ in range(steps):
        sim.step_with_policies(bundle.coordinator, bundle.stations)
        if sim.done:
            st.session_state.running = False
            break


def _stats() -> dict[str, float]:
    return st.session_state.sim_state.env.episode_stats


# ──────────────────────────────────────────────────────────────────────────────
# AI INSIGHTS PANEL
# ──────────────────────────────────────────────────────────────────────────────


def _ai_insights_panel() -> None:
    stats = _stats()
    state = st.session_state.sim_state
    env = state.env

    vehicles_seen = max(1.0, stats.get("vehicles_seen", 1.0))
    avg_wait = stats.get("total_wait_time", 0.0) / vehicles_seen
    solar_kwh = stats.get("solar_energy_kwh", 0.0)
    total_kwh = max(1e-6, stats.get("total_energy_kwh", 0.0))
    solar_pct = 100.0 * solar_kwh / total_kwh
    overloads = int(stats.get("grid_overload_events", 0))
    em_served = stats.get("emergency_served", 0.0)
    em_missed = stats.get("emergency_missed", 0.0)
    grid_pct = 100.0 * env.episode_state.grid.total_grid_kw_used / max(1.0, env.episode_state.grid.global_limit_kw)

    st.markdown('<div class="section-label">🧠 AI Insights</div>', unsafe_allow_html=True)

    insights: list[tuple[str, str, str]] = []

    # Grid pressure
    if grid_pct > 100:
        insights.append(("bad", "⚡ Grid Overload", f"Grid at {grid_pct:.0f}% — critical overload. Reduce charging intensity or increase capacity."))
    elif grid_pct > 80:
        insights.append(("warn", "⚠️ Grid Pressure", f"Grid at {grid_pct:.0f}% — approaching limit. Consider redistributing load."))
    else:
        insights.append(("ok", "✅ Grid Stable", f"Grid at {grid_pct:.0f}% — operating normally within safe bounds."))

    # Solar utilization
    if solar_pct >= 50:
        insights.append(("ok", "☀️ High Solar Usage", f"{solar_pct:.1f}% of energy from solar — excellent green efficiency."))
    elif solar_pct >= 20:
        insights.append(("warn", "🌤️ Moderate Solar", f"{solar_pct:.1f}% solar. More solar-capable stations may be underutilized."))
    else:
        insights.append(("bad", "🌧️ Low Solar", f"Only {solar_pct:.1f}% solar energy. Check weather conditions and solar station status."))

    # Emergency response
    total_em = em_served + em_missed
    if total_em > 0:
        em_rate = 100.0 * em_served / total_em
        level = "ok" if em_rate >= 80 else ("warn" if em_rate >= 50 else "bad")
        icon = "✅" if em_rate >= 80 else ("⚠️" if em_rate >= 50 else "🚨")
        insights.append((level, f"{icon} Emergency Rate {em_rate:.0f}%", f"{int(em_served)} served, {int(em_missed)} missed. {'Excellent response.' if em_rate>=80 else 'Improve emergency routing priority.'}"))
    else:
        insights.append(("ok", "🚨 No Emergencies Yet", "No emergency vehicles in this episode so far."))

    # Wait time
    if avg_wait > 15:
        insights.append(("bad", "⏳ High Wait Times", f"Average wait: {avg_wait:.1f} min. Stations are congested — consider adding capacity."))
    elif avg_wait > 5:
        insights.append(("warn", "⏳ Moderate Wait", f"Average wait: {avg_wait:.1f} min. Queues manageable but not optimal."))
    else:
        insights.append(("ok", "✅ Low Wait Times", f"Average wait: {avg_wait:.1f} min — vehicles are being served quickly."))

    # Overload history
    if overloads > 5:
        insights.append(("bad", "🔴 Frequent Overloads", f"{overloads} overload events recorded. Review grid capacity limits."))
    elif overloads > 0:
        insights.append(("warn", "🟡 Minor Overloads", f"{overloads} grid overload events this episode."))

    for (level, title, body) in insights:
        st.markdown(
            f'<div class="insight-card {level}"><b>{title}</b><br>{body}</div>',
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────────────────────
# METRIC PANEL
# ──────────────────────────────────────────────────────────────────────────────


def _metric_panel() -> None:
    stats = _stats()
    vehicles_seen = max(1.0, stats.get("vehicles_seen", 1.0))
    avg_wait = stats.get("total_wait_time", 0.0) / vehicles_seen
    solar_kwh = stats.get("solar_energy_kwh", 0.0)
    total_kwh = max(1e-6, stats.get("total_energy_kwh", 0.0))
    solar_pct = 100.0 * solar_kwh / total_kwh
    overloads = int(stats.get("grid_overload_events", 0))
    total_reward = stats.get("total_reward", 0.0)
    em_served = int(stats.get("emergency_served", 0))
    em_missed = int(stats.get("emergency_missed", 0))
    vehicles_seen_int = int(stats.get("vehicles_seen", 0))

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("🏆 Total Reward", f"{total_reward:.1f}")
    c2.metric("🚗 Vehicles Seen", f"{vehicles_seen_int:,}")
    c3.metric("⏳ Avg Wait (min)", f"{avg_wait:.1f}")
    c4.metric("☀️ Solar %", f"{solar_pct:.1f}%")
    c5.metric("⚡ Grid Overloads", f"{overloads}")
    c6.metric("🚨 Emergency S/M", f"{em_served}/{em_missed}")


# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: LIVE OPS
# ──────────────────────────────────────────────────────────────────────────────


def _tab_live_ops(policy_name: str, checkpoint: str | None, step_batch: int) -> None:
    # Control bar
    ctrl1, ctrl2, ctrl3, ctrl4, ctrl5 = st.columns([1, 1, 1, 1, 2])
    if ctrl1.button("▶ Start", use_container_width=True):
        st.session_state.running = True
    if ctrl2.button("⏸ Pause", use_container_width=True):
        st.session_state.running = False
    if ctrl3.button("⏭ Step", use_container_width=True):
        _run_steps(policy_name, checkpoint, 1)
    if ctrl4.button("🔄 Reset", use_container_width=True):
        st.session_state.sim_state = build_simulation(st.session_state.config, seed=42)
        st.session_state.running = False
        st.rerun()
    with ctrl5:
        if st.session_state.sim_state.done:
            st.warning("Episode complete — press Reset to start a new one.", icon="🏁")

    if st.session_state.running:
        _run_steps(policy_name, checkpoint, step_batch)

    st.markdown('<hr class="glow-divider">', unsafe_allow_html=True)
    _metric_panel()
    st.markdown('<hr class="glow-divider">', unsafe_allow_html=True)

    state = st.session_state.sim_state
    env = state.env

    # Main chart row: map (left) + queue + gauge + heatmap (right)
    col_left, col_right = st.columns([2.2, 1.0])
    with col_left:
        st.plotly_chart(station_map_figure(env), use_container_width=True, theme=None)
        # AI insights below the map
        _ai_insights_panel()

    with col_right:
        st.plotly_chart(queue_line_figure(env), use_container_width=True, theme=None)
        st.plotly_chart(
            grid_utilization_gauge(
                env.episode_state.grid.total_grid_kw_used,
                env.episode_state.grid.global_limit_kw,
            ),
            use_container_width=True,
            theme=None,
        )
        st.plotly_chart(solar_breakdown_chart(env), use_container_width=True, theme=None, key="live_solar")
        st.plotly_chart(station_load_heatmap(env), use_container_width=True, theme=None)

    # History charts
    hist_df = state.history_df()
    if not hist_df.empty:
        st.markdown('<hr class="glow-divider">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Episode History</div>', unsafe_allow_html=True)
        reward_fig, energy_fig, travel_fig = history_figures(hist_df)
        h1, h2 = st.columns(2)
        h1.plotly_chart(reward_fig, use_container_width=True, theme=None)
        h2.plotly_chart(energy_fig, use_container_width=True, theme=None)
        st.plotly_chart(travel_fig, use_container_width=True, theme=None)

        with st.expander("📋 Step-by-step replay (last 20 timesteps)"):
            st.dataframe(hist_df.tail(20).style.format("{:.3f}"), use_container_width=True)

        csv_bytes = hist_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Export Episode CSV",
            data=csv_bytes,
            file_name="ev_grid_episode.csv",
            mime="text/csv",
        )

    if st.session_state.running:
        time.sleep(max(0.03, st.session_state.refresh_ms / 1000.0))
        st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: ANALYTICS
# ──────────────────────────────────────────────────────────────────────────────


def _tab_analytics() -> None:
    state = st.session_state.sim_state
    hist_df = state.history_df()

    if hist_df.empty:
        st.info("Run a simulation first — step through at least a few timesteps to see analytics.", icon="💡")
        return

    st.markdown('<div class="section-label">Energy & Solar</div>', unsafe_allow_html=True)
    a1, a2 = st.columns(2)
    with a1:
        st.plotly_chart(solar_breakdown_chart(state.env), use_container_width=True, theme=None, key="analytics_solar")
    with a2:
        # Episode-level energy trend
        import plotly.graph_objects as go
        fig = go.Figure()
        if "solar_util_pct" in hist_df.columns:
            fig.add_trace(go.Scatter(
                x=hist_df["timestep"], y=hist_df["solar_util_pct"],
                name="Solar %", line=dict(color="#FFB830", width=2),
                fill="tozeroy", fillcolor="rgba(255,184,48,0.07)",
            ))
        fig.update_layout(
            title="☀️ Solar Utilisation % Over Episode",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True, theme=None)

    st.markdown('<hr class="glow-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Emergency Response</div>', unsafe_allow_html=True)
    st.plotly_chart(emergency_timeline_chart(hist_df), use_container_width=True, theme=None)

    st.markdown('<hr class="glow-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Reward Distribution</div>', unsafe_allow_html=True)
    st.plotly_chart(reward_distribution_chart(hist_df), use_container_width=True, theme=None)

    st.markdown('<hr class="glow-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Episode Summary Stats</div>', unsafe_allow_html=True)
    stats = _stats()
    vehicles_seen = max(1.0, stats.get("vehicles_seen", 1.0))
    summary = {
        "Metric": [
            "Total Reward", "Vehicles Seen", "Avg Wait Time (min)",
            "Solar Energy (kWh)", "Grid Energy (kWh)", "Solar %",
            "Emergency Served", "Emergency Missed", "Grid Overloads",
        ],
        "Value": [
            f"{stats.get('total_reward', 0.0):.2f}",
            f"{int(stats.get('vehicles_seen', 0)):,}",
            f"{stats.get('total_wait_time', 0.0) / vehicles_seen:.2f}",
            f"{stats.get('solar_energy_kwh', 0.0):.2f}",
            f"{max(0.0, stats.get('total_energy_kwh', 0.0) - stats.get('solar_energy_kwh', 0.0)):.2f}",
            f"{100.0 * stats.get('solar_energy_kwh', 0.0) / max(1e-6, stats.get('total_energy_kwh', 0.0)):.1f}%",
            f"{int(stats.get('emergency_served', 0))}",
            f"{int(stats.get('emergency_missed', 0))}",
            f"{int(stats.get('grid_overload_events', 0))}",
        ],
    }
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: COMPARE POLICIES
# ──────────────────────────────────────────────────────────────────────────────


def _tab_compare() -> None:
    st.markdown('<div class="section-label">Policy Benchmarking</div>', unsafe_allow_html=True)

    col_cfg, col_run = st.columns([2, 1])
    with col_cfg:
        policies_to_compare = st.multiselect(
            "Policies to compare",
            ["Random", "Heuristic", "PPO", "MAPPO"],
            default=["Random", "Heuristic"],
        )
        n_steps = st.slider("Simulation steps per policy", 20, 300, 80, step=10)

    with col_run:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("🚀 Run Benchmark", use_container_width=True)

    if run_btn and policies_to_compare:
        records = []
        progress_bar = st.progress(0, text="Benchmarking policies…")
        for p_idx, policy in enumerate(policies_to_compare):
            progress_bar.progress((p_idx) / len(policies_to_compare), text=f"Running {policy}…")
            config = dict(st.session_state.config)
            sim = build_simulation(config, seed=123)
            bundle = build_policy_bundle(policy, sim.env.num_stations)
            for _ in range(n_steps):
                sim.step_with_policies(bundle.coordinator, bundle.stations)
                if sim.done:
                    break
            s = sim.env.episode_stats
            veh = max(1.0, s.get("vehicles_seen", 1.0))
            records.append({
                "policy": policy,
                "total_reward": round(float(s.get("total_reward", 0.0)), 2),
                "avg_wait": round(float(s.get("total_wait_time", 0.0)) / veh, 3),
                "solar_util_pct": round(
                    100.0 * float(s.get("solar_energy_kwh", 0.0)) / max(1e-6, float(s.get("total_energy_kwh", 0.0))), 1
                ),
                "emergency_served": int(s.get("emergency_served", 0)),
                "emergency_missed": int(s.get("emergency_missed", 0)),
                "grid_overloads": int(s.get("grid_overload_events", 0)),
            })
        progress_bar.progress(1.0, text="Done!")
        df = pd.DataFrame(records)

        st.markdown('<hr class="glow-divider">', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

        cmp1, cmp2 = st.columns(2)
        with cmp1:
            st.plotly_chart(comparison_bar(df), use_container_width=True, theme=None)
        with cmp2:
            st.plotly_chart(policy_radar_chart(df), use_container_width=True, theme=None)

        # Highlight winner
        if len(df) > 1:
            best_policy = df.loc[df["total_reward"].idxmax(), "policy"]
            st.success(f"🏆 **Best Policy: {best_policy}** — highest total reward over {n_steps} steps.", icon="🏆")

        # Export comparison
        st.download_button(
            "⬇️ Export Comparison CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="policy_comparison.csv",
            mime="text/csv",
        )
    else:
        if not policies_to_compare:
            st.warning("Select at least one policy to benchmark.", icon="⚠️")
        else:
            st.info("Click **Run Benchmark** to compare the selected policies.", icon="💡")


# ──────────────────────────────────────────────────────────────────────────────
# TAB 4: TRAIN AI
# ──────────────────────────────────────────────────────────────────────────────


def _run_training_thread(
    algorithm: str,
    total_steps: int,
    lr: float,
    gamma: float,
    seed: int,
    log_list: list[str],
    results_holder: dict,
) -> None:
    """Background thread: run a short PPO/MAPPO training loop."""
    try:
        from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv
        from ev_charging_grid_env.envs.pettingzoo_ev_env import PettingZooEVChargingEnv
        from ev_charging_grid_env.training.algorithms.ppo_trainer import PPOConfig, PPOTrainer
        from ev_charging_grid_env.training.algorithms.mappo_trainer import MAPPOConfig, MAPPOTrainer

        log_list.append(f"[{algorithm.upper()}] Starting training… seed={seed}")
        config = dict(st.session_state.config)

        with tempfile.TemporaryDirectory() as tmpdir:
            run_path = Path(tmpdir)

            if algorithm == "ppo":
                rollout = min(512, total_steps // 4)
                cfg = PPOConfig(total_steps=total_steps, rollout_steps=rollout, lr=lr, gamma=gamma, seed=seed)
                env = MultiAgentEVChargingGridEnv(config=config)
                trainer = PPOTrainer(env, cfg, run_path)
                result = trainer.train()
                import torch
                ckpt_bytes = io.BytesIO()
                torch.save(trainer.model.state_dict(), ckpt_bytes)
                results_holder["checkpoint_bytes"] = ckpt_bytes.getvalue()
                results_holder["checkpoint_name"] = f"ppo_seed{seed}.pt"
            else:
                cycles = min(5000, total_steps // 2)
                rollout = min(256, cycles // 4)
                cfg = MAPPOConfig(total_cycles=cycles, rollout_cycles=rollout, lr=lr, gamma=gamma, seed=seed)
                env = PettingZooEVChargingEnv(config=config)
                trainer = MAPPOTrainer(env, cfg, run_path)
                result = trainer.train()
                import torch
                ckpt_bytes = io.BytesIO()
                torch.save(trainer.station_policy.state_dict(), ckpt_bytes)
                results_holder["checkpoint_bytes"] = ckpt_bytes.getvalue()
                results_holder["checkpoint_name"] = f"mappo_station_seed{seed}.pt"

        results_holder["result"] = result
        log_list.append(
            f"[{algorithm.upper()}] Training complete! "
            f"mean_reward={result.get('mean_update_reward', 0.0):.4f} "
            f"last_reward={result.get('last_update_reward', 0.0):.4f}"
        )
    except Exception as exc:
        log_list.append(f"[ERROR] {type(exc).__name__}: {exc}")
    finally:
        results_holder["done"] = True


def _tab_train() -> None:
    st.markdown('<div class="section-label">Configure Training Run</div>', unsafe_allow_html=True)
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        algo = st.selectbox("Algorithm", ["ppo", "mappo"], format_func=str.upper, key="train_algo")
    with t2:
        total_steps = st.selectbox("Training Steps", [1000, 5000, 10000, 40000], index=1, key="train_steps")
    with t3:
        lr = st.select_slider("Learning Rate", [1e-4, 3e-4, 1e-3], value=3e-4, key="train_lr", format_func=lambda x: f"{x:.0e}")
    with t4:
        gamma = st.slider("Discount γ", 0.90, 0.999, 0.99, 0.001, key="train_gamma")

    seed_train = st.number_input("Random Seed", 0, 9999, 42, key="train_seed")

    col_btn, col_note = st.columns([1, 3])
    with col_btn:
        start_btn = st.button("🤖 Start Training", use_container_width=True, disabled=st.session_state.training_running)
    with col_note:
        st.caption(
            f"Runs ~{total_steps:,} steps of **{algo.upper()}** in the background. "
            "A checkpoint (.pt) will be available for download once complete."
        )

    # Launch background training
    if start_btn and not st.session_state.training_running:
        st.session_state.train_log = []
        st.session_state.train_results = {"done": False}
        st.session_state.training_running = True
        thread = threading.Thread(
            target=_run_training_thread,
            args=(
                algo,
                total_steps,
                float(lr),
                float(gamma),
                int(seed_train),
                st.session_state.train_log,
                st.session_state.train_results,
            ),
            daemon=True,
        )
        thread.start()
        st.info("Training launched in background thread. Refresh the page or click below to check progress.", icon="⚙️")

    st.markdown('<hr class="glow-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Training Log</div>', unsafe_allow_html=True)

    log = st.session_state.train_log
    results = st.session_state.train_results

    if results.get("done"):
        st.session_state.training_running = False
        result = results.get("result", {})
        if result:
            r1, r2, r3 = st.columns(3)
            r1.metric("Mean Reward", f"{result.get('mean_update_reward', 0.0):.4f}")
            r2.metric("Last Reward", f"{result.get('last_update_reward', 0.0):.4f}")
            steps_key = "total_steps" if "total_steps" in result else "cycles"
            r3.metric("Steps Run", f"{int(result.get(steps_key, 0)):,}")

        # Download checkpoint
        ckpt_bytes = results.get("checkpoint_bytes")
        if ckpt_bytes:
            st.download_button(
                "⬇️ Download Checkpoint (.pt)",
                data=ckpt_bytes,
                file_name=results.get("checkpoint_name", "checkpoint.pt"),
                mime="application/octet-stream",
            )
        st.success("✅ Training complete!", icon="✅")

    elif st.session_state.training_running:
        st.markdown(
            '<span class="running-badge">● TRAINING IN PROGRESS</span>',
            unsafe_allow_html=True,
        )
        if st.button("🔄 Refresh log"):
            st.rerun()

    if log:
        log_text = "\n".join(log[-40:])
        st.markdown(
            f'<div class="train-log">{log_text}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("No training activity yet. Configure and click **Start Training** above.")

    st.markdown('<hr class="glow-divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Hyperparameter Guide</div>', unsafe_allow_html=True)
    guide = {
        "Parameter": ["Learning Rate", "Discount γ", "Training Steps", "Algorithm"],
        "Recommended": ["3e-4", "0.99", "10000+", "MAPPO for multi-agent"],
        "Effect": [
            "Lower = more stable, higher = faster but may diverge",
            "Closer to 1 = values long-term reward more",
            "More steps → better policy, longer runtime",
            "PPO = centralized control, MAPPO = decentralized station agents",
        ],
    }
    st.dataframe(pd.DataFrame(guide), use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    # Header
    st.markdown(
        '<div class="main-title">⚡ Multi-Agent EV Charging Grid Optimizer</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="main-subtitle">'
        "AI-powered real-time charging grid management with PPO & MAPPO reinforcement learning"
        "</div>",
        unsafe_allow_html=True,
    )

    policy_name, checkpoint, step_batch = _sidebar()
    st.session_state.selected_policy = policy_name

    tab_live, tab_analytics, tab_compare, tab_train = st.tabs(
        ["🔴 Live Operations", "📊 Analytics", "⚔️ Compare Policies", "🤖 Train AI"]
    )

    with tab_live:
        _tab_live_ops(policy_name, checkpoint, step_batch)

    with tab_analytics:
        _tab_analytics()

    with tab_compare:
        _tab_compare()

    with tab_train:
        _tab_train()


if __name__ == "__main__":
    main()
