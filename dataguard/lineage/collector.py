"""
DataGuard OpenLineage Collector & Airflow Integration Interface.
Provides unified lifecycle methods (start_run, complete_run, fail_run) and emits
standardized OpenLineage RunEvents into the LineageRepository while updating Prometheus metrics.
"""

import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from dataguard.lineage.models import (
    LineageStatus,
    LineageRun,
)
from dataguard.lineage.events import (
    RunEvent,
    Run,
    Job,
    InputDataset,
    OutputDataset,
    ColumnLineageDatasetFacet,
    ColumnLineageField,
    ColumnLineageInputField
)
from dataguard.lineage.repository import LineageRepository
from dataguard.lineage.column_lineage import build_column_lineage_facet
from dataguard.metrics import (
    LINEAGE_EVENTS_TOTAL,
    LINEAGE_EVENT_FAILURES_TOTAL,
    LINEAGE_RUNS_TOTAL,
    LINEAGE_FAILED_RUNS_TOTAL,
    LINEAGE_DATASETS_TOTAL,
    LINEAGE_EDGES_TOTAL,
    LINEAGE_PROCESSING_DURATION_SECONDS
)


class LineageCollector:
    """
    Core collector interface designed for pipeline automation and Airflow DAGs.
    """

    def __init__(self, repository: Optional[LineageRepository] = None):
        self.repository = repository or LineageRepository()

    def _update_metrics_safe(self, ev_type: str, pipeline_id: str, is_fail: bool = False, duration: float = 0.0):
        try:
            LINEAGE_EVENTS_TOTAL.labels(event_type=ev_type, pipeline_id=pipeline_id).inc()
            LINEAGE_PROCESSING_DURATION_SECONDS.labels(event_type=ev_type).observe(duration)
            if is_fail:
                LINEAGE_FAILED_RUNS_TOTAL.labels(pipeline_id=pipeline_id).inc()
            
            # Update gauges
            counts = self.repository.get_counts()
            LINEAGE_DATASETS_TOTAL.set(counts.get("datasets", 0))
            LINEAGE_EDGES_TOTAL.set(counts.get("edges", 0))
        except Exception:
            pass

    def emit_event(self, event: RunEvent) -> LineageRun:
        """
        Directly ingests an OpenLineage RunEvent and records metrics.
        """
        start_t = time.perf_counter()
        pipeline_id = event.job.name
        ev_type = event.eventType.upper()
        try:
            run = self.repository.ingest_openlineage_event(event)
            duration = time.perf_counter() - start_t
            is_fail = (ev_type == "FAIL")
            self._update_metrics_safe(ev_type, pipeline_id, is_fail=is_fail, duration=duration)
            try:
                LINEAGE_RUNS_TOTAL.labels(pipeline_id=pipeline_id, status=ev_type).inc()
            except Exception:
                pass
            return run
        except Exception as e:
            try:
                LINEAGE_EVENT_FAILURES_TOTAL.labels(pipeline_id=pipeline_id).inc()
            except Exception:
                pass
            raise e

    def start_run(
        self,
        pipeline_id: str,
        inputs: List[str],
        job_name: Optional[str] = None,
        namespace: str = "default",
        run_id: Optional[str] = None,
        facets: Optional[Dict[str, Any]] = None
    ) -> LineageRun:
        """
        Airflow / Pipeline hook: records the start of a pipeline run.
        """
        r_id = run_id or f"run_{uuid.uuid4().hex[:16]}"
        j_name = job_name or pipeline_id

        input_objs: List[InputDataset] = []
        for inp in inputs:
            ns = "postgres" if inp.startswith("postgres.") else namespace
            nm = inp.replace("postgres.", "")
            input_objs.append(InputDataset(namespace=ns, name=nm))

        event = RunEvent(
            eventType="START",
            eventTime=datetime.now(timezone.utc).isoformat(),
            run=Run(runId=r_id, facets=facets or {}),
            job=Job(namespace=namespace, name=j_name, facets={"pipeline_id": pipeline_id}),
            inputs=input_objs,
            outputs=[]
        )

        return self.emit_event(event)

    def complete_run(
        self,
        run_id: str,
        outputs: List[str],
        pipeline_id: Optional[str] = None,
        job_name: Optional[str] = None,
        namespace: str = "default",
        column_mappings: Optional[List[Dict[str, str]]] = None,
        facets: Optional[Dict[str, Any]] = None
    ) -> LineageRun:
        """
        Airflow / Pipeline hook: records successful completion of a pipeline run.
        """
        j_name = job_name or pipeline_id or "default_pipeline"
        pipe_id = pipeline_id or j_name

        existing_run = self.repository.get_run(run_id)
        input_names = existing_run.inputs if existing_run else []

        input_objs = [
            InputDataset(
                namespace="postgres" if inp.startswith("postgres.") else namespace,
                name=inp.replace("postgres.", "")
            )
            for inp in input_names
        ]

        output_objs: List[OutputDataset] = []
        for out in outputs:
            ns = "redis" if out.startswith("redis.") else namespace
            nm = out.replace("redis.", "")

            # If column mappings provided or available from catalog, attach columnLineage facet
            col_facet = None
            if column_mappings:
                fields_dict: Dict[str, ColumnLineageField] = {}
                for m in column_mappings:
                    if m.get("target_dataset") in (out, nm):
                        src_ds = m.get("source_dataset", "")
                        fields_dict[m["target_column"]] = ColumnLineageField(
                            inputFields=[
                                ColumnLineageInputField(
                                    namespace="postgres" if src_ds.startswith("postgres.") else "default",
                                    name=src_ds.replace("postgres.", ""),
                                    field=m["source_column"]
                                )
                            ],
                            transformationDescription=m.get("transformation", "TRANSFORM"),
                            transformationType="TRANSFORMATION"
                        )
                if fields_dict:
                    col_facet = ColumnLineageDatasetFacet(fields=fields_dict)
            else:
                col_facet = build_column_lineage_facet(target_dataset=out, pipeline=pipe_id)

            facets_dict: Dict[str, Any] = {}
            if col_facet and col_facet.fields:
                facets_dict["columnLineage"] = col_facet.model_dump() if hasattr(col_facet, "model_dump") else col_facet.dict()

            output_objs.append(OutputDataset(
                namespace=ns,
                name=nm,
                facets=facets_dict
            ))

        run_facets = existing_run.facets if existing_run else {}
        if facets:
            run_facets.update(facets)

        event = RunEvent(
            eventType="COMPLETE",
            eventTime=datetime.now(timezone.utc).isoformat(),
            run=Run(runId=run_id, facets=run_facets),
            job=Job(namespace=namespace, name=j_name, facets={"pipeline_id": pipe_id}),
            inputs=input_objs,
            outputs=output_objs
        )

        return self.emit_event(event)

    def fail_run(
        self,
        run_id: str,
        pipeline_id: Optional[str] = None,
        job_name: Optional[str] = None,
        namespace: str = "default",
        error_message: Optional[str] = None,
        facets: Optional[Dict[str, Any]] = None
    ) -> LineageRun:
        """
        Airflow / Pipeline hook: records failure of a pipeline run.
        """
        j_name = job_name or pipeline_id or "default_pipeline"

        existing_run = self.repository.get_run(run_id)
        input_names = existing_run.inputs if existing_run else []

        input_objs = [
            InputDataset(
                namespace="postgres" if inp.startswith("postgres.") else namespace,
                name=inp.replace("postgres.", "")
            )
            for inp in input_names
        ]

        run_facets = existing_run.facets if existing_run else {}
        if facets:
            run_facets.update(facets)
        if error_message:
            run_facets["errorMessage"] = {
                "message": error_message,
                "programmingLanguage": "PYTHON"
            }

        event = RunEvent(
            eventType="FAIL",
            eventTime=datetime.now(timezone.utc).isoformat(),
            run=Run(runId=run_id, facets=run_facets),
            job=Job(namespace=namespace, name=j_name, facets={"pipeline_id": pipeline_id or j_name}),
            inputs=input_objs,
            outputs=[]
        )

        return self.emit_event(event)
