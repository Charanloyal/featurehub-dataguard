"""
Page 8: Schema Diff & Compatibility Engine
Interactive schema comparison evaluating Pull Request modifications into SAFE, WARNING, or BREAKING.
"""

import streamlit as st
import pandas as pd
import json
import copy
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.banners import render_decision_banner


def render_page(client: PlatformClient, demo_mode: bool = False):
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">🔍 Schema Diff & Compatibility Engine</div>
        <div class="hero-subtitle">Automated PR gate categorizing schema drift into SAFE, WARNING, and BREAKING</div>
    </div>
    """, unsafe_allow_html=True)

    dg = client.dg
    contracts = dg.list_contracts()
    dataset_names = sorted([c.get("dataset") for c in contracts])

    if demo_mode:
        st.info("🎯 **Schema Gate Simulation:** Select a production dataset and choose an edit scenario. DataGuard evaluates type widening, nullability relaxation, and dropped columns to decide if a PR is safe to merge.")

    # Select Dataset
    selected_dataset = st.selectbox("Select Production Contract to Compare", dataset_names, index=dataset_names.index("customer_features") if "customer_features" in dataset_names else 0)

    base_contract = dg.get_contract(selected_dataset)
    if not base_contract:
        st.warning(f"Could not load baseline contract for '{selected_dataset}'.")
        return

    # Simulation Scenarios
    st.markdown("#### Choose PR Schema Edit Scenario")
    scenario = st.radio(
        "Simulation Mode",
        [
            "Scenario 1: SAFE (Add optional nullable column 'customer_loyalty_score')",
            "Scenario 2: BREAKING (Drop required existing column)",
            "Scenario 3: BREAKING (Incompatible type change: integer -> string)",
            "Scenario 4: BREAKING (Restricting nullability: nullable True -> False)",
            "Scenario 5: WARNING (Add column with default value)"
        ]
    )

    # Build target contract based on scenario
    target_contract = copy.deepcopy(base_contract)
    cols = target_contract.get("columns", [])

    if "Scenario 1" in scenario:
        cols.append({"name": "customer_loyalty_score", "type": "float", "nullable": True, "description": "Experimental score"})
    elif "Scenario 2" in scenario:
        if cols:
            dropped = cols.pop(-1)
            st.caption(f"Simulating dropped column: `{dropped.get('name')}`")
    elif "Scenario 3" in scenario:
        if cols:
            cols[0]["type"] = "string"
            st.caption(f"Simulating type alteration on `{cols[0].get('name')}` to `string`")
    elif "Scenario 4" in scenario:
        if cols:
            cols[0]["nullable"] = False
            st.caption(f"Simulating strict nullability enforcement on `{cols[0].get('name')}`")
    elif "Scenario 5" in scenario:
        cols.append({"name": "rewards_tier", "type": "string", "nullable": False, "default": "BRONZE"})

    # Execute Diff using real engine
    diff_res = dg.diff_schemas(base_contract, target_contract)
    verdict = diff_res.get("compatibility", "SAFE")
    added = diff_res.get("added_columns", [])
    removed = diff_res.get("removed_columns", [])
    type_changes = diff_res.get("type_changes", [])
    null_changes = diff_res.get("nullability_changes", [])
    summary_msg = diff_res.get("message") or "Schema diff evaluation complete."

    # 1. High Visibility Decision Banner
    st.markdown("<hr style='margin: 16px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
    render_decision_banner(
        verdict=verdict,
        message=summary_msg,
        details=f"Engine: DataGuard SchemaDiffEngine | Baseline: {selected_dataset} v1 vs Target PR"
    )

    # 2. Detailed Change Tables
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**➕ Added Columns ({len(added)})**")
        if added:
            st.dataframe(pd.DataFrame(added), use_container_width=True)
        else:
            st.caption("No columns added.")

        st.markdown(f"**🔀 Type Alterations ({len(type_changes)})**")
        if type_changes:
            st.dataframe(pd.DataFrame(type_changes), use_container_width=True)
        else:
            st.caption("No column type changes.")

    with c2:
        st.markdown(f"**➖ Removed Columns ({len(removed)})**")
        if removed:
            st.dataframe(pd.DataFrame([{"name": r} if isinstance(r, str) else r for r in removed]), use_container_width=True)
        else:
            st.caption("No columns removed.")

        st.markdown(f"**⚠️ Nullability Alterations ({len(null_changes)})**")
        if null_changes:
            st.dataframe(pd.DataFrame(null_changes), use_container_width=True)
        else:
            st.caption("No nullability changes.")
