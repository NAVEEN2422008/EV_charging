"""Plotly visualization helpers for dashboard — enhanced with new chart types."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ev_charging_grid_env.envs.ev_charging_env import MultiAgentEVChargingGridEnv

# ---------------------------------------------------------------------------
# Shared dark-theme layout defaults
# ---------------------------------------------------------------------------

_DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color="#c9d8e8"),
)


def _apply_dark(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(height=height, **_DARK)
    return fig


# ---------------------------------------------------------------------------
# Station map
# ---------------------------------------------------------------------------


def station_map_figure(env: MultiAgentEVChargingGridEnv) -> go.Figure:
    """Interactive scatter map of all charging stations with live status."""
    rows = []
    for station in env.episode_state.stations:
        rows.append(
            {
                "station": f"S{station.station_id}",
                "x": station.location_xy[0],
                "y": station.location_xy[1],
                "queue": len(station.queue),
                # size must be > 0 for Plotly px.scatter; add 1 to avoid 0-size markers
                "size_display": max(1, len(station.queue) + 1),
                "charging": len(station.charging_vehicles),
                "status": "outage" if station.outage_time_left > 0 else ("solar" if station.has_solar else "grid"),
                "solar_kw": round(station.solar_kw_used, 2),
                "grid_kw": round(station.grid_kw_used, 2),
                "price": round(station.dynamic_price, 3),
                "charger_type": station.charger_type,
            }
        )
    df = pd.DataFrame(rows)

    color_map = {
        "solar": "#00D084",
        "grid": "#00C2FF",
        "outage": "#FF4B4B",
    }

    fig = px.scatter(
        df,
        x="x",
        y="y",
        color="status",
        size="size_display",
        size_max=45,
        hover_name="station",
        hover_data={
            "solar_kw": True,
            "grid_kw": True,
            "queue": True,
            "charging": True,
            "price": True,
            "charger_type": True,
            "size_display": False,
            "x": False,
            "y": False,
        },
        title="⚡ City Charging Grid — Station Map",
        color_discrete_map=color_map,
    )

    # Add station labels
    for _, row in df.iterrows():
        fig.add_annotation(
            x=row["x"],
            y=row["y"] + 0.6,
            text=row["station"],
            showarrow=False,
            font=dict(size=10, color="#c9d8e8"),
        )

    # Overlay incoming vehicle positions
    if env.last_arrivals:
        arrivals_data = [
            {
                "x": v.location_xy[0],
                "y": v.location_xy[1],
                "kind": "🚨 Emergency" if v.is_emergency else "🚗 Normal",
            }
            for v in env.last_arrivals[:150]
        ]
        adf = pd.DataFrame(arrivals_data)
        fig.add_trace(
            go.Scatter(
                x=adf["x"],
                y=adf["y"],
                mode="markers",
                marker=dict(
                    size=7,
                    color=adf["kind"].map({"🚗 Normal": "#7FDBFF", "🚨 Emergency": "#FF851B"}),
                    symbol="diamond",
                    opacity=0.75,
                    line=dict(width=1, color="rgba(255,255,255,0.2)"),
                ),
                name="Incoming EVs",
                hovertext=adf["kind"],
            )
        )

    fig.update_layout(
        height=450,
        legend_title_text="Station Type",
        xaxis=dict(title="X (km)", gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(title="Y (km)", gridcolor="rgba(255,255,255,0.05)"),
        **_DARK,
    )
    return fig


# ---------------------------------------------------------------------------
# Queue line chart
# ---------------------------------------------------------------------------


def queue_line_figure(env: MultiAgentEVChargingGridEnv) -> go.Figure:
    """Bar chart of queue lengths per station with charging overlay."""
    stations = env.episode_state.stations
    labels = [f"S{s.station_id}" for s in stations]
    queues = [len(s.queue) for s in stations]
    charging = [len(s.charging_vehicles) for s in stations]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=queues,
            name="Queued",
            marker_color="#00C2FF",
            opacity=0.85,
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=charging,
            name="Charging",
            marker_color="#00D084",
            opacity=0.85,
        )
    )
    fig.update_layout(
        title="Queue & Charging Load per Station",
        barmode="stack",
        xaxis_title="Station",
        yaxis_title="Vehicles",
        height=300,
        **_DARK,
    )
    return fig


# ---------------------------------------------------------------------------
# History trend figures
# ---------------------------------------------------------------------------


def history_figures(
    history_df: pd.DataFrame,
) -> tuple[go.Figure, go.Figure, go.Figure]:
    """Return reward, grid usage, and travel distance trend plots."""
    # Reward over time
    reward_fig = go.Figure()
    reward_fig.add_trace(
        go.Scatter(
            x=history_df["timestep"],
            y=history_df["total_reward"],
            mode="lines",
            name="Cumulative Reward",
            line=dict(width=2.5, color="#00D084"),
            fill="tozeroy",
            fillcolor="rgba(0,208,132,0.07)",
        )
    )
    if "reward" in history_df.columns:
        reward_fig.add_trace(
            go.Scatter(
                x=history_df["timestep"],
                y=history_df["reward"],
                mode="lines",
                name="Step Reward",
                line=dict(width=1.5, color="#7C4DFF", dash="dot"),
                opacity=0.7,
            )
        )
    reward_fig.update_layout(title="🏆 Reward Over Time", height=280, **_DARK)

    # Grid usage vs capacity
    energy_fig = go.Figure()
    energy_fig.add_trace(
        go.Scatter(
            x=history_df["timestep"],
            y=history_df["grid_kw_used"],
            name="Grid kW Used",
            line=dict(width=2.5, color="#FF4B4B"),
            fill="tozeroy",
            fillcolor="rgba(255,75,75,0.06)",
        )
    )
    energy_fig.add_trace(
        go.Scatter(
            x=history_df["timestep"],
            y=history_df["grid_kw_limit"],
            name="Grid Capacity",
            line=dict(dash="dot", color="#AAAAAA", width=1.5),
        )
    )
    energy_fig.update_layout(title="⚡ Grid Usage vs Capacity", height=280, **_DARK)

    # Travel distance
    travel_fig = go.Figure()
    travel_fig.add_trace(
        go.Scatter(
            x=history_df["timestep"],
            y=history_df["travel_distance_km"],
            mode="lines",
            name="Avg Travel Distance",
            line=dict(width=2, color="#FFB830"),
            fill="tozeroy",
            fillcolor="rgba(255,184,48,0.06)",
        )
    )
    travel_fig.update_layout(title="🛣️ Avg Travel Distance (km)", height=280, **_DARK)

    return reward_fig, energy_fig, travel_fig


# ---------------------------------------------------------------------------
# Comparison bar chart
# ---------------------------------------------------------------------------


def comparison_bar(summary: pd.DataFrame) -> go.Figure:
    """Multi-metric grouped bar chart comparing policies."""
    metrics = ["total_reward", "avg_wait", "solar_util_pct"]
    titles = ["Total Reward", "Avg Wait Time", "Solar Util %"]
    colors = ["#00D084", "#FF4B4B", "#FFB830"]

    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=titles,
    )
    for i, (metric, color) in enumerate(zip(metrics, colors), start=1):
        if metric in summary.columns:
            fig.add_trace(
                go.Bar(
                    x=summary["policy"],
                    y=summary[metric],
                    marker_color=color,
                    name=titles[i - 1],
                    showlegend=False,
                ),
                row=1,
                col=i,
            )
    fig.update_layout(title="Policy Comparison", height=360, **_DARK)
    return fig


# ---------------------------------------------------------------------------
# Station load heatmap
# ---------------------------------------------------------------------------


def station_load_heatmap(env: MultiAgentEVChargingGridEnv) -> go.Figure:
    """Heatmap showing queue + charging load across all stations."""
    stations = env.episode_state.stations
    z = [
        [len(s.queue) for s in stations],
        [len(s.charging_vehicles) for s in stations],
        [round(s.grid_kw_used, 1) for s in stations],
    ]
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=[f"S{s.station_id}" for s in stations],
            y=["Queued", "Charging", "Grid kW"],
            colorscale="Turbo",
            showscale=True,
            hoverongaps=False,
        )
    )
    fig.update_layout(title="🔥 Station Load Heatmap", height=240, **_DARK)
    return fig


# ---------------------------------------------------------------------------
# Grid utilization gauge
# ---------------------------------------------------------------------------


def grid_utilization_gauge(grid_kw_used: float, grid_kw_limit: float) -> go.Figure:
    """Gauge chart showing real-time grid pressure as a percentage."""
    pct = 100.0 * grid_kw_used / max(1e-6, grid_kw_limit)
    bar_color = "#00D084" if pct < 70 else ("#FFB830" if pct < 100 else "#FF4B4B")
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=pct,
            number={"suffix": "%", "font": {"size": 28, "color": "#c9d8e8"}},
            delta={"reference": 70, "relative": False, "valueformat": ".1f"},
            title={"text": "Grid Utilization", "font": {"size": 14, "color": "#9fb3c8"}},
            gauge={
                "axis": {"range": [0, 150], "tickcolor": "#555"},
                "bar": {"color": bar_color, "thickness": 0.3},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 70], "color": "rgba(0,208,132,0.1)"},
                    {"range": [70, 100], "color": "rgba(255,184,48,0.1)"},
                    {"range": [100, 150], "color": "rgba(255,75,75,0.12)"},
                ],
                "threshold": {
                    "line": {"color": "#FF4B4B", "width": 3},
                    "thickness": 0.75,
                    "value": 100,
                },
            },
        )
    )
    fig.update_layout(height=250, **_DARK)
    return fig


# ---------------------------------------------------------------------------
# NEW: Solar vs Grid breakdown donut chart
# ---------------------------------------------------------------------------


def solar_breakdown_chart(env: MultiAgentEVChargingGridEnv) -> go.Figure:
    """Donut chart showing solar vs grid energy split at current timestep."""
    solar_total = sum(s.solar_kw_used for s in env.episode_state.stations)
    grid_total = sum(s.grid_kw_used for s in env.episode_state.stations)
    total = solar_total + grid_total
    if total < 1e-6:
        labels = ["Solar", "Grid"]
        values = [50.0, 50.0]
        note = "No energy delivered this step"
    else:
        labels = ["Solar ☀️", "Grid ⚡"]
        values = [solar_total, grid_total]
        note = f"Solar: {100 * solar_total / total:.1f}%"

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.65,
            marker=dict(colors=["#FFB830", "#00C2FF"]),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>%{value:.2f} kW<extra></extra>",
        )
    )
    fig.add_annotation(
        text=f"<b>{note}</b>",
        x=0.5,
        y=0.5,
        font=dict(size=12, color="#c9d8e8"),
        showarrow=False,
    )
    fig.update_layout(title="☀️ Energy Mix — Solar vs Grid", height=300, showlegend=False, **_DARK)
    return fig


# ---------------------------------------------------------------------------
# NEW: Emergency served/missed time-series
# ---------------------------------------------------------------------------


def emergency_timeline_chart(history_df: pd.DataFrame) -> go.Figure:
    """Area chart tracking emergency vehicle service over the episode."""
    if history_df.empty or "emergency_served" not in history_df.columns:
        fig = go.Figure()
        fig.update_layout(title="🚨 Emergency Timeline — No Data", height=260, **_DARK)
        return fig

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history_df["timestep"],
            y=history_df["emergency_served"],
            name="Served ✅",
            mode="lines",
            line=dict(width=2, color="#00D084"),
            fill="tozeroy",
            fillcolor="rgba(0,208,132,0.08)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=history_df["timestep"],
            y=history_df["emergency_missed"],
            name="Missed ❌",
            mode="lines",
            line=dict(width=2, color="#FF4B4B"),
            fill="tozeroy",
            fillcolor="rgba(255,75,75,0.08)",
        )
    )
    fig.update_layout(
        title="🚨 Emergency Response Timeline",
        xaxis_title="Timestep",
        yaxis_title="Count",
        height=280,
        **_DARK,
    )
    return fig


# ---------------------------------------------------------------------------
# NEW: Step reward distribution histogram
# ---------------------------------------------------------------------------


def reward_distribution_chart(history_df: pd.DataFrame) -> go.Figure:
    """Histogram of per-step rewards to visualize reward distribution."""
    if history_df.empty or "reward" not in history_df.columns:
        fig = go.Figure()
        fig.update_layout(title="🏆 Reward Distribution — No Data", height=260, **_DARK)
        return fig

    rewards = history_df["reward"].dropna()
    mean_r = float(rewards.mean())
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=rewards,
            nbinsx=30,
            marker_color="#7C4DFF",
            opacity=0.8,
            name="Step Reward",
        )
    )
    fig.add_vline(
        x=mean_r,
        line=dict(color="#00D084", width=2, dash="dash"),
        annotation_text=f"Mean: {mean_r:.2f}",
        annotation_font_color="#00D084",
        annotation_position="top right",
    )
    fig.update_layout(
        title="📊 Step Reward Distribution",
        xaxis_title="Reward",
        yaxis_title="Frequency",
        height=280,
        **_DARK,
    )
    return fig


# ---------------------------------------------------------------------------
# NEW: Policy radar chart
# ---------------------------------------------------------------------------


def policy_radar_chart(summary: pd.DataFrame) -> go.Figure:
    """Radar chart comparing policies across multiple normalized metrics."""
    if summary.empty:
        fig = go.Figure()
        fig.update_layout(title="Policy Radar — No Data", height=360, **_DARK)
        return fig

    dimensions = ["total_reward", "avg_wait", "solar_util_pct"]
    dim_labels = ["Total Reward", "Low Wait Time", "Solar Util %"]
    colors = ["#00D084", "#00C2FF", "#FFB830", "#FF4B4B", "#7C4DFF"]
    colors_fill = [
        "rgba(0,208,132,0.15)", 
        "rgba(0,194,255,0.15)", 
        "rgba(255,184,48,0.15)", 
        "rgba(255,75,75,0.15)", 
        "rgba(124,77,255,0.15)"
    ]
    fig = go.Figure()
    for i, row in summary.iterrows():
        # Normalize: total_reward higher=better, avg_wait lower=better (invert), solar higher=better
        vals = [
            float(row.get("total_reward", 0)),
            -float(row.get("avg_wait", 0)) + 50,  # Invert: lower wait → higher score
            float(row.get("solar_util_pct", 0)),
        ]
        # Close polygon
        vals_closed = vals + [vals[0]]
        labels_closed = dim_labels + [dim_labels[0]]
        fig.add_trace(
            go.Scatterpolar(
                r=vals_closed,
                theta=labels_closed,
                fill="toself",
                name=str(row.get("policy", f"Policy {i}")),
                opacity=0.75,
                line=dict(color=colors[i % len(colors)]),
                fillcolor=colors_fill[i % len(colors_fill)],
            )
        )
    fig.update_layout(
        title="🕸️ Policy Radar Chart",
        polar=dict(radialaxis=dict(visible=True, showticklabels=False)),
        height=360,
        showlegend=True,
        **_DARK,
    )
    return fig
