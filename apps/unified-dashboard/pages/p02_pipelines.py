"""
Page 2: Pipeline Operations & Execution Trace
Monitors Airflow pipelines, historical runs, and execution stage failure graphs.
"""

import streamlit as st
import pandas as pd
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.banners import get_status_badge_html
from apps.unified_dashboard.utils.formatting import format_ms, format_timestamp


def render_page(client: PlatformClient, demo_mode: bool = False):
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">🌪️ Pipeline Operations Console</div>
        <div class="hero-subtitle">Airflow orchestration, execution stages, and automated failure trace</div>
    </div>
    """, unsafe_allow_html=True)

    if demo_mode:
        st.info("🎯 **Operations Drill-Down:** Filter pipeline runs by status or dataset. Selecting any pipeline reveals metadata, SLA policies, and stage-by-stage execution graphs with failure highlights.")

    # 1. Filters
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        status_filter = st.selectbox("Status Filter", ["ALL", "SUCCESS", "FAILED", "RUNNING"])
    with fcol2:
        dataset_filter = st.selectbox("Dataset Filter", ["ALL", "customer_features", "transactions", "merchants", "accounts"])
    with fcol3:
        limit_val = st.slider("Max Runs to Display", min_value=10, max_value=100, value=30)

    # Fetch real pipeline runs
    runs = client.get_pipelines(status=status_filter, dataset=dataset_filter, limit=limit_val)

    if not runs:
        st.warning("No pipeline runs found matching the selected filter criteria.")
        return

    # Pipeline Runs Table
    df_runs = pd.DataFrame(runs)
    selected_pipeline_id = st.selectbox(
        "🔎 Select Pipeline to Inspect Detail",
        options=list(df_runs["pipeline_id"].unique())
    )

    # Display Table
    display_rows = []
    for r in runs:
        display_rows.append({
            "Run ID": r.get("run_id")[:12] + "...",
            "Pipeline ID": r.get("pipeline_id"),
            "Dataset": r.get("dataset"),
            "Status": r.get("status"),
            "Duration": format_ms(r.get("duration_ms")),
            "Started At": format_timestamp(r.get("started_at")),
            "Error": r.get("error_message") or "None"
        })

    st.subheader("Historical Pipeline Execution Ledger")
    st.dataframe(pd.DataFrame(display_rows), use_container_width=True)

    # 2. Pipeline Detail Section
    st.markdown("<hr style='margin: 24px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
    st.subheader(f"Detailed Execution Trace: `{selected_pipeline_id}`")

    detail = client.get_pipeline_detail(selected_pipeline_id)
    meta = detail["metadata"]
    recent_runs = detail["runs"]
    stages = detail["stages"]

    # Metadata & SLAs
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1:
        st.markdown(f"**Dataset:** `{meta.get('dataset', 'customer_features')}`")
        st.markdown(f"**Owner:** `{meta.get('owner', 'featurestore-team')}`")
    with mcol2:
        st.markdown(f"**Contract Version:** `{meta.get('contract_version', 'v1')}`")
        st.markdown(f"**Schedule:** `{meta.get('schedule', '0 */2 * * *')}`")
    with mcol3:
        st.markdown(f"**Freshness SLA:** `{meta.get('freshness_sla_minutes', 60)} minutes`")
        st.markdown(f"**Target Store:** `Redis + Parquet`")
    with mcol4:
        latest_status = recent_runs[0].get("status", "SUCCESS") if recent_runs else "UNKNOWN"
        st.markdown(f"**Latest Status:** {get_status_badge_html(latest_status)}", unsafe_allow_html=True)
        dur = recent_runs[0].get("duration_ms") if recent_runs else 0
        st.markdown(f"**Duration:** `{format_ms(dur)}`")

    # 3. Stage Execution Graph
    st.markdown("#### Execution Stage Topology & Health")
    is_failed = latest_status == "FAILED"
    failed_error = recent_runs[0].get("error_message") if recent_runs else ""

    stage_cols = st.columns(len(stages))
    for idx, s in enumerate(stages):
        with stage_cols[idx]:
            # Determine stage health
            if is_failed and idx >= 2:  # typically failed at quality or schema
                st_badge = get_status_badge_html("FAILED" if idx == 2 else "SKIPPED")
                box_border = "#FECACA" if idx == 2 else "#E2E8F0"
                box_bg = "#FEF2F2" if idx == 2 else "#F8FAFC"
            else:
                st_badge = get_status_badge_html("SUCCESS")
                box_border = "#BBF7D0"
                box_bg = "#F0FDF4"

            st.markdown(f"""
            <div style="background: {box_bg}; border: 1px solid {box_border}; border-radius: 6px; padding: 10px 8px; text-align: center; min-height: 110px;">
                <div style="font-size: 0.72rem; font-weight: 700; color: #1E293B; margin-bottom: 4px;">
                    Stage {idx + 1}
                </div>
                <div style="font-size: 0.8rem; font-weight: 600; color: #0F172A; min-height: 36px;">
                    {s['name']}
                </div>
                <div style="margin-top: 6px;">
                    {st_badge}
                </div>
            </div>
            """, unsafe_allow_html=True)

    if is_failed and failed_error:
        st.error(f"⚠️ **Stage Failure Diagnostics:** {failed_error}")
