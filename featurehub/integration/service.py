"""
FeatureHub + DataGuard Integrated Platform Orchestrator (Phase I).
Executes the unified end-to-end data platform flow:
Data Source -> Feature Computation -> DataGuard Contract Validation ->
DataGuard Schema Validation -> Great Expectations -> OpenLineage ->
Airflow -> FeatureHub Offline Store -> Materialization -> Redis ->
FeatureHub API -> ML Prediction.

And the failure path:
Bad Data / Breaking Schema / Stale Features -> DataGuard -> FAILED ->
OpenLineage FAILED RUN + Operational Incident (owner + severity).
"""

import time
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

from featurehub.integration.models import (
    IntegrationStage,
    StageStatus,
    IntegrationStageResult,
    IntegratedPipelineResult
)
from featurehub.computation.engine import compute_offline_features
from featurehub.online_store.redis_store import RedisOnlineStore
from featurehub.materialization.service import FeatureMaterializer
from featurehub.inference.predictor import RealTimePredictor

from dataguard.contracts.registry import ContractRegistryService
from dataguard.contracts.validator import ContractValidator
from dataguard.schema.diff import SchemaDiffEngine
from dataguard.schema.models import DiffSeverity, SchemaChange
from dataguard.quality.runner import DataQualityRunner
from dataguard.quality.models import QualityRunResult, QualityStatus, QualityCheckResult
from dataguard.lineage.collector import LineageCollector
from dataguard.incidents.manager import IncidentManager
from dataguard.incidents.models import Incident, IncidentSeverity
from dataguard.pipelines.repository import PipelineRepository
from dataguard.pipelines.models import PipelineRunStatus
from dataguard.pipelines.freshness import FreshnessMonitorService

logger = logging.getLogger("featurehub.integration")

PIPELINE_ID = "integrated_feature_store_pipeline"
DEFAULT_DATASET = "customer_features"
OFFLINE_STORE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "offline_store"


