"""
DataGuard Data Quality Pydantic Data Models.
Defines typed models for quality expectations, validation results, runs, freshness, and summaries.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class QualityStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class QualitySeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    WARNING = "WARNING"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class QualityCheckResult(BaseModel):
    run_id: str = Field(..., description="Unique validation run ID")
    dataset: str = Field(..., description="Target dataset name")
    check_name: str = Field(..., description="Unique descriptive name for the check")
    column: Optional[str] = Field(None, description="Target column evaluated, if column-level")
    expectation_type: str = Field(..., description="Great Expectations expectation type")
    status: QualityStatus = Field(..., description="Evaluation status: PASS, FAIL, or WARNING")
    severity: QualitySeverity = Field(QualitySeverity.MEDIUM, description="Impact severity classification")
    observed_value: Optional[Any] = Field(None, description="Observed metric value or violation summary")
    expected_value: Optional[Any] = Field(None, description="Expected invariant or threshold")
    success: bool = Field(..., description="True if check passed successfully")
    duration_ms: float = Field(0.0, description="Execution duration of this check in milliseconds")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pipeline: str = Field("default_pipeline", description="Originating data pipeline or ETL stage")
    details: Dict[str, Any] = Field(default_factory=dict, description="Raw Great Expectations diagnostic metadata")

    def __getitem__(self, item: str) -> Any:
        d = self.to_dict()
        if item in d:
            return d[item]
        if hasattr(self, item):
            val = getattr(self, item)
            return val.value if hasattr(val, "value") else val
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return item in self.to_dict() or hasattr(self, item)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "dataset": self.dataset,
            "dataset_name": self.dataset,
            "check_name": self.check_name,
            "column": self.column,
            "column_name": self.column,
            "expectation_type": self.expectation_type,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "severity": self.severity.value if hasattr(self.severity, "value") else str(self.severity),
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "success": self.success,
            "passed": self.success,  # Backwards compatibility
            "details": self.details,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "pipeline": self.pipeline,
        }


class QualityRunResult(BaseModel):
    run_id: str = Field(..., description="Unique run identifier")
    dataset: str = Field(..., description="Evaluated dataset name")
    contract_version: str = Field("v1.0.0", description="Data contract version tag evaluated against")
    pipeline: str = Field("default_pipeline", description="Pipeline identifier")
    overall_status: QualityStatus = Field(..., description="Overall suite status: PASS, FAIL, or WARNING")
    total_checks: int = Field(0, description="Total number of evaluated expectations")
    passed_checks: int = Field(0, description="Number of passed expectation checks")
    failed_checks: int = Field(0, description="Number of failed expectation checks")
    warning_checks: int = Field(0, description="Number of checks resulting in warning")
    quality_score: float = Field(100.0, description="Quality score percentage: (passed / total) * 100")
    duration_ms: float = Field(0.0, description="Total run duration in milliseconds")
    freshness_status: FreshnessStatus = Field(FreshnessStatus.FRESH, description="Dataset freshness status")
    freshness_delay_minutes: Optional[float] = Field(None, description="Calculated freshness delay in minutes")
    last_record_timestamp: Optional[str] = Field(None, description="Timestamp of latest record in dataset")
    executed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    checks: List[QualityCheckResult] = Field(default_factory=list, description="List of individual check results")
    row_count: int = Field(0, description="Row count of evaluated dataset")

    def __getitem__(self, item: str) -> Any:
        d = self.to_dict()
        if item in d:
            return d[item]
        if hasattr(self, item):
            val = getattr(self, item)
            return val.value if hasattr(val, "value") else val
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return item in self.to_dict() or hasattr(self, item)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "validation_id": self.run_id,
            "dataset": self.dataset,
            "dataset_name": self.dataset,
            "contract_version": self.contract_version,
            "pipeline": self.pipeline,
            "overall_status": self.overall_status.value if hasattr(self.overall_status, "value") else str(self.overall_status),
            "status": self.overall_status.value if hasattr(self.overall_status, "value") else str(self.overall_status),
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "warning_checks": self.warning_checks,
            "quality_score": round(self.quality_score, 2),
            "duration_ms": round(self.duration_ms, 2),
            "freshness_status": self.freshness_status.value if hasattr(self.freshness_status, "value") else str(self.freshness_status),
            "freshness_delay_minutes": self.freshness_delay_minutes,
            "last_record_timestamp": self.last_record_timestamp,
            "executed_at": self.executed_at,
            "row_count": self.row_count,
            "checks": [c.to_dict() for c in self.checks]
        }


class QualitySummaryResponse(BaseModel):
    total_datasets: int = Field(..., description="Total datasets known to contract registry")
    datasets_checked: int = Field(..., description="Count of distinct datasets with at least one quality run")
    datasets_passing: int = Field(..., description="Count of datasets whose latest run is PASS")
    datasets_failing: int = Field(..., description="Count of datasets whose latest run is FAIL")
    total_checks: int = Field(..., description="Cumulative count of all evaluated checks")
    checks_passed: int = Field(..., description="Cumulative count of passed checks")
    checks_failed: int = Field(..., description="Cumulative count of failed checks")
    overall_quality_score: float = Field(..., description="Average or aggregate quality score percentage")
    freshness_violations: int = Field(..., description="Count of datasets currently in WARNING or STALE freshness state")
