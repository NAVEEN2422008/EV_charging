"""Reusable Streamlit dashboard components."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st


PALETTE = {
    "bg": "#0a1020",
    "panel": "#11192d",
    "panel_alt": "#16213a",
    "text": "#edf3ff",
    "muted": "#8ba0c7",
    "good": "#13d47a",
    "warn": "#f4c542",
    "bad": "#ff5d5d",
    "accent": "#4cc9f0",
    "accent_alt": "#9b6bff",
}


def inject_theme() -> None:
    """Apply the dashboard visual language to Streamlit."""

    st.markdown(
        f"""
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

          :root {{
            --bg: {PALETTE["bg"]};
            --panel: {PALETTE["panel"]};
            --panel-alt: {PALETTE["panel_alt"]};
            --text: {PALETTE["text"]};
            --muted: {PALETTE["muted"]};
            --good: {PALETTE["good"]};
            --warn: {PALETTE["warn"]};
            --bad: {PALETTE["bad"]};
            --accent: {PALETTE["accent"]};
            --accent-alt: {PALETTE["accent_alt"]};
          }}

          .stApp {{
            background:
              radial-gradient(circle at top right, rgba(76, 201, 240, 0.12), transparent 25%),
              radial-gradient(circle at top left, rgba(19, 212, 122, 0.12), transparent 22%),
              linear-gradient(180deg, #060b16 0%, var(--bg) 55%, #080d18 100%);
            color: var(--text);
            font-family: 'Space Grotesk', sans-serif;
          }}

          [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
          [data-testid="stToolbar"] {{ right: 1rem; }}
          section[data-testid="stSidebar"] {{ display: none; }}
          .block-container {{ padding-top: 1.3rem; padding-bottom: 2rem; max-width: 1500px; }}

          .glass-card {{
            background: linear-gradient(180deg, rgba(17, 25, 45, 0.96), rgba(10, 16, 32, 0.98));
            border: 1px solid rgba(139, 160, 199, 0.18);
            border-radius: 22px;
            padding: 1rem 1.1rem;
            box-shadow: 0 18px 40px rgba(0, 0, 0, 0.32);
            overflow: hidden;
          }}

          .hero-card {{
            padding: 1.35rem 1.5rem;
            margin-bottom: 1rem;
            position: relative;
          }}

          .hero-card::after {{
            content: "";
            position: absolute;
            inset: auto -80px -80px auto;
            width: 180px;
            height: 180px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(76, 201, 240, 0.22), transparent 70%);
          }}

          .eyebrow {{
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.16em;
            font-size: 0.72rem;
            margin-bottom: 0.45rem;
          }}

          .hero-title {{
            font-size: 2.1rem;
            font-weight: 700;
            margin-bottom: 0.4rem;
          }}

          .hero-subtitle {{
            color: var(--muted);
            max-width: 55rem;
            line-height: 1.6;
          }}

          .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.4rem 0.7rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            margin: 0.2rem 0.4rem 0 0;
          }}

          .metric-value {{
            font-size: 1.6rem;
            font-weight: 700;
            margin-bottom: 0.15rem;
          }}

          .micro-copy {{
            color: var(--muted);
            font-size: 0.84rem;
            line-height: 1.45;
          }}

          .station-card {{
            min-height: 220px;
            position: relative;
          }}

          .station-accent {{
            position: absolute;
            inset: 0 auto auto 0;
            height: 4px;
            width: 100%;
            border-radius: 22px 22px 0 0;
          }}

          .mono {{
            font-family: 'IBM Plex Mono', monospace;
          }}

          .panel-title {{
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 0.9rem;
          }}

          .explain-row {{
            border-left: 4px solid rgba(76, 201, 240, 0.72);
            padding: 0.7rem 0.9rem;
            margin-bottom: 0.7rem;
            border-radius: 0 14px 14px 0;
            background: rgba(76, 201, 240, 0.08);
          }}

          .alert-row {{
            border-left-color: rgba(255, 93, 93, 0.72);
            background: rgba(255, 93, 93, 0.08);
          }}

          .control-tip {{
            padding: 0.75rem 0.9rem;
            border-radius: 16px;
            background: rgba(19, 212, 122, 0.08);
            border: 1px solid rgba(19, 212, 122, 0.14);
            color: var(--muted);
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def tone_color(tone: str) -> str:
    return {
        "good": PALETTE["good"],
        "warn": PALETTE["warn"],
        "bad": PALETTE["bad"],
        "accent": PALETTE["accent"],
    }.get(tone, PALETTE["accent"])


def metric_card(label: str, value: str, helper: str, tone: str = "accent") -> None:
    color = tone_color(tone)
    st.markdown(
        f"""
        <div class="glass-card">
          <div class="eyebrow">{label}</div>
          <div class="metric-value" style="color:{color};">{value}</div>
          <div class="micro-copy">{helper}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_header(snapshot: dict[str, Any]) -> None:
    status_tone = tone_color(snapshot["status_tone"])
    st.markdown(
        f"""
        <div class="glass-card hero-card">
          <div class="eyebrow">Smart City RL Dashboard</div>
          <div class="hero-title">Multi-Agent EV Charging Grid Optimizer</div>
          <div class="hero-subtitle">
            Watch ten charging stations coordinate queueing, solar harvesting, dynamic pricing,
            and emergency prioritization in a live simulation loop.
          </div>
          <div style="margin-top: 1rem;">
            <span class="status-pill"><span style="color:{PALETTE["accent"]};">Task</span> {snapshot["task_label"]}</span>
            <span class="status-pill"><span style="color:{status_tone};">Status</span> {snapshot["status_label"]}</span>
            <span class="status-pill"><span style="color:{PALETTE["accent_alt"]};">Step</span> {snapshot["step"]}</span>
            <span class="status-pill"><span style="color:{PALETTE["good"]};">Mode</span> {snapshot["agent_label"]}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_station_grid(stations: list[dict[str, Any]]) -> None:
    st.markdown('<div class="panel-title">City Grid View</div>', unsafe_allow_html=True)
    for start in range(0, len(stations), 5):
        cols = st.columns(5)
        for col, station in zip(cols, stations[start : start + 5]):
            with col:
                accent = tone_color(station["tone"])
                st.markdown(
                    f"""
                    <div class="glass-card station-card">
                      <div class="station-accent" style="background:{accent};"></div>
                      <div class="eyebrow">Station {station["station_id"]}</div>
                      <div class="metric-value">{station["used_slots"]}/{station["total_slots"]}</div>
                      <div class="micro-copy">Charging slots used</div>
                      <hr style="border-color: rgba(255,255,255,0.06); margin: 0.9rem 0;" />
                      <div class="micro-copy mono">Queue {station["queue_length"]} | Emergency {station["emergency_queue"]}</div>
                      <div class="micro-copy mono">Solar {station["solar_kw"]:.1f} kW | Grid {station["grid_kw"]:.1f} kW</div>
                      <div class="micro-copy mono">Price {station["price"]:.2f}x | Status {station["status"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_vehicle_flow(history: list[dict[str, Any]]) -> None:
    st.markdown('<div class="panel-title">Vehicle Flow</div>', unsafe_allow_html=True)
    steps = [row["step"] for row in history]
    arrivals = [row["arrivals"] for row in history]
    served = [row["served"] for row in history]
    emergencies = [row["emergencies"] for row in history]
    avg_wait = [row["avg_wait"] for row in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=steps, y=arrivals, mode="lines+markers", name="Incoming"))
    fig.add_trace(go.Scatter(x=steps, y=served, mode="lines+markers", name="Served"))
    fig.add_trace(go.Bar(x=steps, y=emergencies, name="Emergency", opacity=0.45))
    fig.add_trace(go.Scatter(x=steps, y=avg_wait, mode="lines", name="Avg wait", yaxis="y2"))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=320,
        legend=dict(orientation="h", y=1.15),
        yaxis2=dict(overlaying="y", side="right", title="Wait"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_energy_panel(history: list[dict[str, Any]], metrics: dict[str, Any]) -> None:
    st.markdown('<div class="panel-title">Energy Usage</div>', unsafe_allow_html=True)
    steps = [row["step"] for row in history]
    solar = [row["solar"] for row in history]
    grid = [row["grid"] for row in history]

    area = go.Figure()
    area.add_trace(go.Scatter(x=steps, y=solar, fill="tozeroy", name="Solar"))
    area.add_trace(go.Scatter(x=steps, y=grid, fill="tonexty", name="Grid"))
    area.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=300,
        legend=dict(orientation="h", y=1.15),
    )
    st.plotly_chart(area, use_container_width=True, config={"displayModeBar": False})

    donut = go.Figure(
        data=[
            go.Pie(
                labels=["Solar", "Grid"],
                values=[max(metrics["solar_kwh_used"], 0.01), max(metrics["grid_kwh_used"], 0.01)],
                hole=0.62,
                marker=dict(colors=[PALETTE["good"], PALETTE["accent"]]),
                textinfo="label+percent",
            )
        ]
    )
    donut.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=260,
        showlegend=False,
    )
    st.plotly_chart(donut, use_container_width=True, config={"displayModeBar": False})


def render_reward_chart(history: list[dict[str, Any]]) -> None:
    st.markdown('<div class="panel-title">Live Reward</div>', unsafe_allow_html=True)
    steps = [row["step"] for row in history]
    rewards = [row["reward"] for row in history]
    if rewards:
        rolling = []
        for idx in range(len(rewards)):
            start = max(0, idx - 4)
            rolling.append(sum(rewards[start : idx + 1]) / (idx - start + 1))
    else:
        rolling = []

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=steps, y=rewards, mode="lines+markers", name="Reward"))
    fig.add_trace(go.Scatter(x=steps, y=rolling, mode="lines", name="Smoothed"))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=300,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_explainer(explanations: list[str], critical_notes: list[str], enabled: bool) -> None:
    st.markdown('<div class="panel-title">AI Decision Explainer</div>', unsafe_allow_html=True)
    if not enabled:
        st.markdown('<div class="control-tip">Explainable mode is off. Toggle it on to see why stations accept, redirect, or reprioritize vehicles.</div>', unsafe_allow_html=True)
        return

    for message in explanations[:6]:
        st.markdown(f'<div class="explain-row">{message}</div>', unsafe_allow_html=True)
    for message in critical_notes[:3]:
        st.markdown(f'<div class="explain-row alert-row">{message}</div>', unsafe_allow_html=True)


def render_training_preview(curve: list[float], labels: list[str]) -> None:
    st.markdown('<div class="panel-title">Training Preview</div>', unsafe_allow_html=True)
    if not curve:
        st.markdown('<div class="control-tip">Run a preview to compare Random, Heuristic, and RL-style control behavior.</div>', unsafe_allow_html=True)
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=labels, y=curve, mode="lines+markers", name="Reward curve"))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=280,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
