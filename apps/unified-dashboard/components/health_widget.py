"""
Platform Health Widget Component
Renders live status, latency, and last-checked timestamps across all 6 core subsystems.
"""

import streamlit as st
from typing import List, Dict, Any
from apps.unified_dashboard.components.banners import get_status_badge_html


def render_platform_health_widget(checks: List[Dict[str, Any]], compact: bool = False):
    """Render structured health monitoring table or compact grid."""
    if compact:
        cols = st.columns(len(checks))
        for i, c in enumerate(checks):
            with cols[i]:
                st.markdown(f"""
                <div class="platform-card" style="padding: 12px 14px; text-align: center;">
                    <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase;">
                        {c.get('service')}
                    </div>
                    <div style="margin: 6px 0;">
                        {get_status_badge_html(c.get('status', 'UNKNOWN'))}
                    </div>
                    <div style="font-size: 0.72rem; color: #94A3B8; font-family: monospace;">
                        {c.get('latency_ms', 0.0)}ms
                    </div>
                </div>
                """, unsafe_allow_html=True)
        return

    st.markdown("""
    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; overflow: hidden; margin: 16px 0;">
        <div style="background: #F8FAFC; padding: 12px 18px; border-bottom: 1px solid #E2E8F0; display: flex; justify-content: space-between; align-items: center;">
            <div style="font-weight: 700; font-size: 0.95rem; color: #0F172A;">
                🏥 Infrastructure & Service Health Monitor
            </div>
            <div style="font-size: 0.75rem; color: #64748B;">
                Live Subsystem Verification (Zero Mock Data)
            </div>
        </div>
        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem;">
            <thead>
                <tr style="border-bottom: 1px solid #E2E8F0; background: #F8FAFC; color: #64748B;">
                    <th style="padding: 10px 18px;">Subsystem</th>
                    <th style="padding: 10px 18px;">Platform Role</th>
                    <th style="padding: 10px 18px;">Status</th>
                    <th style="padding: 10px 18px;">Latency</th>
                    <th style="padding: 10px 18px;">Endpoint / Channel</th>
                    <th style="padding: 10px 18px;">Last Checked</th>
                </tr>
            </thead>
            <tbody>
    """, unsafe_allow_html=True)

    rows_html = ""
    for c in checks:
        rows_html += f"""
        <tr style="border-bottom: 1px solid #F1F5F9;">
            <td style="padding: 12px 18px; font-weight: 600; color: #1E293B;">{c.get('service')}</td>
            <td style="padding: 12px 18px; color: #64748B;">{c.get('role', 'Core Component')}</td>
            <td style="padding: 12px 18px;">{get_status_badge_html(c.get('status', 'UNKNOWN'))}</td>
            <td style="padding: 12px 18px; font-family: monospace; font-size: 0.82rem; color: #334155;">{c.get('latency_ms', 0.0):.2f} ms</td>
            <td style="padding: 12px 18px; font-family: monospace; font-size: 0.8rem; color: #64748B;">{c.get('endpoint', 'Active')}</td>
            <td style="padding: 12px 18px; color: #94A3B8; font-size: 0.78rem;">{c.get('last_checked', 'Just now')}</td>
        </tr>
        """

    st.markdown(rows_html + "</tbody></table></div>", unsafe_allow_html=True)
