"""
DataGuard Pipeline Orchestration Models (Phase G).
Defines schemas for pipeline configurations, execution runs, metrics, and health status.
"""

from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class PipelineStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DEPRECATED = "DEPRECATED"


class PipelineRunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class PipelineConfig(BaseModel):
    pipeline_id: str
    name: str
    owner: str
    dataset: str
    contract: str
    freshness_sla_minutes: int = 60
    description: Optional[str] = None
    schedule: Optional[str] = None
    status: PipelineStatus = PipelineStatus.ACTIVE
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None


class PipelineRun(BaseModel):
    run_id: str
    pipeline_id: str
    dataset: str
    status: PipelineRunStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    quality_run_id: Optional[str] = None
    incident_id: Optional[str] = None
    lineage_run_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class PipelineSummary(BaseModel):
    total_pipelines: int
    active_pipelines: int
    successful_pipelines: int
    failed_pipelines: int
    running_pipelines: int
    stale_pipelines: int
    total_runs: int
    failed_runs: int
    success_rate: float


class PipelineHealth(BaseModel):
    pipeline_id: str
    status: str
    is_healthy: bool
    freshness_status: str
    last_run: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = None
    active_incidents: int = 0
