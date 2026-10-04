"""
Page 14: Platform Infrastructure & Subsystem Health
Continuous health monitoring across PostgreSQL, Redis, Airflow, FeatureHub API, DataGuard API, and Prometheus.
"""

import streamlit as st
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.health_widget import render_platform_health_widget
from apps.unified_dashboard.components.banners import get_status_badge_html


def render_page(client: PlatformClient, demo_mode: bool = False):
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">🏥 System & Infrastructure Health</div>
        <div class="hero-subtitle">Continuous live diagnostic monitoring across all 6 production subsystems</div>
    </div>
    """, unsafe_allow_html=True)

    if demo_mode:
        st.info("🎯 **Live Infrastructure Verification:** Health status, socket responsiveness, and latency are evaluated directly against running container ports and local services. Zero hardcoded mock statuses.")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("Monitor status, response latency, and connectivity state across datastores and APIs.")
    with col2:
        refresh = st.button("🔄 Refresh Health Diagnostics", use_container_width=True)

    # Perform real health checks
    checks = client.get_system_health()

    # Top summary metrics
    total_services = len(checks)
    healthy_services = sum(1 for c in checks if c.get("status") == "HEALTHY")
    degraded_services = sum(1 for c in checks if c.get("status") == "DEGRADED")
    down_services = sum(1 for c in checks if c.get("status") == "DOWN")

    hcol1, hcol2, hcol3 = st.columns(3)
    with hcol1:
        st.metric("Healthy Subsystems", f"{healthy_services} / {total_services}")
    with hcol2:
        st.metric("Degraded", f"{degraded_services}")
    with hcol3:
        st.metric("Offline / Down", f"{down_services}")

    st.markdown("<hr style='margin: 16px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # Render full detailed health table
    render_platform_health_widget(checks, compact=False)

    # Detailed Subsystem Cards
    st.subheader("Subsystem Diagnostic Reports")
    gcols = st.columns(3)
    for idx, c in enumerate(checks):
        with gcols[idx % 3]:
            st.markdown(f"""
            <div class="platform-card" style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-weight: 700; color: #0F172A; font-size: 0.95rem;">{c.get('service')}</div>
                    <div>{get_status_badge_html(c.get('status'))}</div>
                </div>
                <div style="font-size: 0.8rem; color: #64748B; margin-top: 4px;">Role: {c.get('role')}</div>
                <div style="font-size: 0.8rem; color: #334155; margin-top: 2px;">Endpoint: <code>{c.get('endpoint')}</code></div>
                <div style="font-size: 0.8rem; color: #334155; margin-top: 2px;">Latency: <strong>{c.get('latency_ms', 0):.2f} ms</strong></div>
                <div style="font-size: 0.72rem; color: #94A3B8; margin-top: 8px;">Last verified: {c.get('last_checked')}</div>
            </div>
            """, unsafe_allow_html=True)
