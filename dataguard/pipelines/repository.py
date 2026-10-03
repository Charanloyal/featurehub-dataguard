"""
DataGuard Pipeline Repository (Phase G).
PostgreSQL persistence layer for pipeline configurations, execution runs,
historical tracking, dynamic summaries, and health assessments.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

from dataguard.contracts.registry import get_default_db_url, create_db_engine
from dataguard.pipelines.models import (
    PipelineConfig,
    PipelineRun,
    PipelineStatus,
    PipelineRunStatus,
    PipelineSummary,
    PipelineHealth
)

logger = logging.getLogger("dataguard.pipelines.repository")


class PipelineRepository:
    """
    Manages persistence of pipelines and pipeline runs in PostgreSQL.
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or get_default_db_url()
        self.engine = create_db_engine(self.db_url)

    def upsert_pipeline(self, config: PipelineConfig) -> PipelineConfig:
        """
        Creates or updates a pipeline definition in PostgreSQL.
        """
        now = datetime.now(timezone.utc)
        tags_json = json.dumps(config.tags)

        query = text("""
            INSERT INTO pipeline_metadata (
                pipeline_id, name, owner, dataset, contract,
                freshness_sla_minutes, description, schedule,
                status, created_at, updated_at, tags_json
            ) VALUES (
                :pipeline_id, :name, :owner, :dataset, :contract,
                :freshness_sla_minutes, :description, :schedule,
                :status, :created_at, :updated_at, :tags_json
            )
            ON CONFLICT (pipeline_id) DO UPDATE SET
                name = EXCLUDED.name,
                owner = EXCLUDED.owner,
                dataset = EXCLUDED.dataset,
                contract = EXCLUDED.contract,
                freshness_sla_minutes = EXCLUDED.freshness_sla_minutes,
                description = EXCLUDED.description,
                schedule = EXCLUDED.schedule,
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at,
                tags_json = EXCLUDED.tags_json
        """)

        with self.engine.begin() as conn:
            conn.execute(query, {
                "pipeline_id": config.pipeline_id,
                "name": config.name,
                "owner": config.owner,
                "dataset": config.dataset,
                "contract": config.contract,
                "freshness_sla_minutes": config.freshness_sla_minutes,
                "description": config.description,
                "schedule": config.schedule,
                "status": config.status.value if isinstance(config.status, PipelineStatus) else str(config.status),
                "created_at": config.created_at or now,
                "updated_at": now,
                "tags_json": tags_json
            })

        return self.get_pipeline(config.pipeline_id) or config

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineConfig]:
        """
        Retrieves a single pipeline configuration by ID.
        """
        query = text("""
            SELECT pipeline_id, name, owner, dataset, contract,
                   freshness_sla_minutes, description, schedule,
                   status, created_at, updated_at, last_run_at,
                   last_success_at, last_failure_at, tags_json
            FROM pipeline_metadata
            WHERE pipeline_id = :pipeline_id
        """)

        with self.engine.connect() as conn:
            row = conn.execute(query, {"pipeline_id": pipeline_id}).fetchone()
            if not row:
                return None

            return self._row_to_config(row)

    def list_pipelines(
        self,
        status: Optional[str] = None,
        owner: Optional[str] = None
    ) -> List[PipelineConfig]:
        """
        Lists all registered pipelines with optional filtering.
        """
        clauses = []
        params: Dict[str, Any] = {}

        if status:
            clauses.append("status = :status")
            params["status"] = status
        if owner:
            clauses.append("owner = :owner")
            params["owner"] = owner

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        query = text(f"""
            SELECT pipeline_id, name, owner, dataset, contract,
                   freshness_sla_minutes, description, schedule,
                   status, created_at, updated_at, last_run_at,
                   last_success_at, last_failure_at, tags_json
            FROM pipeline_metadata
            {where_sql}
            ORDER BY pipeline_id ASC
        """)

        with self.engine.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_config(r) for r in rows]

    def record_run_start(
        self,
        run_id: str,
        pipeline_id: str,
        dataset: str,
        start_time: Optional[datetime] = None
    ) -> PipelineRun:
        """
        Records the beginning of a pipeline run with status RUNNING.
        Also updates last_run_at on pipeline_metadata.
        """
        start_dt = start_time or datetime.now(timezone.utc)

        # Ensure pipeline exists in metadata, or auto-register minimal record
        if not self.get_pipeline(pipeline_id):
            minimal_config = PipelineConfig(
                pipeline_id=pipeline_id,
                name=pipeline_id.replace("_", " ").title(),
                owner="data-platform-team",
                dataset=dataset,
                contract=f"{dataset}.yaml",
                description=f"Auto-registered pipeline for {dataset}"
            )
            self.upsert_pipeline(minimal_config)

        insert_query = text("""
            INSERT INTO pipeline_runs (
                run_id, pipeline_id, dataset, status, start_time,
                duration_ms, retry_count, metrics_json, created_at
            ) VALUES (
                :run_id, :pipeline_id, :dataset, :status, :start_time,
                0.0, 0, '{}', :created_at
            )
            ON CONFLICT (run_id) DO UPDATE SET
                status = EXCLUDED.status,
                start_time = EXCLUDED.start_time
        """)

        update_meta_query = text("""
            UPDATE pipeline_metadata
            SET last_run_at = :last_run_at, updated_at = :updated_at
            WHERE pipeline_id = :pipeline_id
        """)

        with self.engine.begin() as conn:
            conn.execute(insert_query, {
                "run_id": run_id,
                "pipeline_id": pipeline_id,
                "dataset": dataset,
                "status": PipelineRunStatus.RUNNING.value,
                "start_time": start_dt,
                "created_at": start_dt
            })
            conn.execute(update_meta_query, {
                "pipeline_id": pipeline_id,
                "last_run_at": start_dt,
                "updated_at": start_dt
            })

        return PipelineRun(
            run_id=run_id,
            pipeline_id=pipeline_id,
            dataset=dataset,
            status=PipelineRunStatus.RUNNING,
            start_time=start_dt,
            created_at=start_dt
        )

    def record_run_finish(
        self,
        run_id: str,
        status: PipelineRunStatus,
        duration_ms: float,
        quality_run_id: Optional[str] = None,
        incident_id: Optional[str] = None,
        lineage_run_id: Optional[str] = None,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        metrics: Optional[Dict[str, Any]] = None
    ) -> Optional[PipelineRun]:
        """
        Records completion or failure of a pipeline run.
        Updates pipeline_runs record and pipeline_metadata timestamps.
        """
        end_dt = datetime.now(timezone.utc)
        metrics_json = json.dumps(metrics or {})
        status_val = status.value if isinstance(status, PipelineRunStatus) else str(status)

        update_run_query = text("""
            UPDATE pipeline_runs
            SET status = :status,
                end_time = :end_time,
                duration_ms = :duration_ms,
                quality_run_id = :quality_run_id,
                incident_id = :incident_id,
                lineage_run_id = :lineage_run_id,
                error_message = :error_message,
                retry_count = :retry_count,
                metrics_json = :metrics_json
            WHERE run_id = :run_id
            RETURNING pipeline_id, dataset, start_time, created_at
        """)

        with self.engine.begin() as conn:
            row = conn.execute(update_run_query, {
                "run_id": run_id,
                "status": status_val,
                "end_time": end_dt,
                "duration_ms": duration_ms,
                "quality_run_id": quality_run_id,
                "incident_id": incident_id,
                "lineage_run_id": lineage_run_id,
                "error_message": error_message,
                "retry_count": retry_count,
                "metrics_json": metrics_json
            }).fetchone()

            if not row:
                return None

            pipeline_id, dataset, start_time, created_at = row[0], row[1], row[2], row[3]

            # Update last_success_at or last_failure_at on pipeline_metadata
            if status == PipelineRunStatus.SUCCESS:
                meta_query = text("""
                    UPDATE pipeline_metadata
                    SET last_success_at = :ts, updated_at = :ts
                    WHERE pipeline_id = :pipeline_id
                """)
            else:
                meta_query = text("""
                    UPDATE pipeline_metadata
                    SET last_failure_at = :ts, updated_at = :ts
                    WHERE pipeline_id = :pipeline_id
                """)

            conn.execute(meta_query, {"pipeline_id": pipeline_id, "ts": end_dt})

        return PipelineRun(
            run_id=run_id,
            pipeline_id=pipeline_id,
            dataset=dataset,
            status=status,
            start_time=start_time,
            end_time=end_dt,
            duration_ms=duration_ms,
            quality_run_id=quality_run_id,
            incident_id=incident_id,
            lineage_run_id=lineage_run_id,
            error_message=error_message,
            retry_count=retry_count,
            metrics=metrics or {},
            created_at=created_at
        )

    def get_run(self, run_id: str) -> Optional[PipelineRun]:
        """
        Retrieves a single pipeline run by run_id.
        """
        query = text("""
            SELECT run_id, pipeline_id, dataset, status, start_time,
                   end_time, duration_ms, quality_run_id, incident_id,
                   lineage_run_id, error_message, retry_count, metrics_json, created_at
            FROM pipeline_runs
            WHERE run_id = :run_id
        """)

        with self.engine.connect() as conn:
            row = conn.execute(query, {"run_id": run_id}).fetchone()
            if not row:
                return None
            return self._row_to_run(row)

    def list_runs(
        self,
        pipeline_id: Optional[str] = None,
        limit: int = 50
    ) -> List[PipelineRun]:
        """
        Lists recent pipeline runs.
        """
        where_sql = "WHERE pipeline_id = :pipeline_id" if pipeline_id else ""
        params: Dict[str, Any] = {"limit": limit}
        if pipeline_id:
            params["pipeline_id"] = pipeline_id

        query = text(f"""
            SELECT run_id, pipeline_id, dataset, status, start_time,
                   end_time, duration_ms, quality_run_id, incident_id,
                   lineage_run_id, error_message, retry_count, metrics_json, created_at
            FROM pipeline_runs
            {where_sql}
            ORDER BY start_time DESC
            LIMIT :limit
        """)

        with self.engine.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_run(r) for r in rows]

    def get_latest_run(self, pipeline_id: str) -> Optional[PipelineRun]:
        """
        Retrieves the latest execution run for a given pipeline.
        """
        runs = self.list_runs(pipeline_id=pipeline_id, limit=1)
        return runs[0] if runs else None

    def get_pipeline_summary(self) -> PipelineSummary:
        """
        Computes dynamic summary aggregated from real metadata and run history.
        """
        with self.engine.connect() as conn:
            # 1. Total and active pipelines
            pipe_counts = conn.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) as active
                FROM pipeline_metadata
            """)).fetchone()
            total_pipelines = pipe_counts[0] if pipe_counts else 0
            active_pipelines = pipe_counts[1] if pipe_counts else 0

            # 2. Run statistics
            run_counts = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_runs,
                    COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_runs,
                    COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as success_runs,
                    COUNT(CASE WHEN status = 'RUNNING' THEN 1 END) as running_runs
                FROM pipeline_runs
            """)).fetchone()
            total_runs = run_counts[0] if run_counts else 0
            failed_runs = run_counts[1] if run_counts else 0
            success_runs = run_counts[2] if run_counts else 0
            running_runs = run_counts[3] if run_counts else 0

            # 3. Pipeline states based on latest runs
            latest_status = conn.execute(text("""
                WITH ranked_runs AS (
                    SELECT pipeline_id, status,
                           ROW_NUMBER() OVER(PARTITION BY pipeline_id ORDER BY start_time DESC) as rn
                    FROM pipeline_runs
                )
                SELECT 
                    COUNT(CASE WHEN status = 'SUCCESS' THEN 1 END) as successful_pipes,
                    COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_pipes,
                    COUNT(CASE WHEN status = 'RUNNING' THEN 1 END) as running_pipes
                FROM ranked_runs
                WHERE rn = 1
            """)).fetchone()

            successful_pipelines = latest_status[0] if latest_status else 0
            failed_pipelines = latest_status[1] if latest_status else 0
            running_pipelines = latest_status[2] if latest_status else 0

            # 4. Check for stale pipelines (where last_run_at is older than freshness_sla)
            stale_row = conn.execute(text("""
                SELECT COUNT(*)
                FROM pipeline_metadata
                WHERE last_run_at IS NOT NULL
                  AND last_run_at < NOW() - (freshness_sla_minutes || ' minutes')::INTERVAL
            """)).fetchone()
            stale_pipelines = stale_row[0] if stale_row else 0

            # 5. Success rate
            success_rate = round((success_runs / total_runs * 100.0), 2) if total_runs > 0 else 100.0

            return PipelineSummary(
                total_pipelines=total_pipelines,
                active_pipelines=active_pipelines,
                successful_pipelines=successful_pipelines,
                failed_pipelines=failed_pipelines,
                running_pipelines=running_pipelines,
                stale_pipelines=stale_pipelines,
                total_runs=total_runs,
                failed_runs=failed_runs,
                success_rate=success_rate
            )

    def get_pipeline_health(self, pipeline_id: str) -> Optional[PipelineHealth]:
        """
        Evaluates health score and operational state of a pipeline.
        """
        pipe = self.get_pipeline(pipeline_id)
        if not pipe:
            return None

        latest_run = self.get_latest_run(pipeline_id)
        quality_score: Optional[float] = None
        active_incidents = 0
        freshness_status = "FRESH"

        # Check freshness SLA
        if pipe.last_run_at:
            delta_mins = (datetime.now(timezone.utc) - pipe.last_run_at.replace(tzinfo=timezone.utc)).total_seconds() / 60.0
            if delta_mins > pipe.freshness_sla_minutes:
                freshness_status = "STALE"

        with self.engine.connect() as conn:
            # Check latest quality run score if exists
            if latest_run and latest_run.quality_run_id:
                q_row = conn.execute(text("""
                    SELECT quality_score, freshness_status
                    FROM quality_runs
                    WHERE run_id = :run_id
                """), {"run_id": latest_run.quality_run_id}).fetchone()
                if q_row:
                    quality_score = float(q_row[0]) if q_row[0] is not None else 100.0
                    if q_row[1]:
                        freshness_status = q_row[1]

            # Check active incidents
            inc_row = conn.execute(text("""
                SELECT COUNT(*)
                FROM incidents
                WHERE (pipeline = :pipe OR pipeline_id = :pipe)
                  AND status != 'RESOLVED'
            """), {"pipe": pipeline_id}).fetchone()
            if inc_row:
                active_incidents = int(inc_row[0])

        is_healthy = (
            (latest_run is None or latest_run.status == PipelineRunStatus.SUCCESS)
            and active_incidents == 0
            and freshness_status != "STALE"
        )

        return PipelineHealth(
            pipeline_id=pipeline_id,
            status=pipe.status.value,
            is_healthy=is_healthy,
            freshness_status=freshness_status,
            last_run=latest_run.model_dump(mode="json") if latest_run else None,
            quality_score=quality_score,
            active_incidents=active_incidents
        )

    def _row_to_config(self, row: Any) -> PipelineConfig:
        tags_raw = row[14]
        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except Exception:
            tags = []

        return PipelineConfig(
            pipeline_id=row[0],
            name=row[1],
            owner=row[2],
            dataset=row[3],
            contract=row[4],
            freshness_sla_minutes=row[5],
            description=row[6],
            schedule=row[7],
            status=PipelineStatus(row[8]),
            created_at=row[9],
            updated_at=row[10],
            last_run_at=row[11],
            last_success_at=row[12],
            last_failure_at=row[13],
            tags=tags
        )

    def _row_to_run(self, row: Any) -> PipelineRun:
        metrics_raw = row[12]
        try:
            metrics = json.loads(metrics_raw) if metrics_raw else {}
        except Exception:
            metrics = {}

        return PipelineRun(
            run_id=row[0],
            pipeline_id=row[1],
            dataset=row[2],
            status=PipelineRunStatus(row[3]),
            start_time=row[4],
            end_time=row[5],
            duration_ms=float(row[6]) if row[6] is not None else 0.0,
            quality_run_id=row[7],
            incident_id=row[8],
            lineage_run_id=row[9],
            error_message=row[10],
            retry_count=int(row[11]) if row[11] is not None else 0,
            metrics=metrics,
            created_at=row[13]
        )
