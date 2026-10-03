"""
DataGuard OpenLineage Repository.
Persistent storage for lineage datasets, jobs, runs, edges, and column-level lineage.
Backed by PostgreSQL 16 with automatic transactional integrity and SQLite support for testing.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from collections import deque

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    DateTime,
    Index,
    select,
    desc
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from dataguard.lineage.models import (
    LineageStatus,
    LineageDataset,
    LineageJob,
    LineageRun,
    LineageEdge,
    ColumnLineageMapping,
    ColumnLineageDetail,
    LineageGraphNode,
    LineageGraphEdge,
    LineageGraphResponse,
    DatasetLineageSummary,
    UpstreamLineageResponse,
    DownstreamLineageResponse,
)
from dataguard.lineage.events import RunEvent

Base = declarative_base()


class LineageDatasetModel(Base):
    __tablename__ = "lineage_datasets"

    dataset_id = Column(String(256), primary_key=True)
    namespace = Column(String(128), nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    schema_facets = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_lineage_datasets_name", "name"),
        Index("idx_lineage_datasets_namespace", "namespace"),
    )


class LineageJobModel(Base):
    __tablename__ = "lineage_jobs"

    job_id = Column(String(256), primary_key=True)
    namespace = Column(String(128), nullable=False)
    name = Column(String(128), nullable=False)
    pipeline_id = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_lineage_jobs_pipeline", "pipeline_id"),
    )


class LineageRunModel(Base):
    __tablename__ = "lineage_runs"

    run_id = Column(String(64), primary_key=True)
    job_id = Column(String(256), nullable=False)
    pipeline_id = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    inputs_json = Column(Text, nullable=True)
    outputs_json = Column(Text, nullable=True)
    facets_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_lineage_runs_job_id", "job_id"),
        Index("idx_lineage_runs_pipeline", "pipeline_id"),
        Index("idx_lineage_runs_status", "status"),
    )


class LineageEdgeModel(Base):
    __tablename__ = "lineage_edges"

    edge_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), nullable=False)
    source_dataset = Column(String(256), nullable=False)
    target_dataset = Column(String(256), nullable=False)
    pipeline_id = Column(String(128), nullable=False)
    edge_type = Column(String(32), default="DATA_FLOW")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_lineage_edges_source", "source_dataset"),
        Index("idx_lineage_edges_target", "target_dataset"),
        Index("idx_lineage_edges_run_id", "run_id"),
    )


class LineageColumnModel(Base):
    __tablename__ = "lineage_columns"

    column_edge_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), nullable=False)
    source_dataset = Column(String(256), nullable=False)
    source_column = Column(String(128), nullable=False)
    target_dataset = Column(String(256), nullable=False)
    target_column = Column(String(128), nullable=False)
    transformation = Column(Text, nullable=False)
    pipeline_id = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_lineage_cols_source", "source_dataset", "source_column"),
        Index("idx_lineage_cols_target", "target_dataset", "target_column"),
        Index("idx_lineage_cols_run_id", "run_id"),
    )


def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _iso_to_dt(iso_str: Optional[str]) -> Optional[datetime]:
    if not iso_str:
        return None
    try:
        clean_str = iso_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return datetime.now(timezone.utc)


class LineageRepository:
    """
    SQLAlchemy-based Lineage Repository for DataGuard.
    """

    def __init__(self, db_url: Optional[str] = None, db_path: Optional[Path] = None):
        if db_url:
            self.database_url = db_url
        elif db_path:
            self.database_url = f"sqlite:///{db_path}"
        else:
            from dataguard.contracts.registry import get_default_db_url
            self.database_url = get_default_db_url()

        connect_args = {}
        if self.database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        self.engine = create_engine(
            self.database_url,
            echo=False,
            connect_args=connect_args,
            pool_pre_ping=True
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._init_db()

    def _init_db(self):
        Base.metadata.create_all(bind=self.engine)

    def register_dataset(
        self,
        name: str,
        namespace: str = "default",
        description: Optional[str] = None,
        schema_facets: Optional[Dict[str, Any]] = None
    ) -> LineageDataset:
        dataset_id = f"{namespace}.{name}" if namespace else name
        schema_str = json.dumps(schema_facets) if schema_facets else None

        with self.SessionLocal() as session:
            existing = session.query(LineageDatasetModel).filter(
                LineageDatasetModel.namespace == namespace,
                LineageDatasetModel.name == name
            ).first()

            now = datetime.now(timezone.utc)
            if existing:
                if description:
                    existing.description = description
                if schema_str:
                    existing.schema_facets = schema_str
                existing.updated_at = now
                session.commit()
                session.refresh(existing)
                target = existing
            else:
                target = LineageDatasetModel(
                    dataset_id=dataset_id,
                    namespace=namespace,
                    name=name,
                    description=description,
                    schema_facets=schema_str,
                    created_at=now,
                    updated_at=now
                )
                session.add(target)
                session.commit()
                session.refresh(target)

            return LineageDataset(
                dataset_id=target.dataset_id,
                namespace=target.namespace,
                name=target.name,
                description=target.description,
                schema_facets=json.loads(target.schema_facets) if target.schema_facets else None,
                created_at=_dt_to_iso(target.created_at) or "",
                updated_at=_dt_to_iso(target.updated_at) or ""
            )

    def register_job(
        self,
        name: str,
        namespace: str = "default",
        pipeline_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> LineageJob:
        pipe_id = pipeline_id or name
        job_id = f"{namespace}.{name}" if namespace else name

        with self.SessionLocal() as session:
            existing = session.query(LineageJobModel).filter(
                LineageJobModel.namespace == namespace,
                LineageJobModel.name == name
            ).first()

            now = datetime.now(timezone.utc)
            if existing:
                existing.pipeline_id = pipe_id
                if description:
                    existing.description = description
                existing.updated_at = now
                session.commit()
                session.refresh(existing)
                target = existing
            else:
                target = LineageJobModel(
                    job_id=job_id,
                    namespace=namespace,
                    name=name,
                    pipeline_id=pipe_id,
                    description=description,
                    created_at=now,
                    updated_at=now
                )
                session.add(target)
                session.commit()
                session.refresh(target)

            return LineageJob(
                job_id=target.job_id,
                namespace=target.namespace,
                name=target.name,
                pipeline_id=target.pipeline_id,
                description=target.description,
                created_at=_dt_to_iso(target.created_at) or "",
                updated_at=_dt_to_iso(target.updated_at) or ""
            )

    def record_run(
        self,
        run_id: str,
        job_id: str,
        pipeline_id: str,
        status: LineageStatus,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        inputs: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
        facets: Optional[Dict[str, Any]] = None
    ) -> LineageRun:
        st_dt = _iso_to_dt(start_time) or datetime.now(timezone.utc)
        et_dt = _iso_to_dt(end_time) if end_time else None

        with self.SessionLocal() as session:
            existing = session.query(LineageRunModel).filter_by(run_id=run_id).first()

            if existing:
                existing.status = status.value if hasattr(status, "value") else str(status)
                if et_dt:
                    existing.end_time = et_dt
                if inputs is not None:
                    existing.inputs_json = json.dumps(inputs)
                if outputs is not None:
                    existing.outputs_json = json.dumps(outputs)
                if facets:
                    curr_facets = json.loads(existing.facets_json or "{}")
                    curr_facets.update(facets)
                    existing.facets_json = json.dumps(curr_facets)
                session.commit()
                session.refresh(existing)
                target = existing
            else:
                target = LineageRunModel(
                    run_id=run_id,
                    job_id=job_id,
                    pipeline_id=pipeline_id,
                    status=status.value if hasattr(status, "value") else str(status),
                    start_time=st_dt,
                    end_time=et_dt,
                    inputs_json=json.dumps(inputs or []),
                    outputs_json=json.dumps(outputs or []),
                    facets_json=json.dumps(facets or {}),
                    created_at=datetime.now(timezone.utc)
                )
                session.add(target)
                session.commit()
                session.refresh(target)

            return LineageRun(
                run_id=target.run_id,
                job_id=target.job_id,
                pipeline_id=target.pipeline_id,
                status=LineageStatus(target.status),
                start_time=_dt_to_iso(target.start_time) or "",
                end_time=_dt_to_iso(target.end_time),
                inputs=json.loads(target.inputs_json or "[]"),
                outputs=json.loads(target.outputs_json or "[]"),
                facets=json.loads(target.facets_json or "{}"),
                created_at=_dt_to_iso(target.created_at) or ""
            )

    def record_edge(
        self,
        run_id: str,
        source_dataset: str,
        target_dataset: str,
        pipeline_id: str,
        edge_type: str = "DATA_FLOW"
    ) -> LineageEdge:
        edge_id = f"edge_{uuid.uuid4().hex[:16]}"
        with self.SessionLocal() as session:
            existing = session.query(LineageEdgeModel).filter_by(
                source_dataset=source_dataset,
                target_dataset=target_dataset,
                pipeline_id=pipeline_id
            ).first()

            if existing:
                existing.run_id = run_id
                session.commit()
                session.refresh(existing)
                target = existing
            else:
                target = LineageEdgeModel(
                    edge_id=edge_id,
                    run_id=run_id,
                    source_dataset=source_dataset,
                    target_dataset=target_dataset,
                    pipeline_id=pipeline_id,
                    edge_type=edge_type,
                    created_at=datetime.now(timezone.utc)
                )
                session.add(target)
                session.commit()
                session.refresh(target)

            return LineageEdge(
                edge_id=target.edge_id,
                run_id=target.run_id,
                source_dataset=target.source_dataset,
                target_dataset=target.target_dataset,
                pipeline_id=target.pipeline_id,
                edge_type=target.edge_type,
                created_at=_dt_to_iso(target.created_at) or ""
            )

    def record_column_mapping(
        self,
        run_id: str,
        source_dataset: str,
        source_column: str,
        target_dataset: str,
        target_column: str,
        transformation: str,
        pipeline_id: str
    ) -> ColumnLineageMapping:
        col_id = f"col_{uuid.uuid4().hex[:16]}"
        with self.SessionLocal() as session:
            existing = session.query(LineageColumnModel).filter_by(
                source_dataset=source_dataset,
                source_column=source_column,
                target_dataset=target_dataset,
                target_column=target_column,
                pipeline_id=pipeline_id
            ).first()

            if existing:
                existing.run_id = run_id
                existing.transformation = transformation
                session.commit()
                session.refresh(existing)
                target = existing
            else:
                target = LineageColumnModel(
                    column_edge_id=col_id,
                    run_id=run_id,
                    source_dataset=source_dataset,
                    source_column=source_column,
                    target_dataset=target_dataset,
                    target_column=target_column,
                    transformation=transformation,
                    pipeline_id=pipeline_id,
                    created_at=datetime.now(timezone.utc)
                )
                session.add(target)
                session.commit()
                session.refresh(target)

            return ColumnLineageMapping(
                column_edge_id=target.column_edge_id,
                run_id=target.run_id,
                source_dataset=target.source_dataset,
                source_column=target.source_column,
                target_dataset=target.target_dataset,
                target_column=target.target_column,
                transformation=target.transformation,
                pipeline_id=target.pipeline_id,
                created_at=_dt_to_iso(target.created_at) or ""
            )

    def ingest_openlineage_event(self, event: RunEvent) -> LineageRun:
        """
        Ingests and persists a complete OpenLineage RunEvent payload into PostgreSQL.
        Registers jobs, input/output datasets, edges, and column-level facets.
        """
        pipe_id = event.job.facets.get("pipeline_id") or event.job.name
        job = self.register_job(
            name=event.job.name,
            namespace=event.job.namespace,
            pipeline_id=pipe_id,
            description=event.job.facets.get("documentation", {}).get("description")
        )

        input_names: List[str] = []
        for inp in event.inputs:
            ds_name = inp.name
            full_name = f"{inp.namespace}.{ds_name}" if inp.namespace != "default" else ds_name
            input_names.append(full_name)
            self.register_dataset(
                name=inp.name,
                namespace=inp.namespace,
                description=f"Input dataset for {event.job.name}"
            )

        output_names: List[str] = []
        for out in event.outputs:
            ds_name = out.name
            full_name = f"{out.namespace}.{ds_name}" if out.namespace != "default" else ds_name
            output_names.append(full_name)
            self.register_dataset(
                name=out.name,
                namespace=out.namespace,
                description=f"Output dataset produced by {event.job.name}"
            )

        # Parse status
        ev_type = event.eventType.upper()
        if ev_type == "START":
            st = LineageStatus.START
        elif ev_type == "COMPLETE":
            st = LineageStatus.COMPLETE
        elif ev_type == "FAIL":
            st = LineageStatus.FAIL
        else:
            st = LineageStatus.RUNNING

        end_time = event.eventTime if st in (LineageStatus.COMPLETE, LineageStatus.FAIL) else None

        run = self.record_run(
            run_id=event.run.runId,
            job_id=job.job_id,
            pipeline_id=job.pipeline_id,
            status=st,
            start_time=event.eventTime if st == LineageStatus.START else None,
            end_time=end_time,
            inputs=input_names,
            outputs=output_names,
            facets=event.run.facets
        )

        # Build lineage edges between all inputs -> pipeline and pipeline -> outputs
        # And direct input -> output dependencies
        for inp_name in input_names:
            self.record_edge(
                run_id=event.run.runId,
                source_dataset=inp_name,
                target_dataset=job.pipeline_id,
                pipeline_id=job.pipeline_id,
                edge_type="INPUT_TO_PIPELINE"
            )

        for out_name in output_names:
            self.record_edge(
                run_id=event.run.runId,
                source_dataset=job.pipeline_id,
                target_dataset=out_name,
                pipeline_id=job.pipeline_id,
                edge_type="PIPELINE_TO_OUTPUT"
            )

        # Direct dataset-to-dataset edge for data flow graph
        for inp_name in input_names:
            for out_name in output_names:
                self.record_edge(
                    run_id=event.run.runId,
                    source_dataset=inp_name,
                    target_dataset=out_name,
                    pipeline_id=job.pipeline_id,
                    edge_type="DATASET_DEPENDENCY"
                )

        # Parse columnLineage facet if present on outputs
        for out in event.outputs:
            col_facet = out.get_column_lineage_facet()
            if col_facet and col_facet.fields:
                out_full_name = f"{out.namespace}.{out.name}" if out.namespace != "default" else out.name
                for target_col, field_meta in col_facet.fields.items():
                    for in_field in field_meta.inputFields:
                        src_full_name = f"{in_field.namespace}.{in_field.name}" if in_field.namespace != "default" else in_field.name
                        self.record_column_mapping(
                            run_id=event.run.runId,
                            source_dataset=src_full_name,
                            source_column=in_field.field,
                            target_dataset=out_full_name,
                            target_column=target_col,
                            transformation=field_meta.transformationDescription or "TRANSFORM",
                            pipeline_id=job.pipeline_id
                        )

        return run

    def get_run(self, run_id: str) -> Optional[LineageRun]:
        with self.SessionLocal() as session:
            model = session.query(LineageRunModel).filter_by(run_id=run_id).first()
            if not model:
                return None
            return LineageRun(
                run_id=model.run_id,
                job_id=model.job_id,
                pipeline_id=model.pipeline_id,
                status=LineageStatus(model.status),
                start_time=_dt_to_iso(model.start_time) or "",
                end_time=_dt_to_iso(model.end_time),
                inputs=json.loads(model.inputs_json or "[]"),
                outputs=json.loads(model.outputs_json or "[]"),
                facets=json.loads(model.facets_json or "{}"),
                created_at=_dt_to_iso(model.created_at) or ""
            )

    def get_runs_for_pipeline(self, pipeline_id: str, limit: int = 50) -> List[LineageRun]:
        with self.SessionLocal() as session:
            models = session.query(LineageRunModel).filter(
                LineageRunModel.pipeline_id == pipeline_id
            ).order_by(desc(LineageRunModel.start_time)).limit(limit).all()

            return [
                LineageRun(
                    run_id=m.run_id,
                    job_id=m.job_id,
                    pipeline_id=m.pipeline_id,
                    status=LineageStatus(m.status),
                    start_time=_dt_to_iso(m.start_time) or "",
                    end_time=_dt_to_iso(m.end_time),
                    inputs=json.loads(m.inputs_json or "[]"),
                    outputs=json.loads(m.outputs_json or "[]"),
                    facets=json.loads(m.facets_json or "{}"),
                    created_at=_dt_to_iso(m.created_at) or ""
                )
                for m in models
            ]

    def get_column_lineage(self, target_dataset: str, target_column: Optional[str] = None) -> List[ColumnLineageDetail]:
        clean_target = target_dataset.lower()
        with self.SessionLocal() as session:
            query = session.query(LineageColumnModel)
            all_cols = query.all()

            # Filter with flexible namespace matching (e.g. 'transactions' matches 'postgres.transactions')
            matched = [
                c for c in all_cols
                if (c.target_dataset.lower() == clean_target or 
                    c.target_dataset.lower().endswith(f".{clean_target}"))
            ]

            if target_column:
                matched = [c for c in matched if c.target_column.lower() == target_column.lower()]

            # Group source columns per target_column
            grouped: Dict[str, Dict[str, Any]] = {}
            for row in matched:
                t_col = row.target_column
                if t_col not in grouped:
                    grouped[t_col] = {
                        "target_column": t_col,
                        "source_columns": [],
                        "transformation": row.transformation,
                        "pipeline": row.pipeline_id,
                        "run_id": row.run_id
                    }
                grouped[t_col]["source_columns"].append({
                    "dataset": row.source_dataset,
                    "column": row.source_column
                })

            return [
                ColumnLineageDetail(
                    target_column=v["target_column"],
                    source_columns=v["source_columns"],
                    transformation=v["transformation"],
                    pipeline=v["pipeline"],
                    run_id=v["run_id"]
                )
                for v in grouped.values()
            ]

    def get_graph(self) -> LineageGraphResponse:
        """
        Dynamically constructs full graph topology (nodes & edges) from persisted lineage metadata.
        """
        with self.SessionLocal() as session:
            datasets = session.query(LineageDatasetModel).all()
            jobs = session.query(LineageJobModel).all()
            edges = session.query(LineageEdgeModel).all()

            node_map: Dict[str, LineageGraphNode] = {}

            for ds in datasets:
                node_map[ds.dataset_id] = LineageGraphNode(
                    id=ds.dataset_id,
                    name=ds.name,
                    type="dataset",
                    namespace=ds.namespace,
                    metadata={"description": ds.description}
                )

            for j in jobs:
                node_map[j.pipeline_id] = LineageGraphNode(
                    id=j.pipeline_id,
                    name=j.name,
                    type="pipeline",
                    namespace=j.namespace,
                    metadata={"description": j.description}
                )

            # Ensure any edge endpoints not explicitly in dataset/job table are added as nodes
            graph_edges: List[LineageGraphEdge] = []
            for e in edges:
                if e.source_dataset not in node_map:
                    node_map[e.source_dataset] = LineageGraphNode(
                        id=e.source_dataset,
                        name=e.source_dataset.split(".")[-1],
                        type="dataset",
                        namespace="default"
                    )
                if e.target_dataset not in node_map:
                    node_map[e.target_dataset] = LineageGraphNode(
                        id=e.target_dataset,
                        name=e.target_dataset.split(".")[-1],
                        type="dataset",
                        namespace="default"
                    )

                graph_edges.append(LineageGraphEdge(
                    source=e.source_dataset,
                    target=e.target_dataset,
                    pipeline_id=e.pipeline_id,
                    run_id=e.run_id,
                    edge_type=e.edge_type
                ))

            nodes_list = list(node_map.values())
            return LineageGraphResponse(
                nodes=nodes_list,
                edges=graph_edges,
                total_nodes=len(nodes_list),
                total_edges=len(graph_edges)
            )

    def get_upstream(self, dataset: str, max_depth: int = 5) -> UpstreamLineageResponse:
        """
        BFS traversal to find all upstream datasets and intermediate pipelines feeding the dataset.
        """
        graph = self.get_graph()
        
        # Build adjacency mapping: target -> list of sources
        incoming: Dict[str, List[LineageGraphEdge]] = {}
        for edge in graph.edges:
            incoming.setdefault(edge.target.lower(), []).append(edge)

        # Match initial node
        start_nodes = [
            n.id for n in graph.nodes 
            if n.id.lower() == dataset.lower() or n.id.lower().endswith(f".{dataset.lower()}")
        ]

        visited: Set[str] = set()
        queue = deque([(node, 0) for node in start_nodes])
        upstream_datasets: Set[str] = set()
        pipelines: Set[str] = set()

        while queue:
            curr, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for edge in incoming.get(curr.lower(), []):
                src = edge.source
                if src.lower() not in visited:
                    visited.add(src.lower())
                    
                    # Distinguish dataset vs pipeline
                    is_pipe = any(n.id == src and n.type == "pipeline" for n in graph.nodes)
                    if is_pipe:
                        pipelines.add(src)
                    else:
                        upstream_datasets.add(src)
                    
                    if edge.pipeline_id:
                        pipelines.add(edge.pipeline_id)

                    queue.append((src, depth + 1))

        # Do not include the target dataset itself in upstream list
        for s in start_nodes:
            upstream_datasets.discard(s)

        return UpstreamLineageResponse(
            dataset=dataset,
            upstream_datasets=sorted(list(upstream_datasets)),
            pipelines=sorted(list(pipelines)),
            depth=max_depth
        )

    def get_downstream(self, dataset: str, max_depth: int = 5) -> DownstreamLineageResponse:
        """
        BFS traversal to find all downstream datasets and consuming pipelines.
        """
        graph = self.get_graph()
        
        # Build adjacency mapping: source -> list of targets
        outgoing: Dict[str, List[LineageGraphEdge]] = {}
        for edge in graph.edges:
            outgoing.setdefault(edge.source.lower(), []).append(edge)

        start_nodes = [
            n.id for n in graph.nodes 
            if n.id.lower() == dataset.lower() or n.id.lower().endswith(f".{dataset.lower()}")
        ]

        visited: Set[str] = set()
        queue = deque([(node, 0) for node in start_nodes])
        downstream_datasets: Set[str] = set()
        pipelines: Set[str] = set()

        while queue:
            curr, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for edge in outgoing.get(curr.lower(), []):
                tgt = edge.target
                if tgt.lower() not in visited:
                    visited.add(tgt.lower())
                    
                    is_pipe = any(n.id == tgt and n.type == "pipeline" for n in graph.nodes)
                    if is_pipe:
                        pipelines.add(tgt)
                    else:
                        downstream_datasets.add(tgt)
                    
                    if edge.pipeline_id:
                        pipelines.add(edge.pipeline_id)

                    queue.append((tgt, depth + 1))

        for s in start_nodes:
            downstream_datasets.discard(s)

        return DownstreamLineageResponse(
            dataset=dataset,
            downstream_datasets=sorted(list(downstream_datasets)),
            pipelines=sorted(list(pipelines)),
            depth=max_depth
        )

    def get_dataset_summary(self, dataset: str) -> Optional[DatasetLineageSummary]:
        graph = self.get_graph()
        matched = [
            n for n in graph.nodes 
            if n.id.lower() == dataset.lower() or n.id.lower().endswith(f".{dataset.lower()}")
        ]
        if not matched:
            return None

        node = matched[0]
        upstream = self.get_upstream(dataset, max_depth=5)
        downstream = self.get_downstream(dataset, max_depth=5)

        with self.SessionLocal() as session:
            latest_run = session.query(LineageRunModel).filter(
                LineageRunModel.outputs_json.like(f"%{dataset}%")
            ).order_by(desc(LineageRunModel.start_time)).first()

            return DatasetLineageSummary(
                dataset=node.id,
                namespace=node.namespace,
                producing_pipelines=upstream.pipelines,
                consuming_pipelines=downstream.pipelines,
                upstream_datasets=upstream.upstream_datasets,
                downstream_datasets=downstream.downstream_datasets,
                latest_run_id=latest_run.run_id if latest_run else None,
                last_updated=_dt_to_iso(latest_run.end_time or latest_run.start_time) if latest_run else None
            )

    def get_counts(self) -> Dict[str, int]:
        with self.SessionLocal() as session:
            return {
                "datasets": session.query(LineageDatasetModel).count(),
                "jobs": session.query(LineageJobModel).count(),
                "runs": session.query(LineageRunModel).count(),
                "edges": session.query(LineageEdgeModel).count(),
                "column_mappings": session.query(LineageColumnModel).count(),
            }
