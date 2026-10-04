"""
Sidebar Navigation Component
Provides primary routing, demo mode toggles, and platform context.
"""

import streamlit as st
from typing import Tuple


PAGES = [
    "1. Platform Overview",
    "2. Pipeline Operations",
    "3. FeatureHub",
    "4. DataGuard",
    "5. Data Quality",
    "6. Schema & Contracts",
    "7. Lineage",
    "8. Incidents",
    "9. ML Prediction",
    "10. Benchmarks",
    "11. System Health",
    "12. Demo Center"
]


def render_sidebar() -> Tuple[str, bool]:
    """
    Renders sidebar navigation and controls.
    Returns: (selected_page_name, is_demo_mode_active)
    """
    with st.sidebar:
        st.markdown("""
        <div style="padding: 4px 0 16px 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.5rem;">⚡🛡️</span>
                <span style="font-weight: 800; font-size: 1.15rem; color: #0F172A; letter-spacing: -0.02em;">
                    FeatureHub + DataGuard
                </span>
            </div>
            <div style="font-size: 0.75rem; color: #64748B; margin-top: 4px; font-weight: 500;">
                Production Data & ML Reliability Platform
            </div>
            <div style="margin-top: 8px;">
                <span class="status-pill status-healthy">● PLATFORM LIVE</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Demo Mode Toggle
        demo_mode = st.toggle("🎯 Recruiter Demo Mode", value=st.session_state.get("demo_mode", False), help="Enables guided walkthrough callouts and pre-filled inputs for fast evaluation.")
        st.session_state["demo_mode"] = demo_mode

        # Navigation Menu
        default_index = 0
        if "nav_selection" in st.session_state and st.session_state["nav_selection"] in PAGES:
            default_index = PAGES.index(st.session_state["nav_selection"])

        selected_page = st.radio(
            "PRIMARY NAVIGATION",
            PAGES,
            index=default_index,
            label_visibility="visible"
        )
        st.session_state["nav_selection"] = selected_page

        st.markdown("""
        <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #E2E8F0; font-size: 0.72rem; color: #94A3B8;">
            <div><strong>Runtime Engine:</strong> Python 3.13 / FastAPI</div>
            <div><strong>Datastores:</strong> PostgreSQL 16 & Redis 7.2</div>
            <div><strong>Orchestration:</strong> Apache Airflow 2.9</div>
            <div><strong>Lineage:</strong> OpenLineage v1 Spec</div>
            <div style="margin-top: 8px; font-weight: 600; color: #64748B;">v3.1.0 • Verified Production</div>
        </div>
        """, unsafe_allow_html=True)

    return selected_page, demo_mode
