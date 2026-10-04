"""
FeatureHub + DataGuard Integrated Platform Models (Phase I).
Defines schemas for the complete end-to-end data platform flow:
Raw Ingestion -> Computation -> Contracts -> Diff -> Quality -> Lineage -> Offline -> Redis -> ML Inference.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class IntegrationStage(str, Enum):
    DATA_SOURCE = "DATA_SOURCE"
    FEATURE_COMPUTATION = "FEATURE_COMPUTATION"
    CONTRACT_VALIDATION = "CONTRACT_VALIDATION"
    SCHEMA_VALIDATION = "SCHEMA_VALIDATION"
    DATA_QUALITY = "DATA_QUALITY"
    OPENLINEAGE = "OPENLINEAGE"
    AIRFLOW_ORCHESTRATION = "AIRFLOW_ORCHESTRATION"
    OFFLINE_STORE = "OFFLINE_STORE"
    MATERIALIZATION = "MATERIALIZATION"
    REDIS_ONLINE_STORE = "REDIS_ONLINE_STORE"
    FEATUREHUB_API = "FEATUREHUB_API"
    ML_PREDICTION = "ML_PREDICTION"


class StageStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class IntegrationStageResult(BaseModel):
    stage: IntegrationStage
    status: StageStatus
    duration_ms: float = 0.0
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class IntegratedPipelineResult(BaseModel):
    pipeline_id: str
    run_id: str
    status: StageStatus
    dataset_name: str
    stages: List[IntegrationStageResult] = Field(default_factory=list)
    features_computed_count: int = 0
    records_materialized_count: int = 0
    quality_score: Optional[float] = None
    schema_compatible: bool = True
    openlineage_run_id: Optional[str] = None
    incident_id: Optional[str] = None
    incident_owner: Optional[str] = None
    incident_severity: Optional[str] = None
    ml_prediction: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def get_stage(self, stage: IntegrationStage) -> Optional[IntegrationStageResult]:
        for s in self.stages:
            if s.stage == stage:
                return s
        return None
