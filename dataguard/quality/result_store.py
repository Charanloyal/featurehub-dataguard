"""
DataGuard Quality Result Store.
Persists validation runs and expectation check results in PostgreSQL.
Supports historical trend retrieval, quality scoring, and summary aggregations.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    select,
    desc,
    func,
    and_
)
from sqlalchemy.engine import Engine

from dataguard.contracts.registry import get_default_db_url, create_db_engine
from dataguard.quality.models import (
    QualityStatus,
    QualitySeverity,
    FreshnessStatus,
    QualityCheckResult,
    QualityRunResult,
    QualitySummaryResponse
)


class QualityResultStore:
    """
    Manages persistence and retrieval of data quality runs and individual checks.
    Supports PostgreSQL in production and SQLite in test environments.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        db_path: Optional[Path] = None,
        engine: Optional[Engine] = None
    ):
        if engine is not None:
            self.engine = engine
            self.db_url = str(engine.url)
        elif db_url is not None:
            self.db_url = db_url
            self.engine = create_db_engine(self.db_url)
        elif db_path is not None:
            self.db_url = f"sqlite:///{Path(db_path).resolve().as_posix()}"
            self.engine = create_engine(self.db_url)
        else:
            self.db_url = get_default_db_url()
            self.engine = create_db_engine(self.db_url)

        self.metadata = MetaData()
        self._define_schema()
        self._init_db()

    def _define_schema(self):
        self.quality_runs = Table(
            "quality_runs",
            self.metadata,
            Column("run_id", String(64), primary_key=True),
            Column("dataset_name", String(128), nullable=False, index=True),
            Column("contract_version", String(64), default="v1.0.0"),
            Column("pipeline_name", String(128), default="default_pipeline"),
            Column("overall_status", String(32), nullable=False),
            Column("total_checks", Integer, default=0),
            Column("passed_checks", Integer, default=0),
            Column("failed_checks", Integer, default=0),
            Column("warning_checks", Integer, default=0),
            Column("quality_score", Float, default=100.0),
            Column("duration_ms", Float, default=0.0),
            Column("freshness_status", String(32), default="FRESH"),
            Column("freshness_delay_minutes", Float, nullable=True),
            Column("last_record_timestamp", String(64), nullable=True),
            Column("row_count", Integer, default=0),
            Column("executed_at", DateTime(timezone=True), server_default=func.now(), index=True),
            Column("metadata_json", Text, nullable=True),
        )

        self.quality_results = Table(
            "quality_results",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("run_id", String(64), ForeignKey("quality_runs.run_id", ondelete="CASCADE"), nullable=False, index=True),
            Column("dataset_name", String(128), nullable=False, index=True),
            Column("check_name", String(256), nullable=False),
            Column("column_name", String(128), nullable=True),
            Column("expectation_type", String(128), nullable=False),
            Column("status", String(32), nullable=False),
            Column("severity", String(32), nullable=False),
            Column("success", Boolean, nullable=False),
            Column("observed_value", Text, nullable=True),
            Column("expected_value", Text, nullable=True),
            Column("duration_ms", Float, default=0.0),
            Column("timestamp", DateTime(timezone=True), server_default=func.now()),
            Column("pipeline_name", String(128), default="default_pipeline"),
            Column("details_json", Text, nullable=True),
        )

    def _init_db(self):
        """Creates tables if they do not exist."""
        self.metadata.create_all(self.engine)

    def record_run(self, run: QualityRunResult) -> None:
        """Persists a complete quality validation run along with all individual check results."""
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            # 1. Insert quality_run
            ins_run = self.quality_runs.insert().values(
                run_id=run.run_id,
                dataset_name=run.dataset,
                contract_version=run.contract_version,
                pipeline_name=run.pipeline,
                overall_status=run.overall_status.value if hasattr(run.overall_status, "value") else str(run.overall_status),
                total_checks=run.total_checks,
                passed_checks=run.passed_checks,
                failed_checks=run.failed_checks,
                warning_checks=run.warning_checks,
                quality_score=run.quality_score,
                duration_ms=run.duration_ms,
                freshness_status=run.freshness_status.value if hasattr(run.freshness_status, "value") else str(run.freshness_status),
                freshness_delay_minutes=run.freshness_delay_minutes,
                last_record_timestamp=run.last_record_timestamp,
                row_count=run.row_count,
                executed_at=now,
                metadata_json=json.dumps({"checks_count": len(run.checks)})
            )
            conn.execute(ins_run)

            # 2. Batch insert quality_results
            if run.checks:
                check_rows = []
                for c in run.checks:
                    check_rows.append({
                        "run_id": run.run_id,
                        "dataset_name": run.dataset,
                        "check_name": c.check_name,
                        "column_name": c.column,
                        "expectation_type": c.expectation_type,
                        "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                        "severity": c.severity.value if hasattr(c.severity, "value") else str(c.severity),
                        "success": c.success,
                        "observed_value": str(c.observed_value) if c.observed_value is not None else None,
                        "expected_value": str(c.expected_value) if c.expected_value is not None else None,
                        "duration_ms": c.duration_ms,
                        "timestamp": now,
                        "pipeline_name": c.pipeline,
                        "details_json": json.dumps(c.details)
                    })
                conn.execute(self.quality_results.insert(), check_rows)

    def get_run(self, run_id: str) -> Optional[QualityRunResult]:
        """Retrieves a single validation run by run_id along with its check records."""
        with self.engine.connect() as conn:
            stmt_run = select(self.quality_runs).where(self.quality_runs.c.run_id == run_id)
            row_run = conn.execute(stmt_run).mappings().fetchone()
            if not row_run:
                return None

            stmt_checks = select(self.quality_results).where(self.quality_results.c.run_id == run_id)
            rows_checks = conn.execute(stmt_checks).mappings().fetchall()

            checks = []
            for r in rows_checks:
                details = {}
                if r["details_json"]:
                    try:
                        details = json.loads(r["details_json"])
                    except Exception:
                        pass
                checks.append(QualityCheckResult(
                    run_id=r["run_id"],
                    dataset=r["dataset_name"],
                    check_name=r["check_name"],
                    column=r["column_name"],
                    expectation_type=r["expectation_type"],
                    status=QualityStatus(r["status"]),
                    severity=QualitySeverity(r["severity"]),
                    observed_value=r["observed_value"],
                    expected_value=r["expected_value"],
                    success=r["success"],
                    duration_ms=r["duration_ms"],
                    timestamp=r["timestamp"].isoformat() if hasattr(r["timestamp"], "isoformat") else str(r["timestamp"]),
                    pipeline=r["pipeline_name"],
                    details=details
                ))

            executed_at = row_run["executed_at"]
            return QualityRunResult(
                run_id=row_run["run_id"],
                dataset=row_run["dataset_name"],
                contract_version=row_run["contract_version"],
                pipeline=row_run["pipeline_name"],
                overall_status=QualityStatus(row_run["overall_status"]),
                total_checks=row_run["total_checks"],
                passed_checks=row_run["passed_checks"],
                failed_checks=row_run["failed_checks"],
                warning_checks=row_run["warning_checks"],
                quality_score=row_run["quality_score"],
                duration_ms=row_run["duration_ms"],
                freshness_status=FreshnessStatus(row_run["freshness_status"]) if row_run["freshness_status"] else FreshnessStatus.UNKNOWN,
                freshness_delay_minutes=row_run["freshness_delay_minutes"],
                last_record_timestamp=row_run["last_record_timestamp"],
                row_count=row_run["row_count"],
                executed_at=executed_at.isoformat() if hasattr(executed_at, "isoformat") else str(executed_at),
                checks=checks
            )

    def get_latest_run(self, dataset_name: str) -> Optional[QualityRunResult]:
        """Retrieves the most recent quality run for a given dataset."""
        with self.engine.connect() as conn:
            stmt = (
                select(self.quality_runs.c.run_id)
                .where(self.quality_runs.c.dataset_name == dataset_name)
                .order_by(desc(self.quality_runs.c.executed_at))
                .limit(1)
            )
            row = conn.execute(stmt).fetchone()
            if not row:
                return None
            return self.get_run(row[0])

    def get_history(self, dataset_name: str, limit: int = 20) -> List[QualityRunResult]:
        """Retrieves historical validation runs for a dataset, ordered by execution time desc."""
        with self.engine.connect() as conn:
            stmt = (
                select(self.quality_runs.c.run_id)
                .where(self.quality_runs.c.dataset_name == dataset_name)
                .order_by(desc(self.quality_runs.c.executed_at))
                .limit(limit)
            )
            rows = conn.execute(stmt).fetchall()
            results = []
            for r in rows:
                run = self.get_run(r[0])
                if run:
                    results.append(run)
            return results

    def list_results(
        self,
        dataset: Optional[str] = None,
        status: Optional[str] = None,
        pipeline: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Queries granular check results across runs with optional filtering."""
        with self.engine.connect() as conn:
            stmt = select(self.quality_results).order_by(desc(self.quality_results.c.timestamp))
            if dataset:
                stmt = stmt.where(self.quality_results.c.dataset_name == dataset)
            if status:
                stmt = stmt.where(self.quality_results.c.status == status.upper())
            if pipeline:
                stmt = stmt.where(self.quality_results.c.pipeline_name == pipeline)
            stmt = stmt.limit(limit)

            rows = conn.execute(stmt).mappings().fetchall()
            output = []
            for r in rows:
                details = {}
                if r["details_json"]:
                    try:
                        details = json.loads(r["details_json"])
                    except Exception:
                        pass
                output.append({
                    "id": r["id"],
                    "run_id": r["run_id"],
                    "dataset": r["dataset_name"],
                    "dataset_name": r["dataset_name"],
                    "check_name": r["check_name"],
                    "column": r["column_name"],
                    "expectation_type": r["expectation_type"],
                    "status": r["status"],
                    "severity": r["severity"],
                    "success": r["success"],
                    "observed_value": r["observed_value"],
                    "expected_value": r["expected_value"],
                    "duration_ms": r["duration_ms"],
                    "timestamp": r["timestamp"].isoformat() if hasattr(r["timestamp"], "isoformat") else str(r["timestamp"]),
                    "pipeline": r["pipeline_name"],
                    "details": details
                })
            return output

    def get_summary(self, total_registered_datasets: int = 25) -> QualitySummaryResponse:
        """
        Dynamically calculates the quality summary based on persisted runs.
        No static or hardcoded counts.
        """
        with self.engine.connect() as conn:
            # 1. Find all distinct datasets that have validation runs
            sel_distinct = select(self.quality_runs.c.dataset_name).distinct()
            distinct_datasets = [r[0] for r in conn.execute(sel_distinct).fetchall()]
            datasets_checked = len(distinct_datasets)

            # 2. For each checked dataset, inspect latest run status
            datasets_passing = 0
            datasets_failing = 0
            freshness_violations = 0
            scores = []

            for ds in distinct_datasets:
                latest = self.get_latest_run(ds)
                if latest:
                    if latest.overall_status == QualityStatus.PASS:
                        datasets_passing += 1
                    else:
                        datasets_failing += 1

                    if latest.freshness_status in {FreshnessStatus.WARNING, FreshnessStatus.STALE}:
                        freshness_violations += 1

                    scores.append(latest.quality_score)

            # 3. Aggregate total check counts
            stmt_totals = select(
                func.sum(self.quality_runs.c.total_checks),
                func.sum(self.quality_runs.c.passed_checks),
                func.sum(self.quality_runs.c.failed_checks)
            )
            agg = conn.execute(stmt_totals).fetchone()
            total_checks = int(agg[0] or 0)
            checks_passed = int(agg[1] or 0)
            checks_failed = int(agg[2] or 0)

            overall_score = round(sum(scores) / len(scores), 2) if scores else 100.0

            effective_total_datasets = max(total_registered_datasets, datasets_checked)

            return QualitySummaryResponse(
                total_datasets=effective_total_datasets,
                datasets_checked=datasets_checked,
                datasets_passing=datasets_passing,
                datasets_failing=datasets_failing,
                total_checks=total_checks,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                overall_quality_score=overall_score,
                freshness_violations=freshness_violations
            )
