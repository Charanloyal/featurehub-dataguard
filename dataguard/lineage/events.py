"""
OpenLineage Standard Event Specifications.
Implements OpenLineage JSON schema specifications for runs, jobs, datasets, and facets.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class OpenLineageFacet(BaseModel):
    producer: str = "https://github.com/Charanloyal/featurehub-dataguard"
    schemaURL: Optional[str] = None

    class Config:
        extra = "allow"


class SchemaField(BaseModel):
    name: str
    type: str
    description: Optional[str] = None


class SchemaDatasetFacet(OpenLineageFacet):
    fields: List[SchemaField] = []


class ColumnLineageInputField(BaseModel):
    namespace: str
    name: str
    field: str


class ColumnLineageField(BaseModel):
    inputFields: List[ColumnLineageInputField] = []
    transformationDescription: Optional[str] = None
    transformationType: Optional[str] = None


class ColumnLineageDatasetFacet(OpenLineageFacet):
    fields: Dict[str, ColumnLineageField] = {}


class Dataset(BaseModel):
    namespace: str = "default"
    name: str
    facets: Dict[str, Any] = Field(default_factory=dict)

    def get_column_lineage_facet(self) -> Optional[ColumnLineageDatasetFacet]:
        col_facet = self.facets.get("columnLineage")
        if not col_facet:
            return None
        if isinstance(col_facet, ColumnLineageDatasetFacet):
            return col_facet
        if isinstance(col_facet, dict):
            return ColumnLineageDatasetFacet(**col_facet)
        return None


class InputDataset(Dataset):
    inputFacets: Dict[str, Any] = Field(default_factory=dict)


class OutputDataset(Dataset):
    outputFacets: Dict[str, Any] = Field(default_factory=dict)


class Run(BaseModel):
    runId: str
    facets: Dict[str, Any] = Field(default_factory=dict)


class Job(BaseModel):
    namespace: str = "default"
    name: str
    facets: Dict[str, Any] = Field(default_factory=dict)


class RunEvent(BaseModel):
    eventType: str  # "START" | "RUNNING" | "COMPLETE" | "FAIL" | "ABORT" | "OTHER"
    eventTime: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    run: Run
    job: Job
    inputs: List[InputDataset] = Field(default_factory=list)
    outputs: List[OutputDataset] = Field(default_factory=list)
    producer: str = "https://github.com/Charanloyal/featurehub-dataguard"
    schemaURL: str = "https://openlineage.io/spec/1-0-5/OpenLineage.json#/definitions/RunEvent"

    def to_dict(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return self.dict()
