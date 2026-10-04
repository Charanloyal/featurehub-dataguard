"""
Metric Cards Component
Renders accessible, responsive metric cards with icons, subtitles, and status indicators.
"""

import streamlit as st
from typing import Optional, List, Dict, Any


def render_metric_card(
    title: str,
    value: Any,
    subtitle: Optional[str] = None,
    icon: Optional[str] = None,
    status_pill: Optional[str] = None,
    status_type: str = "info"
):
    """Render a single styled metric card."""
    icon_html = f"<span style='margin-right: 6px;'>{icon}</span>" if icon else ""
    pill_html = ""
    if status_pill:
        pill_html = f"<span class='status-pill status-{status_type.lower()}'>{status_pill}</span>"

    html = f"""
    <div class="platform-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div class="card-title">{icon_html}{title}</div>
            {pill_html}
        </div>
        <div class="card-value">{value}</div>
        {f'<div class="card-subtitle">{subtitle}</div>' if subtitle else ''}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_kpi_row(cards: List[Dict[str, Any]]):
    """Render a horizontal row of metric cards evenly distributed."""
    cols = st.columns(len(cards))
    for i, card in enumerate(cards):
        with cols[i]:
            render_metric_card(
                title=card.get("title", ""),
                value=card.get("value", ""),
                subtitle=card.get("subtitle"),
                icon=card.get("icon"),
                status_pill=card.get("status_pill"),
                status_type=card.get("status_type", "info")
            )