class FeatureHubDataGuardIntegrator:
    """
    Unified end-to-end orchestrator binding FeatureHub and DataGuard
    into a coherent, production-grade data platform.
    """

    def __init__(
        self,
        registry_service: Optional[ContractRegistryService] = None,
        incident_manager: Optional[IncidentManager] = None,
        quality_runner: Optional[DataQualityRunner] = None,
        lineage_collector: Optional[LineageCollector] = None,
        pipeline_repo: Optional[PipelineRepository] = None,
        online_store: Optional[RedisOnlineStore] = None,
        predictor: Optional[RealTimePredictor] = None
    ):
        self.registry = registry_service or ContractRegistryService()
        self.incident_manager = incident_manager or IncidentManager()
        self.quality_runner = quality_runner or DataQualityRunner(
            registry_service=self.registry,
            incident_manager=self.incident_manager
        )
        self.lineage_collector = lineage_collector or LineageCollector()
        self.pipeline_repo = pipeline_repo or PipelineRepository()
        self.online_store = online_store or RedisOnlineStore()
        self.materializer = FeatureMaterializer(online_store=self.online_store)
        self.predictor = predictor or RealTimePredictor(online_store=self.online_store)
        self.freshness_service = FreshnessMonitorService(
            registry_service=self.registry,
            incident_manager=self.incident_manager
        )

    def run_e2e_pipeline(
        self,
        dataset_name: str = DEFAULT_DATASET,
        target_customer_id: str = "cust_000001",
        as_of_timestamp: Optional[str] = None,
        inject_anomaly: Optional[str] = None,
        allow_breaking: bool = False
    ) -> IntegratedPipelineResult:
        """
        Executes the genuine end-to-end integration flow across all 11 stages.
        """
        pipeline_start = time.perf_counter()
        run_id = f"run_e2e_{uuid.uuid4().hex[:8]}"
        stages: List[IntegrationStageResult] = []

        result = IntegratedPipelineResult(
            pipeline_id=PIPELINE_ID,
            run_id=run_id,
            status=StageStatus.SUCCESS,
            dataset_name=dataset_name,
            stages=stages
        )

        # Start OpenLineage execution run
        self.lineage_collector.start_run(
            pipeline_id=PIPELINE_ID,
            run_id=run_id,
            job_name=PIPELINE_ID,
            inputs=["transactions", "merchants"]
        )
        result.openlineage_run_id = run_id

        # Record pipeline start in repository
        self.pipeline_repo.record_run_start(
            run_id=run_id,
            pipeline_id=PIPELINE_ID,
            dataset=dataset_name
        )

        try:
            # ------------------------------------------------------------------
            # Stage 1: Data Source Verification
            # ------------------------------------------------------------------
            s1_t0 = time.perf_counter()
            data_raw_dir = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
            txns_file = data_raw_dir / "transactions.parquet"
            merch_file = data_raw_dir / "merchants.parquet"

            if not txns_file.exists() or not merch_file.exists():
                raise FileNotFoundError(f"Raw source datasets missing in {data_raw_dir}")

            s1_ms = (time.perf_counter() - s1_t0) * 1000.0
            stages.append(IntegrationStageResult(
                stage=IntegrationStage.DATA_SOURCE,
                status=StageStatus.SUCCESS,
                duration_ms=round(s1_ms, 2),
                details={"transactions_path": str(txns_file), "merchants_path": str(merch_file)}
            ))

            # ------------------------------------------------------------------
            # Stage 2: Feature Computation
            # ------------------------------------------------------------------
            s2_t0 = time.perf_counter()
            computed_dict = compute_offline_features(as_of_timestamp=as_of_timestamp)
            df_features = computed_dict.get(dataset_name)

            if df_features is None or df_features.empty:
                raise ValueError(f"Feature computation produced empty or missing dataset: {dataset_name}")

            # Deep copy so injected anomalies do not pollute cached memory
            df_features = df_features.copy()

            # Stamp observation timestamp to current execution unless testing stale features
            if inject_anomaly != "STALE_FEATURES":
                df_features["feature_timestamp"] = datetime.now(timezone.utc).isoformat()

            # Anomaly Injection Hook (for verifying failure paths)
            if inject_anomaly == "BREAKING_SCHEMA":
                # Drop an essential column or corrupt a type
                if "cust_txn_count_24h" in df_features.columns:
                    df_features.drop(columns=["cust_txn_count_24h"], inplace=True)
                elif "cust_txn_count_1h" in df_features.columns:
                    df_features.drop(columns=["cust_txn_count_1h"], inplace=True)
            elif inject_anomaly == "NULL_VIOLATION":
                # Inject illegal NULL into primary key or non-nullable column
                df_features.loc[0, "customer_id"] = None
            elif inject_anomaly == "RANGE_VIOLATION":
                # Inject negative or absurd value exceeding bounds
                if "cust_txn_amount_sum_24h" in df_features.columns:
                    df_features.loc[0, "cust_txn_amount_sum_24h"] = -99999.0
            elif inject_anomaly == "STALE_FEATURES":
                # Shift timestamp far in the past
                stale_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
                df_features["feature_timestamp"] = stale_ts

            s2_ms = (time.perf_counter() - s2_t0) * 1000.0
            result.features_computed_count = len(df_features)
            stages.append(IntegrationStageResult(
                stage=IntegrationStage.FEATURE_COMPUTATION,
                status=StageStatus.SUCCESS,
                duration_ms=round(s2_ms, 2),
                details={"rows_computed": len(df_features), "feature_columns": list(df_features.columns)}
            ))

            # ------------------------------------------------------------------
            # Stage 3: DataGuard Contract Validation
            # ------------------------------------------------------------------
            s3_t0 = time.perf_counter()
            contract_data = None
            try:
                contract_data = self.registry.get_contract(dataset_name)
            except Exception:
                pass

            if contract_data is None:
                # Load from file directly
                contract_file = Path(__file__).resolve().parent.parent.parent / "dataguard" / "contracts" / f"{dataset_name}.yaml"
                if contract_file.exists():
                    import yaml
                    with open(contract_file, "r", encoding="utf-8") as f:
                        contract_data = yaml.safe_load(f)

            if not contract_data:
                raise ValueError(f"No contract definition found for dataset '{dataset_name}'")

            is_valid, val_errors = ContractValidator.validate_contract(contract_data)
            if not is_valid:
                s3_ms = (time.perf_counter() - s3_t0) * 1000.0
                err_msg = f"Contract validation failed: {val_errors}"
                stages.append(IntegrationStageResult(
                    stage=IntegrationStage.CONTRACT_VALIDATION,
                    status=StageStatus.FAILED,
                    duration_ms=round(s3_ms, 2),
                    error=err_msg
                ))
                return self._abort_with_failure(
                    result=result,
                    stages=stages,
                    failed_stage=IntegrationStage.CONTRACT_VALIDATION,
                    error_message=err_msg,
                    contract=contract_data,
                    severity=IncidentSeverity.CRITICAL,
                    start_time=pipeline_start
                )

            s3_ms = (time.perf_counter() - s3_t0) * 1000.0
            stages.append(IntegrationStageResult(
                stage=IntegrationStage.CONTRACT_VALIDATION,
                status=StageStatus.SUCCESS,
                duration_ms=round(s3_ms, 2),
                details={"version": contract_data.get("version"), "owner": contract_data.get("owner")}
            ))

            # ------------------------------------------------------------------
            # Stage 4: DataGuard Schema Compatibility & Drift Validation
            # ------------------------------------------------------------------
            s4_t0 = time.perf_counter()
            schema_changes, is_breaking = self._validate_schema_compatibility(
                dataset_name=dataset_name,
                df=df_features,
                contract=contract_data
            )
            s4_ms = (time.perf_counter() - s4_t0) * 1000.0

            if is_breaking and not allow_breaking:
                result.schema_compatible = False
                err_msg = f"Breaking schema drift detected in computed features '{dataset_name}'."
                stages.append(IntegrationStageResult(
                    stage=IntegrationStage.SCHEMA_VALIDATION,
                    status=StageStatus.FAILED,
                    duration_ms=round(s4_ms, 2),
                    error=err_msg,
                    details={"changes": [str(c) for c in schema_changes]}
                ))
                failing_check = QualityCheckResult(
                    run_id=result.run_id,
                    dataset=dataset_name,
                    check_name=f"schema_compatibility_{dataset_name}",
                    column=None,
                    expectation_type="expect_schema_to_be_backward_compatible",
                    status=QualityStatus.FAIL,
                    success=False,
                    observed_value=err_msg,
                    expected_value="Backward compatible schema"
                )
                return self._abort_with_failure(
                    result=result,
                    stages=stages,
                    failed_stage=IntegrationStage.SCHEMA_VALIDATION,
                    error_message=err_msg,
                    contract=contract_data,
                    severity=IncidentSeverity.CRITICAL,
                    failing_check=failing_check,
                    start_time=pipeline_start
                )

            stages.append(IntegrationStageResult(
                stage=IntegrationStage.SCHEMA_VALIDATION,
                status=StageStatus.SUCCESS,
                duration_ms=round(s4_ms, 2),
                details={"schema_changes_count": len(schema_changes)}
            ))

            # ------------------------------------------------------------------
            # Stage 5: Great Expectations Quality Validation
            # ------------------------------------------------------------------
            s5_t0 = time.perf_counter()
            quality_res: QualityRunResult = self.quality_runner.run_validation(
                dataset_name=dataset_name,
                df=df_features,
                contract=contract_data,
                pipeline=PIPELINE_ID,
                validate_referential=False,
                validate_freshness=True
            )
            s5_ms = (time.perf_counter() - s5_t0) * 1000.0
            result.quality_score = quality_res.quality_score

            if quality_res.failed_checks > 0 or quality_res.overall_status == QualityStatus.FAIL:
                first_fail = next((c for c in quality_res.checks if not c.success), None)
                err_msg = (
                    f"Quality validation failed with {quality_res.failed_checks} failures. "
                    f"Score: {quality_res.quality_score:.1f}% (Required: 100.0%)"
                )
                stages.append(IntegrationStageResult(
                    stage=IntegrationStage.DATA_QUALITY,
                    status=StageStatus.FAILED,
                    duration_ms=round(s5_ms, 2),
                    error=err_msg,
                    details={
                        "failed_checks": quality_res.failed_checks,
                        "quality_score": quality_res.quality_score,
                        "first_failure": first_fail.check_name if first_fail else None
                    }
                ))

                # Route incident according to failure policy
                sev = IncidentSeverity.HIGH
                if first_fail and ("null" in first_fail.expectation_type or "pk" in first_fail.expectation_type):
                    sev = IncidentSeverity.CRITICAL

                return self._abort_with_failure(
                    result=result,
                    stages=stages,
                    failed_stage=IntegrationStage.DATA_QUALITY,
                    error_message=err_msg,
                    contract=contract_data,
                    severity=sev,
                    failing_check=first_fail,
                    start_time=pipeline_start
                )

            stages.append(IntegrationStageResult(
                stage=IntegrationStage.DATA_QUALITY,
                status=StageStatus.SUCCESS,
                duration_ms=round(s5_ms, 2),
                details={"quality_score": quality_res.quality_score, "passed_checks": quality_res.passed_checks}
            ))

            # ------------------------------------------------------------------
            # Stage 6: OpenLineage Complete Run Emission
            # ------------------------------------------------------------------
            s6_t0 = time.perf_counter()
            self.lineage_collector.complete_run(
                run_id=run_id,
                outputs=[dataset_name],
                pipeline_id=PIPELINE_ID,
                job_name=PIPELINE_ID
            )
            s6_ms = (time.perf_counter() - s6_t0) * 1000.0
            stages.append(IntegrationStageResult(
                stage=IntegrationStage.OPENLINEAGE,
                status=StageStatus.SUCCESS,
                duration_ms=round(s6_ms, 2),
                details={"run_id": run_id, "event_type": "COMPLETE"}
            ))

            # ------------------------------------------------------------------
            # Stage 7: Airflow Pipeline Tracking
            # ------------------------------------------------------------------
            s7_t0 = time.perf_counter()
            self.pipeline_repo.record_run_finish(
                run_id=run_id,
                status=PipelineRunStatus.SUCCESS,
                duration_ms=(time.perf_counter() - pipeline_start) * 1000.0,
                quality_run_id=quality_res.run_id,
                lineage_run_id=run_id,
                metrics={"records_processed": len(df_features)}
            )
            s7_ms = (time.perf_counter() - s7_t0) * 1000.0
            stages.append(IntegrationStageResult(
                stage=IntegrationStage.AIRFLOW_ORCHESTRATION,
                status=StageStatus.SUCCESS,
                duration_ms=round(s7_ms, 2),
                details={"pipeline_id": PIPELINE_ID, "run_id": run_id}
            ))

            # ------------------------------------------------------------------
            # Stage 8: FeatureHub Offline Store Persistence
            # ------------------------------------------------------------------
            s8_t0 = time.perf_counter()
            OFFLINE_STORE_DIR.mkdir(parents=True, exist_ok=True)
            offline_parquet = OFFLINE_STORE_DIR / f"{dataset_name}.parquet"
            df_features.to_parquet(offline_parquet, index=False)
            s8_ms = (time.perf_counter() - s8_t0) * 1000.0
            stages.append(IntegrationStageResult(
                stage=IntegrationStage.OFFLINE_STORE,
                status=StageStatus.SUCCESS,
                duration_ms=round(s8_ms, 2),
                details={"file_path": str(offline_parquet), "rows_saved": len(df_features)}
            ))

            # ------------------------------------------------------------------
            # Stage 9: Feature Materialization to Redis
            # ------------------------------------------------------------------
            s9_t0 = time.perf_counter()
            mat_records = 0
            for _, row in df_features.iterrows():
                cid = str(row["customer_id"])
                ts = str(row["feature_timestamp"])
                feat_dict = {
                    k: v for k, v in row.to_dict().items()
                    if k not in ["customer_id", "feature_timestamp"]
                }
                self.online_store.put_online_features(
                    entity_name="customer",
                    entity_id=cid,
                    feature_vector=feat_dict,
                    feature_timestamp=ts
                )
                mat_records += 1

            s9_ms = (time.perf_counter() - s9_t0) * 1000.0
            result.records_materialized_count = mat_records
            stages.append(IntegrationStageResult(
                stage=IntegrationStage.MATERIALIZATION,
                status=StageStatus.SUCCESS,
                duration_ms=round(s9_ms, 2),
                details={"records_materialized": mat_records}
            ))

            # ------------------------------------------------------------------
            # Stage 10: Redis Online Store Verification
            # ------------------------------------------------------------------
            s10_t0 = time.perf_counter()
            target_cid = target_customer_id
            if not df_features.empty and target_cid not in df_features["customer_id"].values:
                target_cid = str(df_features["customer_id"].iloc[0])

            retrieved = self.online_store.get_online_features(
                entity_name="customer",
                entity_id=target_cid
            )
            s10_ms = (time.perf_counter() - s10_t0) * 1000.0
            stages.append(IntegrationStageResult(
                stage=IntegrationStage.REDIS_ONLINE_STORE,
                status=StageStatus.SUCCESS,
                duration_ms=round(s10_ms, 2),
                details={
                    "entity_id": target_cid,
                    "retrieved": retrieved is not None,
                    "features_count": len(retrieved.get("features", {})) if retrieved else 0
                }
            ))

            # ------------------------------------------------------------------
            # Stage 11: FeatureHub API & ML Prediction
            # ------------------------------------------------------------------
            s11_t0 = time.perf_counter()
            prediction_output = self.predictor.predict_fraud_risk(
                customer_id=target_cid,
                transaction_amount=250.0,
                merchant_id="merch_001",
                timestamp=datetime.now(timezone.utc).isoformat(),
                channel="MOBILE_APP"
            )
            s11_ms = (time.perf_counter() - s11_t0) * 1000.0
            result.ml_prediction = prediction_output
            stages.append(IntegrationStageResult(
                stage=IntegrationStage.ML_PREDICTION,
                status=StageStatus.SUCCESS,
                duration_ms=round(s11_ms, 2),
                details=prediction_output
            ))

        except Exception as e:
            logger.exception("Unexpected exception in integrated pipeline: %s", e)
            return self._abort_with_failure(
                result=result,
                stages=stages,
                failed_stage=IntegrationStage.AIRFLOW_ORCHESTRATION,
                error_message=str(e),
                contract=contract_data or {"owner": "data-platform-team"},
                severity=IncidentSeverity.CRITICAL,
                start_time=pipeline_start
            )

        total_duration = (time.perf_counter() - pipeline_start) * 1000.0
        result.duration_ms = round(total_duration, 2)
        result.stages = stages
        result.status = StageStatus.SUCCESS
        return result

    def _validate_schema_compatibility(
        self,
        dataset_name: str,
        df: pd.DataFrame,
        contract: Dict[str, Any]
    ) -> Tuple[List[SchemaChange], bool]:
        """Validates computed DataFrame columns against the data contract."""
        contract_cols = {c["name"]: c for c in contract.get("columns", []) if isinstance(c, dict)}
        active_columns = []
        for col_name, dtype in df.dtypes.items():
            col_str = str(col_name)
            matched = contract_cols.get(col_str)
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

        is_breaking = (diff_res.is_breaking or any(c.severity == DiffSeverity.BREAKING for c in diff_res.changes))
        return diff_res.changes, is_breaking

    def _abort_with_failure(
        self,
        result: IntegratedPipelineResult,
        stages: List[IntegrationStageResult],
        failed_stage: IntegrationStage,
        error_message: str,
        contract: Dict[str, Any],
        severity: IncidentSeverity,
        start_time: float,
        failing_check: Optional[QualityCheckResult] = None
    ) -> IntegratedPipelineResult:
        """
        Handles the Failure Path:
        1. Emits OpenLineage FAIL RunEvent.
        2. Creates an operational incident in PostgreSQL with owner attribution and severity.
        3. Marks downstream stages SKIPPED.
        4. Halts execution to protect Redis and ML models from corrupted features.
        """
        # 1. Emit OpenLineage FAIL event
        self.lineage_collector.fail_run(
            run_id=result.run_id,
            error_message=error_message,
            pipeline_id=PIPELINE_ID,
            job_name=PIPELINE_ID
        )

        # 2. Create Incident with Owner Attribution
        owner = contract.get("owner", "featurestore-team")
        check_obj = failing_check or QualityCheckResult(
            run_id=result.run_id,
            dataset=result.dataset_name,
            check_name=f"{failed_stage.value.lower()}_check",
            column=None,
            expectation_type=f"expect_{failed_stage.value.lower()}_to_succeed",
            status=QualityStatus.FAIL,
            success=False,
            observed_value=error_message,
            expected_value="SUCCESS"
        )

        incident: Optional[Incident] = self.incident_manager.handle_check_failure(
            check=check_obj,
            dataset=result.dataset_name,
            pipeline=PIPELINE_ID,
            contract=contract
        )

        if incident:
            result.incident_id = incident.incident_id
            result.incident_owner = incident.owner
            result.incident_severity = incident.severity.value
        else:
            result.incident_owner = owner
            result.incident_severity = severity.value

        # 3. Mark skipped stages
        all_stages = [
            IntegrationStage.DATA_SOURCE,
            IntegrationStage.FEATURE_COMPUTATION,
            IntegrationStage.CONTRACT_VALIDATION,
            IntegrationStage.SCHEMA_VALIDATION,
            IntegrationStage.DATA_QUALITY,
            IntegrationStage.OPENLINEAGE,
            IntegrationStage.AIRFLOW_ORCHESTRATION,
            IntegrationStage.OFFLINE_STORE,
            IntegrationStage.MATERIALIZATION,
            IntegrationStage.REDIS_ONLINE_STORE,
            IntegrationStage.ML_PREDICTION
        ]

        executed_stages = {s.stage for s in stages}
        for s in all_stages:
            if s not in executed_stages:
                stages.append(IntegrationStageResult(
                    stage=s,
                    status=StageStatus.SKIPPED,
                    details={"reason": f"Execution halted due to failure in {failed_stage.value}"}
                ))

        # 4. Record failed run in pipeline history
        self.pipeline_repo.record_run_finish(
            run_id=result.run_id,
            status=PipelineRunStatus.FAILED,
            duration_ms=(time.perf_counter() - start_time) * 1000.0,
            error_message=error_message,
            incident_id=result.incident_id,
            lineage_run_id=result.run_id
        )

        result.stages = stages
        result.status = StageStatus.FAILED
        result.error_message = error_message
        result.duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return result
