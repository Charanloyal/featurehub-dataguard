"""
Decision Banners & Status Badges Component
Renders accessible decision banners and status badges for schema diffs, CI gates, and pipeline health.
"""

import streamlit as st
from typing import Optional


def render_decision_banner(verdict: str, message: Optional[str] = None, details: Optional[str] = None):
    """
    Renders high-visibility decision banners for Schema Compatibility & CI/CD Gates.
    Compatible with: SAFE, WARNING, BREAKING.
    """
    verdict_upper = (verdict or "SAFE").upper()

    if verdict_upper in ["SAFE", "COMPATIBLE", "PASS"]:
        cls_name = "decision-safe"
        icon = "✅"
        title = "COMPATIBLE — SAFE TO MERGE & MATERIALIZE"
        default_msg = "No breaking schema changes detected. Backward compatibility verified against production baseline."
    elif verdict_upper in ["WARNING", "REVIEW_REQUIRED"]:
        cls_name = "decision-warning"
        icon = "⚠️"
        title = "REVIEW REQUIRED — NON-BREAKING CHANGES DETECTED"
        default_msg = "Additive schema modifications or new nullable columns detected. Manual review recommended."
    else:  # BREAKING, FAILED, BLOCK
        cls_name = "decision-breaking"
        icon = "❌"
        title = "MERGE BLOCKED — BREAKING CHANGES DETECTED"
        default_msg = "Breaking schema drift or deleted columns detected. Fast-fail circuit breaker triggered to protect Redis and downstream ML models."

    msg = message or default_msg
    html = f"""
    <div class="decision-banner {cls_name}">
        <div style="font-size: 2.2rem; line-height: 1;">{icon}</div>
        <div style="flex-grow: 1;">
            <div style="font-weight: 800; font-size: 1.15rem; letter-spacing: -0.01em;">{title}</div>
            <div style="font-size: 0.9rem; margin-top: 4px; opacity: 0.95;">{msg}</div>
            {f'<div style="font-size: 0.8rem; margin-top: 6px; font-family: monospace; background: rgba(0,0,0,0.05); padding: 4px 8px; border-radius: 4px;">{details}</div>' if details else ''}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def get_status_badge_html(status: str) -> str:
    """Generate accessible HTML for status badges."""
    st_upper = (status or "UNKNOWN").upper()
    status_type = "info"

    if st_upper in ["SUCCESS", "HEALTHY", "SAFE", "RESOLVED", "UP"]:
        status_type = "healthy"
        icon = "●"
    elif st_upper in ["WARNING", "DEGRADED", "REVIEW", "ACKNOWLEDGED", "SLOW"]:
        status_type = "warning"
        icon = "▲"
    elif st_upper in ["FAILED", "DOWN", "BREAKING", "CRITICAL", "OPEN", "BLOCKED"]:
        status_type = "down"
        icon = "■"
    elif st_upper in ["SKIPPED", "INFO", "STANDBY"]:
        status_type = "info"
        icon = "○"

    return f"<span class='status-pill status-{status_type}'><span>{icon}</span> {st_upper}</span>"
