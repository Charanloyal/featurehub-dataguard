"""
Formatting Utilities
Helpers for timestamps, numbers, latencies, and labels.
"""

from datetime import datetime
from typing import Any, Optional


def format_ms(val: Optional[float]) -> str:
    """Format millisecond duration with appropriate scale."""
    if val is None:
        return "N/A"
    if val >= 1000.0:
        return f"{val / 1000.0:.2f} s"
    return f"{val:.2f} ms"


def format_number(val: Optional[int]) -> str:
    """Format integer with thousands separator."""
    if val is None:
        return "0"
    return f"{val:,}"


def format_percentage(val: Optional[float]) -> str:
    """Format float as percentage."""
    if val is None:
        return "0.0%"
    return f"{val:.1f}%"


def format_timestamp(val: Any) -> str:
    """Format various timestamp representations to clean readable UTC string."""
    if not val:
        return "N/A"
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        s = str(val).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(val)[:19]
