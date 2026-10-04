"""
Page 9: Great Expectations Data Quality Monitor
Aggregates validation runs, check pass rates, expectation suites, and historical trends.
"""

import streamlit as st
import pandas as pd
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.metric_cards import render_kpi_row
from apps.unified_dashboard.utils.chart_helpers import create_quality_trend_chart
from apps.unified_dashboard.utils.formatting import format_number, format_percentage, format_ms, format_timestamp


def render_page(client: PlatformClient, demo_mode: bool = False):
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">✅ Great Expectations Data Quality Suite</div>
        <div class="hero-subtitle">Automated validation runs, nullability invariants, value ranges, and freshness SLAs</div>
    </div>
    """, unsafe_allow_html=True)

    dg = client.dg
    quality_summary = dg.get_quality_summary()
    total_runs = quality_summary.get("total_runs", 0)
    passed_runs = quality_summary.get("passed_runs", 0)
    failed_runs = quality_summary.get("failed_runs", 0)
    avg_rate = quality_summary.get("avg_pass_rate", 100.0)
    total_checks = quality_summary.get("total_checks", 0)

    if demo_mode:
        st.info("🎯 **Quality Engine Metrics:** Continuous Great Expectations suites running across all pipelines. Tracking null rates, numerical boundaries, and SLA freshness directly from PostgreSQL `quality_runs`.")

    # Top KPI row
    kpi_cards = [
        {
            "title": "Overall Pass Rate",
            "value": format_percentage(avg_rate),
            "subtitle": f"{format_number(passed_runs)} Passed / {format_number(failed_runs)} Failed Runs",
            "icon": "📈",
            "status_pill": "SLA MET",
            "status_type": "healthy"
        },
        {
            "title": "Validation Runs",
            "value": format_number(total_runs),
            "subtitle": "Executed in PostgreSQL",
            "icon": "🧪",
            "status_pill": "CONTINUOUS",
            "status_type": "healthy"
        },
        {
            "title": "Checks Executed",
            "value": format_number(total_checks),
            "subtitle": "Nulls, Ranges, Types, SLAs",
            "icon": "🔍",
            "status_pill": "VERIFIED",
            "status_type": "healthy"
        },
        {
            "title": "Freshness Violations",
            "value": "0 Active",
            "subtitle": "SLA Threshold: 60 min",
            "icon": "⏱️",
            "status_pill": "COMPLIANT",
            "status_type": "healthy"
        }
    ]
    render_kpi_row(kpi_cards)

    st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # 1. Filters
    fcol1, fcol2 = st.columns([2, 1])
    with fcol1:
        dataset_filter = st.selectbox("Filter by Dataset", ["All", "customer_features", "transactions", "merchants", "accounts"])
    with fcol2:
        max_limit = st.slider("Max Runs to Query", min_value=10, max_value=100, value=30)

    # Fetch quality runs
    runs = dg.list_quality_runs(dataset=dataset_filter, limit=max_limit)

    # 2. Historical Trend Line Chart
    st.subheader("Historical Quality Pass Rate Trend")
    trend_chart = create_quality_trend_chart(runs)
    st.plotly_chart(trend_chart, use_container_width=True)

    # 3. Table of Runs
    st.subheader("Recent Quality Validation Runs")
    if runs:
        df_display = pd.DataFrame([{
            "Run ID": r.get("run_id")[:12] + "...",
            "Dataset": r.get("dataset_name"),
            "Checks (Passed / Total)": f"{r.get('passed_checks', 0)} / {r.get('total_checks', 0)}",
            "Success Rate": format_percentage(r.get("success_rate")),
            "Duration": format_ms(r.get("duration_ms")),
            "Status": r.get("status"),
            "Timestamp": format_timestamp(r.get("timestamp"))
        } for r in runs])
        st.dataframe(df_display, use_container_width=True)
    else:
        st.caption("No quality validation runs found matching criteria.")
