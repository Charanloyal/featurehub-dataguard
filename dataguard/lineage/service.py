"""
DataGuard OpenLineage Service Facade.
Coordinates event collection, persistent storage, and graph/column lineage traversal.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path

from dataguard.lineage.models import (
    LineageRun,
    LineageGraphResponse,
    DatasetLineageSummary,
    UpstreamLineageResponse,
    DownstreamLineageResponse,
    ColumnLineageDetail
)
from dataguard.lineage.events import RunEvent
from dataguard.lineage.repository import LineageRepository
from dataguard.lineage.collector import LineageCollector


def _to_dict(model: Any) -> Dict[str, Any]:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)


class LineageService:
    """
    DataGuard Lineage API Service facade.
    Backed by PostgreSQL LineageRepository and LineageCollector.
    """

    def __init__(
        self,
        repository: Optional[LineageRepository] = None,
        db_url: Optional[str] = None,
        db_path: Optional[Path] = None
    ):
        if repository is not None:
            self.repository = repository
        else:
            self.repository = LineageRepository(db_url=db_url, db_path=db_path)
        self.collector = LineageCollector(repository=self.repository)

    def get_lineage_graph(self) -> Dict[str, Any]:
        """
        Dynamically returns full graph topology (nodes & edges) from PostgreSQL lineage metadata.
        """
        graph = self.repository.get_graph()
        return _to_dict(graph)

    def get_dataset_lineage(self, dataset: str) -> Optional[Dict[str, Any]]:
        """
        Returns complete lineage summary for a specific dataset.
        """
        summary = self.repository.get_dataset_summary(dataset)
        return _to_dict(summary) if summary else None

    def get_upstream(self, dataset: str, depth: int = 5) -> Dict[str, Any]:
        """
        Traverses upstream dependencies feeding into the dataset.
        """
        res = self.repository.get_upstream(dataset, max_depth=depth)
        return _to_dict(res)

    def get_downstream(self, dataset: str, depth: int = 5) -> Dict[str, Any]:
        """
        Traverses downstream dependencies consuming the dataset.
        """
        res = self.repository.get_downstream(dataset, max_depth=depth)
        return _to_dict(res)

    def get_column_lineage(self, dataset: str, column: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns column-level lineage details for target dataset.
        """
        cols = self.repository.get_column_lineage(dataset, target_column=column)
        return [_to_dict(c) for c in cols]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single pipeline run by run_id.
        """
        run = self.repository.get_run(run_id)
        return _to_dict(run) if run else None

    def get_pipeline_runs(self, pipeline_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lists chronological runs for a specific pipeline.
        """
        runs = self.repository.get_runs_for_pipeline(pipeline_id, limit=limit)
        return [_to_dict(r) for r in runs]

    def ingest_event(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingests an OpenLineage RunEvent payload into PostgreSQL.
        """
        event = RunEvent(**event_payload)
        run = self.collector.emit_event(event)
        return _to_dict(run)

    def start_pipeline_run(
        self,
        pipeline_id: str,
        inputs: List[str],
        job_name: Optional[str] = None,
        namespace: str = "default",
        run_id: Optional[str] = None,
        facets: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        run = self.collector.start_run(
            pipeline_id=pipeline_id,
            inputs=inputs,
            job_name=job_name,
            namespace=namespace,
            run_id=run_id,
            facets=facets
        )
        return _to_dict(run)

    def complete_pipeline_run(
        self,
        run_id: str,
        outputs: List[str],
        pipeline_id: Optional[str] = None,
        column_mappings: Optional[List[Dict[str, str]]] = None,
        facets: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        run = self.collector.complete_run(
            run_id=run_id,
            outputs=outputs,
            pipeline_id=pipeline_id,
            column_mappings=column_mappings,
            facets=facets
        )
        return _to_dict(run)

    def fail_pipeline_run(
        self,
        run_id: str,
        pipeline_id: Optional[str] = None,
        error_message: Optional[str] = None,
        facets: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        run = self.collector.fail_run(
            run_id=run_id,
            pipeline_id=pipeline_id,
            error_message=error_message,
            facets=facets
        )
        return _to_dict(run)
