"""
DataGuard OpenLineage Domain Models.
Defines entity models for datasets, jobs, runs, edges, and column-level lineage.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class LineageStatus(str, Enum):
    START = "START"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"
    ABORT = "ABORT"


class LineageDataset(BaseModel):
    dataset_id: str
    namespace: str = "default"
    name: str
    description: Optional[str] = None
    schema_facets: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class LineageJob(BaseModel):
    job_id: str
    namespace: str = "default"
    name: str
    pipeline_id: str
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class LineageRun(BaseModel):
    run_id: str
    job_id: str
    pipeline_id: str
    status: LineageStatus
    start_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = None
    inputs: List[str] = []
    outputs: List[str] = []
    facets: Dict[str, Any] = {}
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class LineageEdge(BaseModel):
    edge_id: str
    run_id: str
    source_dataset: str
    target_dataset: str
    pipeline_id: str
    edge_type: str = "DATA_FLOW"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class ColumnLineageMapping(BaseModel):
    column_edge_id: str
    run_id: str
    source_dataset: str
    source_column: str
    target_dataset: str
    target_column: str
    transformation: str
    pipeline_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class ColumnLineageDetail(BaseModel):
    target_column: str
    source_columns: List[Dict[str, str]]
    transformation: str
    pipeline: str
    run_id: str

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class LineageGraphNode(BaseModel):
    id: str
    name: str
    type: str  # "dataset" | "pipeline" | "model" | "service"
    namespace: str = "default"
    metadata: Dict[str, Any] = {}

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class LineageGraphEdge(BaseModel):
    source: str
    target: str
    pipeline_id: Optional[str] = None
    run_id: Optional[str] = None
    edge_type: str = "DATA_FLOW"

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class LineageGraphResponse(BaseModel):
    nodes: List[LineageGraphNode]
    edges: List[LineageGraphEdge]
    total_nodes: int
    total_edges: int


class DatasetLineageSummary(BaseModel):
    dataset: str
    namespace: str
    producing_pipelines: List[str] = []
    consuming_pipelines: List[str] = []
    upstream_datasets: List[str] = []
    downstream_datasets: List[str] = []
    latest_run_id: Optional[str] = None
    last_updated: Optional[str] = None


class UpstreamLineageResponse(BaseModel):
    dataset: str
    upstream_datasets: List[str]
    pipelines: List[str]
    depth: int


class DownstreamLineageResponse(BaseModel):
    dataset: str
    downstream_datasets: List[str]
    pipelines: List[str]
    depth: int
