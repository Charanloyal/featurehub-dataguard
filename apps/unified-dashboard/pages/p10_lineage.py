"""
Page 10: OpenLineage Provenance & Column-Level Lineage Explorer
Visual exploration of dataset lineage graphs, upstream sources, downstream sinks, and column-level transformations.
"""

import streamlit as st
import pandas as pd
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.metric_cards import render_kpi_row


def render_page(client: PlatformClient, demo_mode: bool = False):
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">🕸️ OpenLineage Provenance & Column Lineage</div>
        <div class="hero-subtitle">End-to-end data lineage graph tracking data products from raw ingest to Redis online features</div>
    </div>
    """, unsafe_allow_html=True)

    dg = client.dg

    # 1. Dataset Selection
    datasets = ["customer_features", "transactions", "merchants", "customers", "accounts"]
    selected_ds = st.selectbox("Select Target Dataset for Lineage Traversal", datasets)

    if demo_mode:
        st.info("🎯 **OpenLineage Compliance:** Lineage graph dynamically traversed from PostgreSQL `lineage_datasets`, `lineage_jobs`, and `lineage_edges`. Column lineage tracks mathematical transformations from source to target.")

    # 2. Fetch Live Upstream and Downstream from LineageService
    svc = dg._get_lineage_service()
    upstream = svc.get_upstream(selected_ds, depth=5)
    downstream = svc.get_downstream(selected_ds, depth=5)
    col_lineage = svc.get_column_lineage(selected_ds)

    up_datasets = upstream.get("upstream_datasets", [])
    down_datasets = downstream.get("downstream_datasets", [])
    up_pipes = upstream.get("pipelines", [])
    down_pipes = downstream.get("pipelines", [])

    # Top KPI row
    kpi_cards = [
        {
            "title": "Upstream Datasets",
            "value": len(up_datasets),
            "subtitle": f"{len(up_pipes)} Ingestion Pipelines",
            "icon": "⬆️",
            "status_pill": "MAPPED",
            "status_type": "healthy"
        },
        {
            "title": "Downstream Sinks",
            "value": len(down_datasets),
            "subtitle": f"{len(down_pipes)} Consuming Pipelines",
            "icon": "⬇️",
            "status_pill": "MATERIALIZING",
            "status_type": "healthy"
        },
        {
            "title": "Column Lineage",
            "value": len(col_lineage),
            "subtitle": "Transformation Rules",
            "icon": "📐",
            "status_pill": "DOCUMENTED",
            "status_type": "healthy"
        },
        {
            "title": "Spec Standard",
            "value": "OpenLineage 1.0",
            "subtitle": "PostgreSQL Repository",
            "icon": "📜",
            "status_pill": "ACTIVE",
            "status_type": "healthy"
        }
    ]
    render_kpi_row(kpi_cards)

    st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # 3. Visual Lineage Graph Topology
    st.subheader(f"Lineage Graph: `{selected_ds}`")

    # Render Visual Topology Flow
    c_up, c_mid, c_down = st.columns([1, 1, 1])

    with c_up:
        st.markdown("""
        <div style="background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 14px;">
            <div style="font-weight: 700; color: #475569; font-size: 0.85rem; text-transform: uppercase;">
                ⬆️ UPSTREAM SOURCES
            </div>
            <div style="margin-top: 8px;">
        """, unsafe_allow_html=True)
        if up_datasets:
            for u in up_datasets[:6]:
                st.markdown(f"- 💾 `{u}`")
        else:
            st.caption("No upstream parents recorded.")
        st.markdown("</div></div>", unsafe_allow_html=True)

    with c_mid:
        st.markdown(f"""
        <div style="background: #EFF6FF; border: 2px solid #3B82F6; border-radius: 8px; padding: 14px; text-align: center;">
            <div style="font-weight: 700; color: #1E40AF; font-size: 0.85rem; text-transform: uppercase;">
                🎯 CURRENT DATASET
            </div>
            <div style="font-size: 1.15rem; font-weight: 800; color: #0F172A; margin: 8px 0;">
                `{selected_ds}`
            </div>
            <div style="font-size: 0.75rem; color: #64748B;">
                Format: Partitioned Parquet &amp; Redis Cache
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c_down:
        st.markdown("""
        <div style="background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 14px;">
            <div style="font-weight: 700; color: #475569; font-size: 0.85rem; text-transform: uppercase;">
                ⬇️ DOWNSTREAM CONSUMERS
            </div>
            <div style="margin-top: 8px;">
        """, unsafe_allow_html=True)
        if down_datasets:
            for d in down_datasets[:6]:
                st.markdown(f"- 🚀 `{d}`")
        else:
            st.caption("No downstream consumers recorded.")
        st.markdown("</div></div>", unsafe_allow_html=True)

    st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # 4. Column-Level Lineage Explorer
    st.subheader(f"Column-Level Lineage Transformations: `{selected_ds}`")

    if col_lineage:
        target_cols = [c.get("target_column") for c in col_lineage]
        selected_col = st.selectbox("Select Target Column to Inspect Transformation Origin", target_cols)

        col_match = next((c for c in col_lineage if c.get("target_column") == selected_col), None)
        if col_match:
            dcol1, dcol2 = st.columns([1, 1])
            with dcol1:
                st.markdown(f"**Target Column:** `{col_match.get('target_column')}`")
                st.markdown(f"**Pipeline:** `{col_match.get('pipeline')}`")
                st.markdown(f"**Run ID:** `{col_match.get('run_id')}`")
                st.markdown(f"**Transformation Logic:**")
                st.info(f"💡 {col_match.get('transformation', 'Direct Pass-Through')}")

            with dcol2:
                st.markdown("**Source Column Provenance:**")
                src_list = col_match.get("source_columns", [])
                if src_list:
                    unique_srcs = []
                    seen = set()
                    for s in src_list:
                        sig = f"{s.get('dataset')}.{s.get('column')}"
                        if sig not in seen:
                            seen.add(sig)
                            unique_srcs.append(s)
                    st.dataframe(pd.DataFrame(unique_srcs), use_container_width=True)
                else:
                    st.caption("No source column facets specified.")
    else:
        st.caption(f"No column-level lineage records currently registered for `{selected_ds}`.")
