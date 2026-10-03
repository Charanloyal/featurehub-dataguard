"""
DataGuard OpenLineage Pipeline Seeder.
Executes realistic platform pipelines, emitting OpenLineage RunEvents to PostgreSQL.
Generates dataset lineage, column-level lineage, historical runs, and a deterministic failure scenario.
"""

import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataguard.lineage.collector import LineageCollector
from dataguard.lineage.column_lineage import PROJECT_COLUMN_MAPPINGS
from dataguard.lineage.repository import LineageRepository
from dataguard.incidents.manager import IncidentManager
from dataguard.incidents.repository import IncidentRepository
from dataguard.incidents.models import IncidentSeverity
from dataguard.quality.models import QualityCheckResult, QualityStatus


def populate_lineage_graph():
    print("=" * 70)
    print("  POPULATING DATAGUARD OPENLINEAGE GRAPH (PostgreSQL 16)")
    print("=" * 70)

    repo = LineageRepository()
    collector = LineageCollector(repository=repo)
    inc_repo = IncidentRepository()
    inc_mgr = IncidentManager(repository=inc_repo)

    # -------------------------------------------------------------
    # 1. Pipeline: customer_quality_pipeline (Postgres -> Clean)
    # -------------------------------------------------------------
    print("\n[+] Executing Pipeline: customer_quality_pipeline...")
    run_cust = collector.start_run(
        pipeline_id="customer_quality_pipeline",
        job_name="customer_quality_pipeline",
        inputs=["postgres.customers"],
        namespace="airflow"
    )
    print(f"    Started Run: {run_cust.run_id}")
    collector.complete_run(
        run_id=run_cust.run_id,
        pipeline_id="customer_quality_pipeline",
        job_name="customer_quality_pipeline",
        outputs=["customers_clean"],
        namespace="airflow"
    )
    print(f"    Completed Run: {run_cust.run_id} (postgres.customers -> customers_clean)")

    # -------------------------------------------------------------
    # 2. Pipeline: transaction_quality_pipeline (Postgres -> Clean)
    # -------------------------------------------------------------
    print("\n[+] Executing Pipeline: transaction_quality_pipeline...")
    run_txn = collector.start_run(
        pipeline_id="transaction_quality_pipeline",
        job_name="transaction_quality_pipeline",
        inputs=["postgres.transactions"],
        namespace="airflow"
    )
    print(f"    Started Run: {run_txn.run_id}")
    collector.complete_run(
        run_id=run_txn.run_id,
        pipeline_id="transaction_quality_pipeline",
        job_name="transaction_quality_pipeline",
        outputs=["transactions_clean"],
        namespace="airflow"
    )
    print(f"    Completed Run: {run_txn.run_id} (postgres.transactions -> transactions_clean)")

    # -------------------------------------------------------------
    # 3. Pipeline: feature_compute (Clean Datasets -> Feature Stores)
    # -------------------------------------------------------------
    print("\n[+] Executing Pipeline: feature_compute (FeatureHub Offline Features)...")
    run_feat = collector.start_run(
        pipeline_id="feature_compute",
        job_name="feature_compute",
        inputs=["transactions_clean", "customers_clean"],
        namespace="airflow"
    )
    print(f"    Started Run: {run_feat.run_id}")
    collector.complete_run(
        run_id=run_feat.run_id,
        pipeline_id="feature_compute",
        job_name="feature_compute",
        outputs=["customer_features", "transaction_features"],
        namespace="airflow"
    )
    print(f"    Completed Run: {run_feat.run_id} ([transactions_clean, customers_clean] -> [customer_features, transaction_features])")

    # -------------------------------------------------------------
    # 4. Pipeline: feature_materialization (FeatureHub -> Redis)
    # -------------------------------------------------------------
    print("\n[+] Executing Pipeline: feature_materialization (Redis Online Store)...")
    run_mat = collector.start_run(
        pipeline_id="feature_materialization",
        job_name="feature_materialization",
        inputs=["customer_features", "transaction_features"],
        namespace="airflow"
    )
    print(f"    Started Run: {run_mat.run_id}")
    collector.complete_run(
        run_id=run_mat.run_id,
        pipeline_id="feature_materialization",
        job_name="feature_materialization",
        outputs=["redis.online_features"],
        namespace="airflow"
    )
    print(f"    Completed Run: {run_mat.run_id} ([customer_features, transaction_features] -> redis.online_features)")

    # -------------------------------------------------------------
    # 5. Pipeline: order_quality_pipeline (Orders -> Clean -> Analytics)
    # -------------------------------------------------------------
    print("\n[+] Executing Pipeline: order_quality_pipeline...")
    run_ord = collector.start_run(
        pipeline_id="order_quality_pipeline",
        job_name="order_quality_pipeline",
        inputs=["postgres.orders"],
        namespace="airflow"
    )
    collector.complete_run(
        run_id=run_ord.run_id,
        pipeline_id="order_quality_pipeline",
        job_name="order_quality_pipeline",
        outputs=["orders_clean"],
        namespace="airflow"
    )
    print(f"    Completed Run: {run_ord.run_id} (postgres.orders -> orders_clean)")

    # -------------------------------------------------------------
    # 6. Pipeline: reconciliation_pipeline (DETERMINISTIC FAILURE SCENARIO)
    # -------------------------------------------------------------
    print("\n[+] Executing Pipeline: reconciliation_pipeline (DETERMINISTIC FAILURE SCENARIO)...")
    failed_run_id = f"run_fail_{uuid.uuid4().hex[:12]}"
    run_rec = collector.start_run(
        pipeline_id="reconciliation_pipeline",
        job_name="reconciliation_pipeline",
        inputs=["transactions_clean", "postgres.accounts"],
        namespace="airflow",
        run_id=failed_run_id
    )
    err_msg = "Ledger reconciliation divergence: settlement credits do not match debit batch sum."
    collector.fail_run(
        run_id=failed_run_id,
        pipeline_id="reconciliation_pipeline",
        job_name="reconciliation_pipeline",
        error_message=err_msg,
        namespace="airflow"
    )
    print(f"    Failed Run: {failed_run_id} marked FAIL with error message.")

    # Create associated DataGuard quality failure and incident referencing run_id
    mock_fail_check = QualityCheckResult(
        run_id=failed_run_id,
        dataset="transactions",
        check_name="ledger_balance_reconciliation",
        column="amount",
        expectation_type="expect_column_pair_values_to_be_equal",
        status=QualityStatus.FAIL,
        severity=IncidentSeverity.CRITICAL,
        observed_value="Discrepancy: $4,250.00 debit variance",
        expected_value="Variance == $0.00",
        success=False,
        pipeline="reconciliation_pipeline"
    )
    created_inc = inc_mgr.handle_check_failure(
        check=mock_fail_check,
        dataset="transactions",
        pipeline="reconciliation_pipeline",
        actor="reconciliation_automation"
    )
    if created_inc:
        print(f"    [INCIDENT LINKED] Incident ID: {created_inc.incident_id}")
        print(f"                      Severity   : {created_inc.severity.value}")
        print(f"                      Referenced Run: {created_inc.run_id}")
        print(f"                      Pipeline   : {created_inc.pipeline}")

    # -------------------------------------------------------------
    # Lineage Statistics Summary
    # -------------------------------------------------------------
    counts = repo.get_counts()
    print("\n" + "=" * 70)
    print("  LINEAGE POPULATION SUMMARY")
    print("=" * 70)
    print(f"  Total Unique Datasets Tracked : {counts['datasets']}")
    print(f"  Total Pipelines / Jobs Tracked : {counts['jobs']}")
    print(f"  Total Pipeline Runs Tracked    : {counts['runs']}")
    print(f"  Total Lineage Dependency Edges : {counts['edges']}")
    print(f"  Total Column Lineage Mappings  : {counts['column_mappings']}")
    print("=" * 70)


if __name__ == "__main__":
    populate_lineage_graph()
