"""
DataGuard Pipeline Orchestrator (Phase G).
Executes end-to-end data platform workflows combining:
- Contract loading & verification
- Schema diff & breaking change gating
- Great Expectations automated quality checks
- OpenLineage standard lifecycle & facet emission
- Incident management with owner attribution & deduplication
- Persistent pipeline execution tracking and Prometheus metrics
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import pandas as pd

from dataguard.contracts.registry import ContractRegistryService, ContractNotFoundError
from dataguard.schema.diff import SchemaDiffEngine
from dataguard.schema.models import DiffSeverity
from dataguard.quality.runner import DataQualityRunner
from dataguard.quality.models import QualityRunResult, QualityStatus, QualityCheckResult
from dataguard.quality.datasets import DatasetCatalog
from dataguard.lineage.collector import LineageCollector
from dataguard.incidents.manager import IncidentManager
from dataguard.incidents.models import Incident
from dataguard.pipelines.repository import PipelineRepository
from dataguard.pipelines.models import PipelineRunStatus, PipelineRun
from dataguard.pipelines.freshness import FreshnessMonitorService
from dataguard.metrics import (
    PIPELINE_RUNS_TOTAL,
    PIPELINE_SUCCESS_TOTAL,
    PIPELINE_FAILURE_TOTAL,
    PIPELINE_DURATION_SECONDS,
    PIPELINE_RETRIES_TOTAL,
    PIPELINE_QUALITY_FAILURES_TOTAL
)

logger = logging.getLogger("dataguard.pipelines.orchestrator")


class PipelineExecutionError(Exception):
    """Raised when a data pipeline encounters a deterministic or critical failure."""
    def __init__(self, message: str, run_id: str, pipeline_id: str, stage: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.run_id = run_id
        self.pipeline_id = pipeline_id
        self.stage = stage
        self.details = details or {}


class TransientInfrastructureError(Exception):
    """Raised when a retryable infrastructure error occurs."""
    pass


class DataGuardPipelineOrchestrator:
    """
    Unified execution engine for Airflow DAGs and DataGuard pipelines.
    """

    def __init__(
        self,
        repository: Optional[PipelineRepository] = None,
        registry_service: Optional[ContractRegistryService] = None,
        quality_runner: Optional[DataQualityRunner] = None,
        lineage_collector: Optional[LineageCollector] = None,
        incident_manager: Optional[IncidentManager] = None,
        freshness_service: Optional[FreshnessMonitorService] = None
    ):
        self.repository = repository or PipelineRepository()
        self.registry = registry_service or ContractRegistryService()
        self.incident_manager = incident_manager or IncidentManager()
        self.quality_runner = quality_runner or DataQualityRunner(
            registry_service=self.registry,
            incident_manager=self.incident_manager
        )
        self.lineage_collector = lineage_collector or LineageCollector()
        self.freshness_service = freshness_service or FreshnessMonitorService(
            registry_service=self.registry,
            incident_manager=self.incident_manager
        )

    def execute_pipeline(
        self,
        pipeline_id: str,
        dataset_name: Optional[str] = None,
        df: Optional[pd.DataFrame] = None,
        run_id: Optional[str] = None,
        validate_schema: bool = True,
        validate_freshness: bool = True,
        test_scenario: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_transient_retries: int = 2,
        raise_on_failure: bool = True
    ) -> Dict[str, Any]:
        """
        Executes the full DataGuard pipeline lifecycle.
        Returns a rich execution result dictionary.
        """
        start_time = time.perf_counter()
        active_run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        
        # 1. Resolve pipeline metadata & target dataset
        pipe_meta = self.repository.get_pipeline(pipeline_id)
        target_dataset = dataset_name or (pipe_meta.dataset if pipe_meta else pipeline_id.replace("_quality_pipeline", "").replace("_pipeline", ""))
        
        logger.info(
            "Starting pipeline execution: pipeline_id=%s run_id=%s dataset=%s scenario=%s",
            pipeline_id, active_run_id, target_dataset, test_scenario
        )

        # 2. Record run start in DB & emit OpenLineage START
        self.repository.record_run_start(
            run_id=active_run_id,
            pipeline_id=pipeline_id,
            dataset=target_dataset
        )
        self.lineage_collector.start_run(
            pipeline_id=pipeline_id,
            run_id=active_run_id,
            job_name=pipeline_id,
            inputs=[target_dataset]
        )

        retry_count = 0
        while True:
            try:
                result = self._execute_lifecycle(
                    pipeline_id=pipeline_id,
                    run_id=active_run_id,
                    dataset_name=target_dataset,
                    df=df,
                    validate_schema=validate_schema,
                    validate_freshness=validate_freshness,
                    test_scenario=test_scenario,
                    timeout_seconds=timeout_seconds
                )
                
                # Success flow
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                duration_sec = duration_ms / 1000.0
                
                self.repository.record_run_finish(
                    run_id=active_run_id,
                    status=PipelineRunStatus.SUCCESS,
                    duration_ms=duration_ms,
                    quality_run_id=result.get("quality_run_id"),
                    incident_id=result.get("incident_id"),
                    lineage_run_id=active_run_id,
                    retry_count=retry_count,
                    metrics={
                        "duration_ms": duration_ms,
                        "quality_score": result.get("quality_score", 100.0),
                        "checks_passed": result.get("checks_passed", 0)
                    }
                )

                # OpenLineage COMPLETE
                self.lineage_collector.complete_run(
                    run_id=active_run_id,
                    outputs=[f"{target_dataset}_clean"],
                    pipeline_id=pipeline_id,
                    job_name=pipeline_id
                )

                # Prometheus metrics
                PIPELINE_RUNS_TOTAL.labels(pipeline_id=pipeline_id, status="SUCCESS").inc()
                PIPELINE_SUCCESS_TOTAL.labels(pipeline_id=pipeline_id).inc()
                PIPELINE_DURATION_SECONDS.labels(pipeline_id=pipeline_id).observe(duration_sec)

                logger.info(
                    "Pipeline finished successfully: pipeline_id=%s run_id=%s duration=%.2fms",
                    pipeline_id, active_run_id, duration_ms
                )
                result["status"] = "SUCCESS"
                result["duration_ms"] = duration_ms
                result["run_id"] = active_run_id
                return result

            except TransientInfrastructureError as tie:
                retry_count += 1
                PIPELINE_RETRIES_TOTAL.labels(pipeline_id=pipeline_id).inc()
                if retry_count <= max_transient_retries:
                    logger.warning("Transient error on pipeline %s, retry %d/%d: %s", pipeline_id, retry_count, max_transient_retries, tie)
                    time.sleep(0.5 * (2 ** retry_count))
                    continue
                else:
                    return self._handle_pipeline_failure(
                        pipeline_id=pipeline_id,
                        run_id=active_run_id,
                        dataset=target_dataset,
                        start_time=start_time,
                        error=tie,
                        failure_type="infrastructure_timeout",
                        stage="infrastructure",
                        retry_count=retry_count,
                        raise_on_failure=raise_on_failure
                    )

            except Exception as ex:
                # Deterministic or quality failure: do not uselessly retry
                failure_type = "quality_failure" if isinstance(ex, PipelineExecutionError) else "system_error"
                stage = getattr(ex, "stage", "execution")
                return self._handle_pipeline_failure(
                    pipeline_id=pipeline_id,
                    run_id=active_run_id,
                    dataset=target_dataset,
                    start_time=start_time,
                    error=ex,
                    failure_type=failure_type,
                    stage=stage,
                    retry_count=retry_count,
                    raise_on_failure=raise_on_failure
                )

    def _execute_lifecycle(
        self,
        pipeline_id: str,
        run_id: str,
        dataset_name: str,
        df: Optional[pd.DataFrame],
        validate_schema: bool,
        validate_freshness: bool,
        test_scenario: Optional[str],
        timeout_seconds: float
    ) -> Dict[str, Any]:
        """
        Executes sequential stages: Load -> Schema Validate -> Quality Checks -> Freshness.
        """
        t0 = time.perf_counter()

        # Step A: Load and prepare dataset
        data_df = df
        if data_df is None:
            data_df = self._load_dataset(dataset_name)

        # Inject deterministic test scenario if requested
        if test_scenario:
            data_df = self._inject_test_scenario(data_df, dataset_name, test_scenario)

        # Step B: Load contract from registry
        contract_data = None
        try:
            contract_data = self.registry.get_contract(dataset_name)
        except ContractNotFoundError:
            # Check if dataset name maps to a standard contract
            if self.registry.get_contract(f"{dataset_name}.yaml"):
                contract_data = self.registry.get_contract(f"{dataset_name}.yaml")
        except Exception as e:
            logger.warning("Could not load contract for %s: %s", dataset_name, e)

        # Step C: Schema Compatibility Diff
        schema_changes = []
        if validate_schema and contract_data is not None:
            schema_changes = self._validate_schema_compatibility(
                dataset_name=dataset_name,
                df=data_df,
                contract=contract_data,
                pipeline_id=pipeline_id,
                run_id=run_id
            )

        # Step D: Freshness Monitoring
        freshness_res = None
        if validate_freshness and (pipeline_id == "freshness_monitoring_pipeline" or test_scenario == "stale_dataset"):
            force_stale = (test_scenario == "stale_dataset")
            freshness_res = self.freshness_service.evaluate_dataset_freshness(
                dataset_name=dataset_name,
                df=data_df,
                pipeline_id=pipeline_id,
                force_stale=force_stale
            )
            if not freshness_res.is_fresh:
                raise PipelineExecutionError(
                    message=f"Freshness SLA breach for {dataset_name}: delay {freshness_res.delay_minutes:.1f}m > SLA {freshness_res.sla_minutes}m",
                    run_id=run_id,
                    pipeline_id=pipeline_id,
                    stage="freshness_validation",
                    details=freshness_res.to_dict()
                )

        # Check timeout before Great Expectations
        if (time.perf_counter() - t0) > timeout_seconds:
            raise TransientInfrastructureError(f"Pipeline execution exceeded timeout of {timeout_seconds}s")

        # Step E: Great Expectations Quality Validation
        quality_res: QualityRunResult = self.quality_runner.run_validation(
            dataset_name=dataset_name,
            df=data_df,
            contract=contract_data,
            pipeline=pipeline_id,
            validate_referential=True,
            validate_freshness=False
        )

        incident_id = None
        if quality_res.failed_checks > 0 or quality_res.overall_status == QualityStatus.FAIL:
            PIPELINE_QUALITY_FAILURES_TOTAL.labels(pipeline_id=pipeline_id, dataset=dataset_name).inc()
            
            # Find the incident created by quality runner or create one
            first_fail = next((c for c in quality_res.checks if not c.success), None)
            if first_fail:
                inc = self.incident_manager.handle_check_failure(
                    check=first_fail,
                    dataset=dataset_name,
                    pipeline=pipeline_id,
                    contract=contract_data
                )
                if inc:
                    incident_id = inc.incident_id

            raise PipelineExecutionError(
                message=f"Quality validation failed with {quality_res.failed_checks} check failures (Score: {quality_res.quality_score:.1f})",
                run_id=run_id,
                pipeline_id=pipeline_id,
                stage="quality_validation",
                details={
                    "quality_run_id": quality_res.run_id,
                    "failed_checks": quality_res.failed_checks,
                    "incident_id": incident_id,
                    "quality_score": quality_res.quality_score
                }
            )

        return {
            "quality_run_id": quality_res.run_id,
            "quality_score": quality_res.quality_score,
            "total_checks": quality_res.total_checks,
            "checks_passed": quality_res.passed_checks,
            "failed_checks": quality_res.failed_checks,
            "freshness": freshness_res.to_dict() if freshness_res else None,
            "schema_changes": len(schema_changes),
            "incident_id": incident_id
        }

    def _validate_schema_compatibility(
        self,
        dataset_name: str,
        df: pd.DataFrame,
        contract: Dict[str, Any],
        pipeline_id: str,
        run_id: str
    ) -> List[Any]:
        """
        Extracts active schema from dataframe and compares against contract.
        Fails if breaking changes are detected.
        """
        # Build active target schema dict from DataFrame
        contract_cols_by_name = {col["name"]: col for col in contract.get("columns", []) if isinstance(col, dict) and "name" in col}
        active_columns = []
        for col_name, dtype in df.dtypes.items():
            col_str = str(col_name)
            matched = contract_cols_by_name.get(col_str)
            type_str = matched.get("type") if matched else "string"
            nullable = bool(df[col_name].isnull().any())
            active_columns.append({
                "name": col_str,
                "type": type_str,
                "nullable": nullable,
                "allowed_values": matched.get("allowed_values") if matched else None
            })

        active_contract = {
            "dataset": dataset_name,
            "version": "live_dataset",
            "owner": "database-inferred",
            "columns": active_columns
        }

        diff_res = SchemaDiffEngine.compare_contracts(
            baseline_contract=contract,
            target_contract=active_contract
        )

        breaking_changes = [c for c in diff_res.changes if c.severity == DiffSeverity.BREAKING]
        if diff_res.is_breaking or len(breaking_changes) > 0:
            # Breaking schema detected!
            first_breaking = breaking_changes[0] if breaking_changes else None
            err_desc = first_breaking.description if first_breaking else "Breaking schema drift detected"

            # Create incident for breaking schema
            check_result = QualityCheckResult(
                run_id=run_id,
                dataset=dataset_name,
                check_name=f"schema_compatibility_{dataset_name}",
                column=first_breaking.column if first_breaking else None,
                expectation_type="expect_schema_to_be_backward_compatible",
                status=QualityStatus.FAIL,
                success=False,
                observed_value=err_desc,
                expected_value="Backward compatible schema",
                details={"breaking_changes": len(breaking_changes)}
            )
            self.incident_manager.handle_check_failure(
                check=check_result,
                dataset=dataset_name,
                pipeline=pipeline_id,
                contract=contract
            )

            raise PipelineExecutionError(
                message=f"Breaking schema drift detected: {err_desc}",
                run_id=run_id,
                pipeline_id=pipeline_id,
                stage="schema_validation",
                details={"breaking_count": len(breaking_changes)}
            )

        return diff_res.changes

    def _load_dataset(self, dataset_name: str) -> pd.DataFrame:
        """
        Loads actual seeded dataset from DatasetCatalog.
        """
        df = DatasetCatalog.load_dataset(dataset_name)
        if df is not None:
            return df
        
        # If not in catalog, create a minimal fallback dataframe
        return pd.DataFrame([{"id": "rec_001", "name": "sample", "amount": 100.0}])

    def _inject_test_scenario(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        scenario: str
    ) -> pd.DataFrame:
        """
        Injects deterministic defect for demo test pipelines.
        """
        mod_df = df.copy()

        if scenario in ["null_failure", "null_violation"]:
            # Inject null into non-nullable column
            col = "email" if "email" in mod_df.columns else mod_df.columns[0]
            mod_df.loc[0:2, col] = None
        elif scenario in ["duplicate_failure", "duplicate_violation"]:
            # Duplicate the first row
            mod_df = pd.concat([mod_df, mod_df.iloc[[0]]], ignore_index=True)
        elif scenario in ["invalid_enum", "enum_violation"]:
            # Find status, kyc_status, or currency column and inject bogus enum
            enum_cols = [c for c in mod_df.columns if c in ["kyc_status", "risk_tier", "status", "currency", "state", "account_type"]]
            target_col = enum_cols[0] if enum_cols else mod_df.columns[-1]
            mod_df.loc[0, target_col] = "INVALID_BOGUS_STATUS_XYZ"
        elif scenario in ["referential_failure", "referential_violation"]:
            # Find foreign key column and inject non-existent ID
            fk_cols = [c for c in mod_df.columns if "id" in c and c != mod_df.columns[0]]
            target_col = fk_cols[0] if fk_cols else "customer_id"
            mod_df.loc[0, target_col] = "NON_EXISTENT_FK_999999"
        elif scenario in ["breaking_schema", "breaking_change"]:
            # Drop a critical column
            if len(mod_df.columns) > 1:
                mod_df = mod_df.drop(columns=[mod_df.columns[1]])

        return mod_df

    def _handle_pipeline_failure(
        self,
        pipeline_id: str,
        run_id: str,
        dataset: str,
        start_time: float,
        error: Exception,
        failure_type: str,
        stage: str,
        retry_count: int,
        raise_on_failure: bool
    ) -> Dict[str, Any]:
        """
        Unified failure callback:
        1. Logs failure
        2. Emits OpenLineage FAIL
        3. Updates pipeline_runs record
        4. Updates Prometheus metrics
        5. Raises exception or returns structured failure
        """
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        duration_sec = duration_ms / 1000.0
        err_msg = str(error)

        logger.error(
            "Pipeline failed: pipeline_id=%s run_id=%s stage=%s error=%s",
            pipeline_id, run_id, stage, err_msg
        )

        details = getattr(error, "details", {}) or {}
        incident_id = details.get("incident_id")
        quality_run_id = details.get("quality_run_id")
        quality_score = details.get("quality_score")
        failed_checks = details.get("failed_checks")

        # 1. Update pipeline_runs in PostgreSQL
        self.repository.record_run_finish(
            run_id=run_id,
            status=PipelineRunStatus.FAILED,
            duration_ms=duration_ms,
            quality_run_id=quality_run_id,
            incident_id=incident_id,
            lineage_run_id=run_id,
            error_message=f"[{stage}] {err_msg}",
            retry_count=retry_count,
            metrics={"duration_ms": duration_ms, "failed_stage": stage, "quality_score": quality_score, "failed_checks": failed_checks}
        )

        # 2. OpenLineage FAIL event
        self.lineage_collector.fail_run(
            run_id=run_id,
            pipeline_id=pipeline_id,
            job_name=pipeline_id,
            error_message=f"[{stage}] {err_msg}"
        )

        # 3. Prometheus metrics
        PIPELINE_RUNS_TOTAL.labels(pipeline_id=pipeline_id, status="FAILED").inc()
        PIPELINE_FAILURE_TOTAL.labels(pipeline_id=pipeline_id, failure_type=failure_type).inc()
        PIPELINE_DURATION_SECONDS.labels(pipeline_id=pipeline_id).observe(duration_sec)

        result = {
            "status": "FAILED",
            "run_id": run_id,
            "pipeline_id": pipeline_id,
            "dataset": dataset,
            "stage": stage,
            "error": err_msg,
            "error_message": err_msg,
            "incident_id": incident_id,
            "quality_run_id": quality_run_id,
            "quality_score": quality_score,
            "failed_checks": failed_checks,
            "duration_ms": duration_ms
        }

        if raise_on_failure:
            raise error

        return result
