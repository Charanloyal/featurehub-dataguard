"""
DataGuard Data Quality Validation Runner.
Orchestrates Great Expectations suites, freshness evaluations, and referential integrity checks.
Persists execution runs to PostgreSQL and updates Prometheus observability metrics.
"""

import time
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
import pandas as pd
import great_expectations as gx

from dataguard.contracts.registry import ContractRegistryService, ContractNotFoundError
from dataguard.quality.models import (
    QualityStatus,
    QualitySeverity,
    FreshnessStatus,
    QualityCheckResult,
    QualityRunResult
)
from dataguard.quality.expectations import ContractExpectationBuilder
from dataguard.quality.freshness import FreshnessValidator
from dataguard.quality.referential import ReferentialIntegrityValidator
from dataguard.quality.datasets import DatasetCatalog
from dataguard.quality.result_store import QualityResultStore
from dataguard.metrics import (
    QUALITY_VALIDATION_TOTAL,
    QUALITY_VALIDATION_FAILURES_TOTAL,
    QUALITY_CHECKS_TOTAL,
    QUALITY_CHECK_FAILURES_TOTAL,
    QUALITY_VALIDATION_DURATION_SECONDS,
    FRESHNESS_VIOLATIONS_TOTAL
)


class DataQualityRunner:
    """
    Executes automated data quality validation against data contracts using Great Expectations.
    Calculates dynamic quality score, evaluates freshness, and verifies referential integrity.
    """

    def __init__(
        self,
        registry_service: Optional[ContractRegistryService] = None,
        result_store: Optional[QualityResultStore] = None,
        incident_manager: Optional[Any] = None
    ):
        self.registry = registry_service or ContractRegistryService()
        self.result_store = result_store or QualityResultStore()
        self.incident_manager = incident_manager

    def run_validation(
        self,
        dataset_name: str,
        df: Optional[pd.DataFrame] = None,
        version: Optional[str] = None,
        contract: Optional[Dict[str, Any]] = None,
        pipeline: str = "default_pipeline",
        validate_referential: bool = True,
        validate_freshness: bool = True,
        create_incidents: bool = True
    ) -> QualityRunResult:
        """
        Executes complete quality validation workflow:
        1. Loads contract and dataset
        2. Compiles Great Expectations suite
        3. Evaluates expectations via GX engine
        4. Evaluates dataset freshness against contract SLA
        5. Evaluates relational foreign key constraints
        6. Computes quality score and aggregates overall status
        7. Persists execution to PostgreSQL
        8. Increments Prometheus metrics
        """
        start_time = time.perf_counter()
        run_id = f"run_{uuid.uuid4().hex[:12]}"

        # 1. Retrieve Contract
        active_contract = contract
        if active_contract is None:
            active_contract = self.registry.get_contract(dataset_name, version=version)
            if not active_contract:
                raise ContractNotFoundError(
                    f"Contract for dataset '{dataset_name}' (version '{version or 'latest'}') not found in registry."
                )

        contract_version = active_contract.get("version", version or "v1.0.0")

        # 2. Retrieve / Load Dataset
        active_df = df
        if active_df is None:
            active_df = DatasetCatalog.load_dataset(dataset_name)

        if not isinstance(active_df, pd.DataFrame):
            raise ValueError(f"Target dataset '{dataset_name}' must be a pandas DataFrame.")

        row_count = len(active_df)

        # 3. Build Great Expectations Suite
        gx_context = gx.get_context(mode="ephemeral")
        suite, severity_map = ContractExpectationBuilder.build_suite_for_contract(
            context=gx_context,
            contract=active_contract,
            suite_name=f"suite_{dataset_name}_{run_id}"
        )

        # 4. Execute GX Validation
        data_source = gx_context.data_sources.add_pandas(f"ds_{run_id}")
        data_asset = data_source.add_dataframe_asset(f"asset_{dataset_name}")
        batch_def = data_asset.add_batch_definition_whole_dataframe(f"bd_{run_id}")

        val_def = gx_context.validation_definitions.add(
            gx.ValidationDefinition(
                name=f"val_def_{run_id}",
                data=batch_def,
                suite=suite
            )
        )

        gx_results = val_def.run(batch_parameters={"dataframe": active_df})

        # 5. Parse and map GX Results to QualityCheckResult
        check_results: List[QualityCheckResult] = []

        for r in gx_results.results:
            exp_type = r.expectation_config.type
            kwargs = r.expectation_config.kwargs or {}
            col = kwargs.get("column")
            map_key = f"{exp_type}:{col or '(table)'}"
            severity = severity_map.get(map_key, ContractExpectationBuilder.get_expectation_severity(exp_type))

            success = bool(r.success)
            status = QualityStatus.PASS if success else QualityStatus.FAIL

            # Diagnostic extraction
            obs_val = None
            if not success:
                if r.exception_info and r.exception_info.get("raised_exception"):
                    obs_val = r.exception_info.get("exception_message")
                elif r.result:
                    unexp_cnt = r.result.get("unexpected_count")
                    unexp_pct = r.result.get("unexpected_percent")
                    if unexp_cnt is not None:
                        obs_val = f"{unexp_cnt} unexpected records ({unexp_pct:.2f}%)" if unexp_pct else f"{unexp_cnt} unexpected"
            else:
                obs_val = "Compliant (0 unexpected)"

            # Expected value extraction
            exp_val = None
            if "value_set" in kwargs:
                exp_val = f"in {kwargs['value_set']}"
            elif "min_value" in kwargs or "max_value" in kwargs:
                exp_val = f"between {kwargs.get('min_value')} and {kwargs.get('max_value')}"
            else:
                exp_val = "Invariant satisfied"

            check_name = f"{exp_type}_{col}" if col else exp_type

            check_results.append(QualityCheckResult(
                run_id=run_id,
                dataset=dataset_name,
                check_name=check_name,
                column=col,
                expectation_type=exp_type,
                status=status,
                severity=severity,
                observed_value=obs_val,
                expected_value=exp_val,
                success=success,
                pipeline=pipeline,
                details=r.result or {}
            ))

        # 6. Freshness Validation
        freshness_status = FreshnessStatus.UNKNOWN
        freshness_delay = None
        last_rec_ts = None

        if validate_freshness:
            freshness_res = FreshnessValidator.evaluate_freshness(
                df=active_df,
                contract=active_contract
            )
            freshness_status = freshness_res["status"]
            freshness_delay = freshness_res["delay_minutes"]
            last_rec_ts = freshness_res["last_record_timestamp"]

            if freshness_status == FreshnessStatus.FRESH:
                fresh_status_enum = QualityStatus.PASS
                fresh_success = True
            elif freshness_status == FreshnessStatus.WARNING:
                fresh_status_enum = QualityStatus.WARNING
                fresh_success = True
            else:
                fresh_status_enum = QualityStatus.FAIL
                fresh_success = False

            check_results.append(QualityCheckResult(
                run_id=run_id,
                dataset=dataset_name,
                check_name=f"freshness_sla_{dataset_name}",
                column=freshness_res.get("column_used"),
                expectation_type="expect_dataset_freshness_within_sla",
                status=fresh_status_enum,
                severity=QualitySeverity.HIGH,
                observed_value=f"Latency: {freshness_delay}m" if freshness_delay is not None else "No timestamp",
                expected_value=f"SLA: <= {freshness_res.get('sla_minutes')}m",
                success=fresh_success,
                pipeline=pipeline,
                details=freshness_res
            ))

        # 7. Referential Integrity Checks
        if validate_referential:
            fk_specs = ReferentialIntegrityValidator.get_relationships(dataset_name)
            for child_fk, parent_ds, parent_pk in fk_specs:
                try:
                    parent_df = DatasetCatalog.load_dataset(parent_ds)
                    ref_check = ReferentialIntegrityValidator.validate_referential_integrity(
                        run_id=run_id,
                        child_dataset=dataset_name,
                        child_df=active_df,
                        parent_dataset=parent_ds,
                        parent_df=parent_df,
                        child_fk_col=child_fk,
                        parent_pk_col=parent_pk,
                        pipeline=pipeline
                    )
                    check_results.append(ref_check)
                except Exception as e:
                    check_results.append(QualityCheckResult(
                        run_id=run_id,
                        dataset=dataset_name,
                        check_name=f"foreign_key_{dataset_name}_{child_fk}_in_{parent_ds}",
                        column=child_fk,
                        expectation_type="expect_column_values_to_match_foreign_key",
                        status=QualityStatus.WARNING,
                        severity=QualitySeverity.MEDIUM,
                        observed_value=f"Error evaluating referential check: {e}",
                        expected_value=f"Reference to {parent_ds}.{parent_pk}",
                        success=False,
                        pipeline=pipeline,
                        details={"error": str(e)}
                    ))

        # 8. Compute Transparent Quality Score
        total_checks = len(check_results)
        passed_checks = sum(1 for c in check_results if c.status == QualityStatus.PASS)
        failed_checks = sum(1 for c in check_results if c.status == QualityStatus.FAIL)
        warning_checks = sum(1 for c in check_results if c.status == QualityStatus.WARNING)

        # Formula: passed_checks / total_checks * 100.0
        quality_score = (passed_checks / total_checks * 100.0) if total_checks > 0 else 100.0

        # Overall Status
        if failed_checks > 0:
            overall_status = QualityStatus.FAIL
        elif warning_checks > 0:
            overall_status = QualityStatus.WARNING
        else:
            overall_status = QualityStatus.PASS

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        run_result = QualityRunResult(
            run_id=run_id,
            dataset=dataset_name,
            contract_version=contract_version,
            pipeline=pipeline,
            overall_status=overall_status,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            warning_checks=warning_checks,
            quality_score=round(quality_score, 2),
            duration_ms=round(duration_ms, 2),
            freshness_status=freshness_status,
            freshness_delay_minutes=freshness_delay,
            last_record_timestamp=last_rec_ts,
            row_count=row_count,
            checks=check_results
        )

        # 9. Persist to PostgreSQL Result Store
        self.result_store.record_run(run_result)

        # 10. Update Prometheus Observability Metrics
        status_str = overall_status.value
        QUALITY_VALIDATION_TOTAL.labels(dataset=dataset_name, status=status_str).inc()
        if overall_status == QualityStatus.FAIL:
            QUALITY_VALIDATION_FAILURES_TOTAL.labels(dataset=dataset_name).inc()

        for c in check_results:
            exp_str = c.expectation_type
            QUALITY_CHECKS_TOTAL.labels(dataset=dataset_name, expectation_type=exp_str).inc()
            if not c.success:
                sev_str = c.severity.value
                QUALITY_CHECK_FAILURES_TOTAL.labels(
                    dataset=dataset_name,
                    expectation_type=exp_str,
                    severity=sev_str
                ).inc()

        QUALITY_VALIDATION_DURATION_SECONDS.labels(dataset=dataset_name).observe(duration_ms / 1000.0)

        if freshness_status in {FreshnessStatus.WARNING, FreshnessStatus.STALE}:
            FRESHNESS_VIOLATIONS_TOTAL.labels(dataset=dataset_name).inc()

        # 11. Automated Incident Creation for Quality Failures (Phase E)
        if create_incidents and failed_checks > 0:
            if self.incident_manager is None:
                try:
                    from dataguard.incidents.repository import IncidentRepository
                    from dataguard.incidents.manager import IncidentManager
                    repo = IncidentRepository(engine=self.result_store.engine)
                    self.incident_manager = IncidentManager(repository=repo, registry_service=self.registry)
                except Exception:
                    pass

            if self.incident_manager is not None:
                for c in check_results:
                    if not c.success or c.status == QualityStatus.FAIL:
                        try:
                            self.incident_manager.handle_check_failure(
                                check=c,
                                dataset=dataset_name,
                                pipeline=pipeline,
                                contract=active_contract
                            )
                        except Exception:
                            pass

        return run_result
