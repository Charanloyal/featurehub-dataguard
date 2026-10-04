"""
Page 11: Incident Management Center & Remediation Console
Monitors data reliability incidents, SLA violations, severity routing, and live lifecycle remediation.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.metric_cards import render_kpi_row
from apps.unified_dashboard.components.banners import get_status_badge_html
from apps.unified_dashboard.utils.chart_helpers import create_incident_distribution_chart
from apps.unified_dashboard.utils.formatting import format_number, format_timestamp


def render_page(client: PlatformClient, demo_mode: bool = False):
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">🚨 Incident Management & Remediation Center</div>
        <div class="hero-subtitle">Operational incident lifecycle: Open → Acknowledged → Resolved with PostgreSQL audit log</div>
    </div>
    """, unsafe_allow_html=True)

    dg = client.dg
    inc_summary = dg.get_incident_summary()
    open_cnt = inc_summary.get("open", 0)
    ack_cnt = inc_summary.get("acknowledged", 0)
    res_cnt = inc_summary.get("resolved", 0)
    total_cnt = inc_summary.get("total", open_cnt + ack_cnt + res_cnt)

    if demo_mode:
        st.info("🎯 **Automated Incident Lifecycle:** Incidents are created automatically when DataGuard contract or quality checks fail. Below, you can Acknowledge or Resolve incidents with real PostgreSQL database state updates.")

    # Top KPI row
    kpi_cards = [
        {
            "title": "Open Incidents",
            "value": format_number(open_cnt),
            "subtitle": "Requires Investigation",
            "icon": "🔴",
            "status_pill": "ACTIVE",
            "status_type": "down" if open_cnt > 0 else "healthy"
        },
        {
            "title": "Acknowledged",
            "value": format_number(ack_cnt),
            "subtitle": "Triage in Progress",
            "icon": "🟡",
            "status_pill": "TRIAGED",
            "status_type": "warning"
        },
        {
            "title": "Resolved",
            "value": format_number(res_cnt),
            "subtitle": "Remediated & Verified",
            "icon": "🟢",
            "status_pill": "CLOSED",
            "status_type": "healthy"
        },
        {
            "title": "Total Tracked",
            "value": format_number(total_cnt),
            "subtitle": "PostgreSQL Audit Trail",
            "icon": "📋",
            "status_pill": "AUDITED",
            "status_type": "healthy"
        }
    ]
    render_kpi_row(kpi_cards)

    st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # 1. Filters & Controls
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        status_tab = st.selectbox("Status Tab", ["ALL", "OPEN", "ACKNOWLEDGED", "RESOLVED"])
    with col2:
        sev_filter = st.selectbox("Severity Filter", ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
    with col3:
        max_rows = st.slider("Max Incidents to Show", min_value=10, max_value=100, value=30)

    # Fetch real incidents
    incidents = dg.list_incidents(
        status=None if status_tab == "ALL" else status_tab,
        severity=None if sev_filter == "ALL" else sev_filter,
        limit=max_rows
    )

    if not incidents:
        st.success("🎉 No active incidents matching the selected filter criteria!")
        return

    # Severity distribution chart
    with st.expander("📊 View Incident Severity Breakdown Chart", expanded=False):
        st.plotly_chart(create_incident_distribution_chart(incidents), use_container_width=True)

    # Incidents Table
    st.subheader("Operational Incidents Ledger")
    df_incidents = pd.DataFrame([{
        "Incident ID": i.get("incident_id"),
        "Dataset": i.get("dataset_name"),
        "Pipeline": i.get("pipeline_id"),
        "Severity": i.get("severity"),
        "Owner": i.get("owner"),
        "Status": i.get("status"),
        "Created At": format_timestamp(i.get("created_at"))
    } for i in incidents])
    st.dataframe(df_incidents, use_container_width=True)

    st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # 2. Incident Detail & Live Action Center
    st.subheader("Incident Drill-Down & Remediation Actions")
    inc_ids = [i.get("incident_id") for i in incidents]
    selected_inc_id = st.selectbox("Select Incident to Investigate & Remediate", inc_ids)

    selected_inc = dg.get_incident(selected_inc_id)
    if selected_inc:
        ic1, ic2, ic3 = st.columns(3)
        with ic1:
            st.markdown(f"**Incident ID:** `{selected_inc.get('incident_id')}`")
            st.markdown(f"**Dataset:** `{selected_inc.get('dataset_name')}`")
            st.markdown(f"**Severity:** {get_status_badge_html(selected_inc.get('severity'))}", unsafe_allow_html=True)
        with ic2:
            st.markdown(f"**Owner Assigned:** `{selected_inc.get('owner')}`")
            st.markdown(f"**Current Status:** {get_status_badge_html(selected_inc.get('status'))}", unsafe_allow_html=True)
            st.markdown(f"**Created:** `{format_timestamp(selected_inc.get('created_at'))}`")
        with ic3:
            st.markdown(f"**Pipeline ID:** `{selected_inc.get('pipeline_id', 'customer_features_pipeline')}`")
            st.markdown(f"**Check Name:** `{selected_inc.get('check_name', 'data_quality_assertion')}`")

        st.markdown("**Error Message / Root Cause:**")
        st.error(selected_inc.get("error_message") or "Anomaly detected in feature schema or quality boundary.")

        # Full DataGuard Incident Story Topology
        st.markdown("#### Incident Origin & Blast Radius Trace")
        st.code(f"""
        [INCIDENT: {selected_inc.get('incident_id')}]
              ↓
        [FAILED CHECK: {selected_inc.get('check_name')}]
              ↓
        [PIPELINE RUN: {selected_inc.get('pipeline_id')}]
              ↓
        [DATASET AFFECTED: {selected_inc.get('dataset_name')}]
              ↓
        [CIRCUIT BREAKER TRIGGERED: Materialization Aborted | Redis Cache Protected]
        """, language="text")

        # Live State Transition Buttons
        st.markdown("#### Operational Lifecycle Actions")
        curr_status = selected_inc.get("status")

        acol1, acol2 = st.columns(2)
        with acol1:
            can_ack = curr_status == "OPEN"
            if st.button("🟡 Acknowledge Incident (Start Triage)", disabled=not can_ack, use_container_width=True):
                with st.spinner("Transitioning incident state in PostgreSQL..."):
                    res = dg.acknowledge_incident(selected_inc_id, user="dashboard_engineer")
                st.success(f"Incident {selected_inc_id} successfully ACKNOWLEDGED.")
                st.rerun()

        with acol2:
            can_resolve = curr_status in ["OPEN", "ACKNOWLEDGED"]
            res_note = st.text_input("Resolution Note", value="Schema verified backward-compatible / quality verified", key="res_note")
            if st.button("🟢 Resolve Incident (Close Ticket)", disabled=not can_resolve, use_container_width=True):
                with st.spinner("Transitioning incident state to RESOLVED in PostgreSQL..."):
                    res = dg.resolve_incident(selected_inc_id, user="dashboard_engineer", resolution_notes=res_note)
                st.success(f"Incident {selected_inc_id} successfully RESOLVED.")
                st.rerun()
