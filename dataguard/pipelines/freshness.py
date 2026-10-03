"""
DataGuard Dataset Freshness Monitoring Service (Phase G).
Dynamically evaluates datasets against configured freshness SLAs,
identifies stale data, emits Prometheus alerts, and generates incidents on SLA breaches.
"""

import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pandas as pd

from dataguard.contracts.registry import ContractRegistryService
from dataguard.incidents.manager import IncidentManager
from dataguard.quality.models import QualityCheckResult, QualityStatus
from dataguard.quality.datasets import DatasetCatalog
from dataguard.metrics import PIPELINE_STALE_TOTAL


class FreshnessEvaluationResult:
    def __init__(
        self,
        dataset: str,
        is_fresh: bool,
        sla_minutes: int,
        delay_minutes: float,
        last_updated: datetime,
        checked_at: datetime,
        incident_created: bool = False,
        incident_id: Optional[str] = None
    ):
        self.dataset = dataset
        self.is_fresh = is_fresh
        self.sla_minutes = sla_minutes
        self.delay_minutes = delay_minutes
        self.last_updated = last_updated
        self.checked_at = checked_at
        self.incident_created = incident_created
        self.incident_id = incident_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "status": "FRESH" if self.is_fresh else "STALE",
            "is_fresh": self.is_fresh,
            "sla_minutes": self.sla_minutes,
            "delay_minutes": round(self.delay_minutes, 2),
            "last_updated": self.last_updated.isoformat(),
            "checked_at": self.checked_at.isoformat(),
            "incident_created": self.incident_created,
            "incident_id": self.incident_id
        }


class FreshnessMonitorService:
    """
    Evaluates real dataset recency against declared contract SLAs.
    """

    def __init__(
        self,
        registry_service: Optional[ContractRegistryService] = None,
        incident_manager: Optional[IncidentManager] = None
    ):
        self.registry = registry_service or ContractRegistryService()
        self.incident_manager = incident_manager or IncidentManager()

    def evaluate_dataset_freshness(
        self,
        dataset_name: str,
        df: Optional[pd.DataFrame] = None,
        pipeline_id: str = "freshness_monitoring_pipeline",
        sla_override_minutes: Optional[int] = None,
        force_stale: bool = False
    ) -> FreshnessEvaluationResult:
        """
        Calculates delta between now and latest dataset update.
        Triggers an incident if the delay exceeds SLA limits.
        """
        now = datetime.now(timezone.utc)

        # 1. Resolve SLA from contract or default
        sla_minutes = sla_override_minutes
        contract_data = None
        try:
            contract_data = self.registry.get_contract(dataset_name)
            if sla_minutes is None and contract_data:
                sla_val = contract_data.get("freshness_sla") or contract_data.get("sla", {}).get("freshness")
                if isinstance(sla_val, str) and sla_val.endswith("m"):
                    sla_minutes = int(sla_val[:-1])
                elif isinstance(sla_val, (int, float)):
                    sla_minutes = int(sla_val)
        except Exception:
            pass

        if not sla_minutes:
            sla_minutes = 60

        # 2. Determine actual last update time
        last_updated: Optional[datetime] = None

        if force_stale:
            # Deterministic stale test scenario: simulate last updated 2 hours ago
            last_updated = datetime.fromtimestamp(now.timestamp() - (sla_minutes * 60 + 3600), tz=timezone.utc)
        else:
            # Inspect DataFrame or physical file
            if df is not None:
                # Look for datetime columns
                date_cols = [c for c in df.columns if any(k in c.lower() for k in ["timestamp", "time", "date", "created", "updated"])]
                if date_cols:
                    for col in date_cols:
                        try:
                            series = pd.to_datetime(df[col], errors="coerce").dropna()
                            if not series.empty:
                                max_ts = series.max()
                                if hasattr(max_ts, "to_pydatetime"):
                                    max_dt = max_ts.to_pydatetime()
                                    if max_dt.tzinfo is None:
                                        max_dt = max_dt.replace(tzinfo=timezone.utc)
                                    last_updated = max_dt
                                    break
                        except Exception:
                            continue

            # Fallback to physical file mtime if available
            if last_updated is None:
                file_path = DatasetCatalog.get_dataset_path(dataset_name)
                if file_path and os.path.exists(file_path):
                    mtime = os.path.getmtime(file_path)
                    last_updated = datetime.fromtimestamp(mtime, tz=timezone.utc)

        # Ultimate fallback
        if last_updated is None:
            last_updated = now

        # Ensure tz-aware
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)

        delay_seconds = (now - last_updated).total_seconds()
        delay_minutes = max(0.0, delay_seconds / 60.0)

        is_fresh = delay_minutes <= sla_minutes
        incident_created = False
        incident_id = None

        if not is_fresh:
            PIPELINE_STALE_TOTAL.labels(pipeline_id=pipeline_id, dataset=dataset_name).inc()

            # Create incident for SLA violation
            check_result = QualityCheckResult(
                check_name=f"freshness_sla_{dataset_name}",
                column=None,
                expectation_type="expect_dataset_to_be_fresh",
                status=QualityStatus.FAIL,
                success=False,
                observed_value=f"Delay: {delay_minutes:.1f} mins (exceeds SLA {sla_minutes} mins)",
                expected_value=f"<= {sla_minutes} mins",
                details={"sla_minutes": sla_minutes, "delay_minutes": delay_minutes}
            )

            incident = self.incident_manager.handle_check_failure(
                check=check_result,
                dataset=dataset_name,
                pipeline=pipeline_id,
                contract=contract_data
            )
            if incident:
                incident_created = True
                incident_id = incident.incident_id

        return FreshnessEvaluationResult(
            dataset=dataset_name,
            is_fresh=is_fresh,
            sla_minutes=sla_minutes,
            delay_minutes=delay_minutes,
            last_updated=last_updated,
            checked_at=now,
            incident_created=incident_created,
            incident_id=incident_id
        )
