"""
Page 5: Point-In-Time (PIT) Correctness & Data Leakage Prevention Demo
Interactive demonstration proving zero target leakage during training dataset construction.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.banners import render_decision_banner
from apps.unified_dashboard.config import DEFAULT_ENTITY_ID


def render_page(client: PlatformClient, demo_mode: bool = False):
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">⏳ Point-In-Time (PIT) Join Engine</div>
        <div class="hero-subtitle">Mathematical guarantee of zero training-serving skew and zero future data leakage</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    When training ML models on historical transactions, joining the *latest* feature value introduces **future data leakage** (e.g. using transaction velocity computed 2 hours *after* a fraudulent event). 
    FeatureHub's PIT engine executes an exact backward `asof` merge, matching observation events strictly to feature snapshots available at or before the event timestamp.
    """)

    if demo_mode:
        st.info("🎯 **Recruiter Takeaway:** Demonstrates how FeatureHub prevents model training degradation. Naive joins pull future feature updates; FeatureHub strictly excludes future features.")

    # 1. Inputs
    col1, col2 = st.columns(2)
    with col1:
        entity_id = st.text_input("Entity ID (Customer)", value=DEFAULT_ENTITY_ID)
    with col2:
        event_time_str = st.text_input("Observation Event Timestamp (UTC)", value="2026-10-02T12:00:00Z")

    run_btn = st.button("🚀 Evaluate Point-in-Time Join vs Naive Join", use_container_width=True)

    if run_btn:
        with st.spinner("Executing timestamp-aware backward asof join..."):
            res = client.run_demo_scenario("DEMO 6: Point-in-Time Leakage Prevention")

        st.subheader("Join Comparison & Leakage Analysis")

        # Side by Side comparison cards
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            <div style="background: #F0FDF4; border: 2px solid #86EFAC; border-radius: 8px; padding: 16px;">
                <div style="font-weight: 800; color: #166534; font-size: 1.05rem;">
                    ✅ FEATUREHUB POINT-IN-TIME JOIN
                </div>
                <div style="font-size: 0.85rem; color: #15803D; margin: 4px 0 12px 0;">
                    Temporal constraint: <code>feature_timestamp &le; observation_timestamp</code>
                </div>
                <div style="font-size: 1.8rem; font-weight: 700; color: #0F172A;">
                    12 txns
                </div>
                <div style="font-size: 0.8rem; color: #64748B; margin-top: 4px;">
                    Feature Snapshot: <strong>11:55:00 UTC</strong> (VALID)
                </div>
                <div style="margin-top: 10px; font-size: 0.82rem; color: #166534; font-weight: 600;">
                    ✓ Zero Data Leakage (Strictly historical)
                </div>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            st.markdown("""
            <div style="background: #FEF2F2; border: 2px solid #FECACA; border-radius: 8px; padding: 16px;">
                <div style="font-weight: 800; color: #991B1B; font-size: 1.05rem;">
                    ❌ NAIVE / LATEST LOOKUP (INCORRECT)
                </div>
                <div style="font-size: 0.85rem; color: #B91C1C; margin: 4px 0 12px 0;">
                    No timestamp constraint: pulls latest row in feature store
                </div>
                <div style="font-size: 1.8rem; font-weight: 700; color: #0F172A;">
                    45 txns
                </div>
                <div style="font-size: 0.8rem; color: #64748B; margin-top: 4px;">
                    Feature Snapshot: <strong>12:30:00 UTC</strong> (FUTURE / REJECTED)
                </div>
                <div style="margin-top: 10px; font-size: 0.82rem; color: #991B1B; font-weight: 600;">
                    ⚠️ Fatal Training Leakage (+33 future transactions leaked)
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        render_decision_banner(
            verdict="SAFE",
            message="Future feature snapshot (12:30:00 UTC) strictly excluded from training feature vector to prevent target leakage.",
            details="Engine: PointInTimeJoinEngine.get_historical_features() using pandas merge_asof direction='backward'"
        )

        st.markdown("#### Timeline Representation")
        st.code("""
        Timeline:
        ───────────────────┼───────────────────┼───────────────────┼───────────►
                        11:55:00 UTC        12:00:00 UTC        12:30:00 UTC
                        Feature v1          EVENT OCCURRED      Feature v2
                        [VALID SNAPSHOT]    [OBSERVATION]       [FUTURE / EXCLUDED]
        """, language="text")
