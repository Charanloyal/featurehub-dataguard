"""
Chart Helpers
Builds polished, accessible Plotly visualizations for quality trends, latency benchmarks, and incident analytics.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict, Any


def create_quality_trend_chart(runs: List[Dict[str, Any]]) -> go.Figure:
    """Create quality validation trend line chart."""
    if not runs:
        fig = go.Figure()
        fig.add_annotation(text="No validation runs available", showarrow=False, font=dict(size=14, color="#64748B"))
        fig.update_layout(height=280, margin=dict(l=20, r=20, t=30, b=20))
        return fig

    df = pd.DataFrame(runs)
    if "timestamp" in df.columns and "success_rate" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
        fig = px.line(
            df,
            x="timestamp",
            y="success_rate",
            markers=True,
            title="Validation Pass Rate Over Time (%)",
            labels={"success_rate": "Pass Rate (%)", "timestamp": "Timestamp"},
            color_discrete_sequence=["#10B981"]
        )
        fig.update_traces(line=dict(width=2.5), marker=dict(size=6))
        fig.add_hline(y=100.0, line_dash="dash", line_color="#059669", annotation_text="Target SLA: 100%")
        fig.update_layout(
            height=280,
            margin=dict(l=20, r=20, t=40, b=20),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            xaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
            yaxis=dict(range=[80, 105], showgrid=True, gridcolor="#F1F5F9")
        )
        return fig

    return go.Figure()


def create_stage_latency_chart(stages: Dict[str, Any]) -> go.Figure:
    """Create per-stage execution latency horizontal bar chart."""
    if not stages:
        fig = go.Figure()
        fig.add_annotation(text="No latency breakdown available", showarrow=False)
        fig.update_layout(height=320)
        return fig

    names = []
    latencies = []
    for k, v in stages.items():
        names.append(k.replace("_", " ").title())
        lat = v.get("mean_ms", 0.0) if isinstance(v, dict) else float(v)
        latencies.append(lat)

    df = pd.DataFrame({"Stage": names, "Latency (ms)": latencies})
    df = df.sort_values("Latency (ms)", ascending=True)

    fig = px.bar(
        df,
        x="Latency (ms)",
        y="Stage",
        orientation="h",
        title="11-Stage Pipeline Execution Breakdown (ms)",
        color="Latency (ms)",
        color_continuous_scale="Blues"
    )
    fig.update_layout(
        height=340,
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        coloraxis_showscale=False,
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
        yaxis=dict(showgrid=False)
    )
    return fig


def create_incident_distribution_chart(incidents: List[Dict[str, Any]]) -> go.Figure:
    """Create incident severity breakdown donut chart."""
    if not incidents:
        fig = go.Figure()
        fig.add_annotation(text="Zero Incidents Logged", showarrow=False, font=dict(size=14, color="#10B981"))
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10))
        return fig

    df = pd.DataFrame(incidents)
    sev_counts = df["severity"].value_counts().reset_index()
    sev_counts.columns = ["Severity", "Count"]

    color_map = {
        "CRITICAL": "#EF4444",
        "HIGH": "#F97316",
        "MEDIUM": "#FBBF24",
        "LOW": "#3B82F6"
    }

    fig = px.pie(
        sev_counts,
        names="Severity",
        values="Count",
        hole=0.55,
        title="Incidents by Severity",
        color="Severity",
        color_discrete_map=color_map
    )
    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="#FFFFFF"
    )
    return fig
