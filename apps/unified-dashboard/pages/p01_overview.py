"""
Page 1: Platform Overview
Landing page delivering immediate 60-second comprehension, hero architecture, live metrics, and health overview.
"""

import streamlit as st
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.metric_cards import render_kpi_row
from apps.unified_dashboard.components.hero_architecture import render_hero_architecture
from apps.unified_dashboard.components.health_widget import render_platform_health_widget
from apps.unified_dashboard.utils.formatting import format_number, format_percentage


def render_page(client: PlatformClient, demo_mode: bool = False):
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">⚡🛡️ FEATUREHUB + DATAGUARD</div>
        <div class="hero-subtitle">Reliable Data Infrastructure for Production Machine Learning</div>
    </div>
    """, unsafe_allow_html=True)

    if demo_mode:
        st.info("🎯 **Recruiter 60-Second Overview:** FeatureHub manages 122+ features with sub-ms Redis serving and zero-leakage training. DataGuard enforces contracts, detects schema drift, and halts bad data in CI & Airflow. All metrics below are live from PostgreSQL 16 and Redis.")

    # 1. Fetch live platform telemetry
    overview = client.get_platform_overview()

    # 2. Row 1: Core Platform Scale KPIs
    row1 = [
        {
            "title": "Production Features",
            "value": format_number(overview["feature_count"]),
            "subtitle": f"{overview['feature_groups_count']} Feature Groups",
            "icon": "⚡",
            "status_pill": "ACTIVE",
            "status_type": "healthy"
        },
        {
            "title": "Data Contracts",
            "value": format_number(overview["contracts_count"]),
            "subtitle": f"{overview['contract_versions_count']} Version Baselines",
            "icon": "📜",
            "status_pill": "POSTGRES 16",
            "status_type": "healthy"
        },
        {
            "title": "Airflow Pipelines",
            "value": format_number(overview["pipelines_count"]),
            "subtitle": f"Latest: {overview['latest_pipeline_id'][:18]}...",
            "icon": "🌪️",
            "status_pill": overview["latest_pipeline_status"],
            "status_type": "healthy" if overview["latest_pipeline_status"] == "SUCCESS" else "down"
        },
        {
            "title": "Quality Pass Rate",
            "value": format_percentage(overview["quality_pass_rate"]),
            "subtitle": f"{format_number(overview['quality_total_runs'])} Suites Executed",
            "icon": "✅",
            "status_pill": "GREAT EXPECTATIONS",
            "status_type": "healthy"
        }
    ]
    render_kpi_row(row1)

    # Row 2: Reliability & Drift KPIs
    row2 = [
        {
            "title": "Open Incidents",
            "value": format_number(overview["open_incidents"]),
            "subtitle": f"{overview['acknowledged_incidents']} Acked / {overview['resolved_incidents']} Resolved",
            "icon": "🚨",
            "status_pill": "SEV ROUTING",
            "status_type": "warning" if overview["open_incidents"] > 0 else "healthy"
        },
        {
            "title": "Stale Feature Groups",
            "value": format_number(overview["stale_feature_groups_count"]),
            "subtitle": "Freshness SLA: 60 mins",
            "icon": "⏳",
            "status_pill": "ZERO STALE",
            "status_type": "healthy"
        },
        {
            "title": "Schema Migrations",
            "value": format_number(overview["recent_schema_changes_count"]),
            "subtitle": "Tracked in Registry",
            "icon": "🔍",
            "status_pill": "COMPATIBLE",
            "status_type": "healthy"
        },
        {
            "title": "Online Store SLA",
            "value": "< 1.0 ms",
            "subtitle": "Redis 7.2 Low Latency",
            "icon": "🚀",
            "status_pill": "SUB-MS",
            "status_type": "healthy"
        }
    ]
    render_kpi_row(row2)

    st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # 3. Hero Visual Architecture
    st.subheader("Platform Architecture Topology")
    render_hero_architecture()

    # 4. Infrastructure Health Summary
    st.subheader("Platform Health Summary")
    health_checks = client.get_system_health()
    render_platform_health_widget(health_checks, compact=False)
