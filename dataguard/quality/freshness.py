"""
DataGuard Freshness Validation Engine.
Calculates real timestamp latencies against contract freshness SLAs.
Deterministically classifies state into FRESH, WARNING, or STALE.
"""

import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List, Union

from dataguard.quality.models import FreshnessStatus


class FreshnessValidator:
    """
    Evaluates dataset freshness by computing latency between current clock
    and the latest record timestamp, measured against contract freshness_sla_minutes.
    """

    TIMESTAMP_CANDIDATES = [
        "timestamp",
        "created_at",
        "detected_at",
        "executed_at",
        "settled_at",
        "event_time",
        "updated_at",
        "observed_at"
    ]

    @classmethod
    def find_timestamp_column(cls, df: pd.DataFrame, contract: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Identifies the primary timestamp column from contract spec or dataframe columns."""
        if contract:
            for col in contract.get("columns", []):
                if str(col.get("type", "")).lower() == "timestamp" and col.get("name") in df.columns:
                    return col["name"]

        for cand in cls.TIMESTAMP_CANDIDATES:
            if cand in df.columns:
                return cand

        # Fallback: check any column with datetime dtype
        for col_name in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col_name]):
                return col_name

        return None

    @classmethod
    def evaluate_freshness(
        cls,
        df: pd.DataFrame,
        contract: Optional[Union[Dict[str, Any], int]] = None,
        sla_minutes: Optional[int] = None,
        timestamp_col: Optional[str] = None,
        reference_time: Optional[datetime] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculates freshness delay = reference_time - max(timestamp).
        Classifies into FRESH, WARNING, or STALE based on contract SLA.
        """
        # Handle positional arg polymorphism
        active_contract = None
        active_sla = None

        if isinstance(contract, dict):
            active_contract = contract
            active_sla = sla_minutes or contract.get("freshness_sla_minutes")
        elif isinstance(contract, (int, float)):
            active_sla = int(contract)
            active_contract = kwargs.get("contract")
        else:
            active_contract = kwargs.get("contract")
            active_sla = sla_minutes

        now = reference_time or datetime.now(timezone.utc)
        effective_sla = active_sla or (active_contract.get("freshness_sla_minutes") if active_contract else 60) or 60

        col = timestamp_col or cls.find_timestamp_column(df, active_contract)
        if not col or len(df) == 0:
            return {
                "status": FreshnessStatus.UNKNOWN,
                "delay_minutes": None,
                "sla_minutes": effective_sla,
                "last_record_timestamp": None,
                "column_used": col,
                "message": "No valid timestamp column found or dataset is empty."
            }

        try:
            # Parse series to datetime with UTC timezone
            ts_series = pd.to_datetime(df[col], utc=True, errors="coerce")
            max_ts = ts_series.max()

            if pd.isnull(max_ts):
                return {
                    "status": FreshnessStatus.UNKNOWN,
                    "delay_minutes": None,
                    "sla_minutes": effective_sla,
                    "last_record_timestamp": None,
                    "column_used": col,
                    "message": f"Column '{col}' has no valid parseable timestamps."
                }

            # Convert to python datetime with UTC
            max_dt = max_ts.to_pydatetime()
            if max_dt.tzinfo is None:
                max_dt = max_dt.replace(tzinfo=timezone.utc)

            delay_seconds = (now - max_dt).total_seconds()
            # If records are in the future or within negative threshold (clock skew), treat as 0
            delay_minutes = max(0.0, delay_seconds / 60.0)

            # Classification policy:
            # - delay <= SLA: FRESH
            # - SLA < delay <= 2 * SLA: WARNING (approaching staleness)
            # - delay > 2 * SLA: STALE (unacceptable latency)
            if delay_minutes <= effective_sla:
                status = FreshnessStatus.FRESH
                msg = f"Dataset is FRESH. Latency is {delay_minutes:.1f}m (SLA: {effective_sla}m)."
            elif delay_minutes <= effective_sla * 2.0:
                status = FreshnessStatus.WARNING
                msg = f"Dataset freshness is at WARNING. Latency is {delay_minutes:.1f}m (exceeds SLA {effective_sla}m)."
            else:
                status = FreshnessStatus.STALE
                msg = f"Dataset is STALE. Latency is {delay_minutes:.1f}m (exceeds SLA {effective_sla}m by >2x)."

            return {
                "status": status,
                "delay_minutes": round(delay_minutes, 2),
                "sla_minutes": effective_sla,
                "last_record_timestamp": max_dt.isoformat(),
                "column_used": col,
                "message": msg
            }

        except Exception as e:
            return {
                "status": FreshnessStatus.UNKNOWN,
                "delay_minutes": None,
                "sla_minutes": effective_sla,
                "last_record_timestamp": None,
                "column_used": col,
                "message": f"Error computing freshness: {e}"
            }
