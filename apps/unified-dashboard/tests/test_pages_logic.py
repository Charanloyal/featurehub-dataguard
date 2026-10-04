"""
Tests for Dashboard Components & Logic
Validates formatting functions, chart generation, decision banners, and badge rendering.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.unified_dashboard.utils.formatting import (
    format_ms,
    format_number,
    format_percentage,
    format_timestamp
)
from apps.unified_dashboard.utils.chart_helpers import (
    create_quality_trend_chart,
    create_stage_latency_chart,
    create_incident_distribution_chart
)
from apps.unified_dashboard.components.banners import get_status_badge_html


class TestFormattingUtils:
    def test_format_ms(self):
        assert format_ms(0.89) == "0.89 ms"
        assert format_ms(5343.79) == "5.34 s"
        assert format_ms(None) == "N/A"

    def test_format_number(self):
        assert format_number(3672) == "3,672"
        assert format_number(122) == "122"
        assert format_number(None) == "0"

    def test_format_percentage(self):
        assert format_percentage(98.64) == "98.6%"
        assert format_percentage(100.0) == "100.0%"
        assert format_percentage(None) == "0.0%"

    def test_format_timestamp(self):
        dt = datetime(2026, 10, 4, 10, 30, 0, tzinfo=timezone.utc)
        assert "2026-10-04" in format_timestamp(dt)
        assert "2026-10-02" in format_timestamp("2026-10-02T12:00:00Z")
        assert format_timestamp(None) == "N/A"


class TestChartHelpers:
    def test_create_quality_trend_chart(self):
        sample_runs = [
            {"timestamp": "2026-10-04T08:00:00Z", "success_rate": 100.0},
            {"timestamp": "2026-10-04T09:00:00Z", "success_rate": 95.0}
        ]
        fig = create_quality_trend_chart(sample_runs)
        assert fig is not None
        assert hasattr(fig, "to_dict")

    def test_create_stage_latency_chart(self):
        stages = {
            "FEATURE_COMPUTATION": {"mean_ms": 557.35},
            "DATA_QUALITY": {"mean_ms": 271.25},
            "MATERIALIZATION": {"mean_ms": 4225.74}
        }
        fig = create_stage_latency_chart(stages)
        assert fig is not None
        assert hasattr(fig, "to_dict")

    def test_create_incident_distribution_chart(self):
        incidents = [
            {"severity": "CRITICAL"},
            {"severity": "CRITICAL"},
            {"severity": "HIGH"},
            {"severity": "MEDIUM"}
        ]
        fig = create_incident_distribution_chart(incidents)
        assert fig is not None
        assert hasattr(fig, "to_dict")


class TestStatusBadges:
    def test_status_badge_html(self):
        html_healthy = get_status_badge_html("HEALTHY")
        assert "status-healthy" in html_healthy
        assert "HEALTHY" in html_healthy

        html_failed = get_status_badge_html("FAILED")
        assert "status-down" in html_failed
        assert "FAILED" in html_failed

        html_warning = get_status_badge_html("WARNING")
        assert "status-warning" in html_warning
        assert "WARNING" in html_warning
