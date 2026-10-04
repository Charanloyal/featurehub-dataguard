"""
Unified Dashboard Components Package
"""

from apps.unified_dashboard.components.metric_cards import render_metric_card, render_kpi_row
from apps.unified_dashboard.components.banners import render_decision_banner, get_status_badge_html
from apps.unified_dashboard.components.hero_architecture import render_hero_architecture
from apps.unified_dashboard.components.health_widget import render_platform_health_widget
from apps.unified_dashboard.components.navbar import render_sidebar

__all__ = [
    "render_metric_card",
    "render_kpi_row",
    "render_decision_banner",
    "get_status_badge_html",
    "render_hero_architecture",
    "render_platform_health_widget",
    "render_sidebar"
]
