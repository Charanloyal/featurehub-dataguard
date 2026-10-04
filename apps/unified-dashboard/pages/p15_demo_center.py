"""
Page 15: Recruiter 60-Second Demo Center
One-click interactive execution of the 6 core platform reliability scenarios.
"""

import streamlit as st
import pandas as pd
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.banners import render_decision_banner, get_status_badge_html
from apps.unified_dashboard.utils.formatting import format_ms


def render_page(client: PlatformClient, demo_mode: bool = False):
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">🎯 Recruiter 60-Second Demo Center</div>
        <div class="hero-subtitle">Interactive execution harness demonstrating live platform capabilities in under one minute</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    Click any of the scenarios below to trigger real pipeline runs, automated circuit breaking, incident remediation, or point-in-time leakage prevention.
    Every scenario executes actual platform code and reports real timings and state changes.
    """)

    # Scenario Selection Grid
    scenarios = [
        ("DEMO 1: Healthy Feature Pipeline", "Run full 11-stage pipeline end-to-end: Compute -> Contract -> Schema -> Quality -> Lineage -> Materialization -> Redis -> ML."),
        ("DEMO 2: Breaking Schema Drift", "Inject dropped column. Watch DataGuard fast-fail in < 1.0s, emit OpenLineage FAIL run, and file CRITICAL incident."),
        ("DEMO 3: Bad Data (Null Violation)", "Inject 5% null values into required features. Great Expectations halts pipeline before Redis write."),
        ("DEMO 4: Stale Features (SLA Breach)", "Inject 48h stale features. Freshness SLA check catches lag and blocks materialization."),
        ("DEMO 5: Incident Investigation & Resolution", "Inspect highest severity open incident, transition state in PostgreSQL to ACKNOWLEDGED then RESOLVED."),
        ("DEMO 6: Point-in-Time Leakage Prevention", "Compare timestamp-aware PIT join vs naive join to demonstrate mathematical prevention of target leakage.")
    ]

    selected_scenario = st.selectbox(
        "Choose Demonstration Scenario to Execute",
        options=[s[0] for s in scenarios],
        format_func=lambda x: f"{x}"
    )

    # Description of selected scenario
    desc = next(s[1] for s in scenarios if s[0] == selected_scenario)
    st.info(f"💡 **Scenario Objective:** {desc}")

    run_scenario_btn = st.button("🚀 Execute Scenario Now", type="primary", use_container_width=True)

    if run_scenario_btn:
        with st.spinner(f"Executing '{selected_scenario}' across platform engine..."):
            res = client.run_demo_scenario(selected_scenario)

        st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
        st.subheader("Scenario Execution Report")

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.metric("Execution Outcome", res.get("status", "SUCCESS"))
        with sc2:
            st.metric("Execution Latency", format_ms(res.get("duration_ms", 0)))
        with sc3:
            if "records_materialized" in res:
                st.metric("Redis Records Materialized", f"{res.get('records_materialized', 0):,} rows")
            elif "incident_id" in res:
                st.metric("Incident Generated", res.get("incident_id"))
                st.markdown(get_status_badge_html(res.get("incident_severity", "CRITICAL")), unsafe_allow_html=True)
            elif "pit_feature_count" in res:
                st.metric("Historical PIT Txns", f"{res.get('pit_feature_count')} txns (Valid)")

        # Result Summary Text
        st.success(f"✓ **Execution Summary:** {res.get('summary', 'Scenario completed successfully.')}")

        # If stages returned (e.g. from integrated pipeline), render stage breakdown
        stages = res.get("stages", [])
        if stages:
            st.markdown("#### Per-Stage Circuit Breaker Execution Log")
            stage_rows = []
            for s in stages:
                stage_rows.append({
                    "Stage Index": s.get("stage_index"),
                    "Stage Name": s.get("stage_name"),
                    "Status": s.get("status"),
                    "Duration (ms)": f"{s.get('duration_ms', 0):.2f} ms",
                    "Diagnostics": s.get("message") or "Stage completed cleanly."
                })
            st.dataframe(pd.DataFrame(stage_rows), use_container_width=True)
