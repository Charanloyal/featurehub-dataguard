"""
DataGuard Incident Lifecycle CLI Demo (Phase E).
Demonstrates end-to-end incident management from data quality failures across 5 production scenarios:
1. Null-value failure (HIGH)
2. Duplicate primary key corruption (CRITICAL)
3. Invalid enum value (MEDIUM)
4. Referential integrity failure (CRITICAL)
5. Stale dataset SLA breach (CRITICAL)
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dataguard.contracts.registry import ContractRegistryService
from dataguard.quality.runner import DataQualityRunner
from dataguard.quality.datasets import DatasetCatalog
from dataguard.incidents.manager import IncidentManager
from dataguard.incidents.repository import IncidentRepository
from dataguard.quality.referential import ReferentialIntegrityValidator


def run_scenario(name: str, dataset_name: str, df, runner: DataQualityRunner, mgr: IncidentManager, actor: str = "oncall_engineer"):
    print(f"\n================================================================================")
    print(f"RUNNING SCENARIO: {name}")
    print(f"Dataset: {dataset_name} | Rows: {len(df)}")
    print(f"================================================================================")

    # 1. Run Data Quality Validation
    print("1. Running Great Expectations quality validation suite...")
    res = runner.run_validation(dataset_name, df=df, validate_referential=False, create_incidents=False)
    print(f"   Validation Status: {res.overall_status.value} (Quality Score: {res.quality_score}%, Failed: {res.failed_checks})")

    # 2. Extract failing check
    failing_checks = [c for c in res.checks if not c.success]
    if not failing_checks:
        print("   [!] No failing checks detected in this scenario.")
        return

    failed_check = failing_checks[0]
    print(f"2. Detected Quality Failure:")
    print(f"   Check Name       : {failed_check.check_name}")
    print(f"   Expectation Type : {failed_check.expectation_type}")
    print(f"   Target Column    : {failed_check.column}")
    print(f"   Observed Value   : {failed_check.observed_value}")
    print(f"   Expected Value   : {failed_check.expected_value}")

    # 3. Create Incident
    print("3. Generating incident via IncidentManager...")
    inc = mgr.handle_check_failure(
        check=failed_check,
        dataset=dataset_name,
        pipeline="incident_demo_pipeline",
        actor="automated_quality_runner"
    )

    print(f"   [CREATED] Incident ID: {inc.incident_id}")
    print(f"   Severity             : {inc.severity.value}")
    print(f"   Assigned Owner       : {inc.owner}")
    print(f"   Initial Status       : {inc.status.value}")
    print(f"   Failure Signature    : {inc.failure_signature}")

    # 4. Acknowledge Incident
    print(f"4. Acknowledging incident as '{actor}'...")
    acked = mgr.acknowledge_incident(inc.incident_id, actor=actor, notes="Triage initiated by on-call engineer.")
    print(f"   [ACKNOWLEDGED] Status: {acked.status.value} at {acked.acknowledged_at}")

    # 5. Resolve Incident
    print(f"5. Resolving incident as '{actor}'...")
    resolved = mgr.resolve_incident(inc.incident_id, actor=actor, notes="Root cause remediated; data reprocessed.")
    print(f"   [RESOLVED] Status    : {resolved.status.value} at {resolved.resolved_at}")

    # 6. Audit Trail History
    events = mgr.get_events(inc.incident_id)
    print(f"6. Incident Event Audit Trail ({len(events)} events):")
    for ev in events:
        old_st = ev.old_status.value if ev.old_status else "None"
        print(f"   - [{ev.timestamp}] {ev.event_type.value}: {old_st} -> {ev.new_status.value} (Actor: {ev.actor}) - {ev.notes}")


def run_referential_scenario(runner: DataQualityRunner, mgr: IncidentManager, actor: str = "oncall_engineer"):
    print(f"\n================================================================================")
    print(f"RUNNING SCENARIO 4: Referential Integrity Failure (Foreign Key Broken)")
    print(f"================================================================================")

    df_ord, df_cust = DatasetCatalog.bad_orders_missing_customer()
    ref_check = ReferentialIntegrityValidator.validate_referential_integrity(
        run_id="demo_fk",
        child_dataset="orders",
        child_df=df_ord,
        parent_dataset="customers",
        parent_df=df_cust,
        child_fk_col="customer_id",
        parent_pk_col="customer_id",
        pipeline="incident_demo_pipeline"
    )

    print(f"1. Referential check result: Success={ref_check.success}, Status={ref_check.status.value}")
    print(f"   Observed: {ref_check.observed_value}")
    print(f"   Expected: {ref_check.expected_value}")

    inc = mgr.handle_check_failure(
        check=ref_check,
        dataset="orders",
        pipeline="incident_demo_pipeline",
        actor="automated_quality_runner"
    )

    print(f"2. [CREATED] Incident ID: {inc.incident_id}")
    print(f"   Severity             : {inc.severity.value}")
    print(f"   Assigned Owner       : {inc.owner}")
    print(f"   Status               : {inc.status.value}")

    acked = mgr.acknowledge_incident(inc.incident_id, actor=actor, notes="Notified merchant ops regarding missing customer ID.")
    resolved = mgr.resolve_incident(inc.incident_id, actor=actor, notes="Backfilled missing customer records.")

    events = mgr.get_events(inc.incident_id)
    print(f"3. Audit Trail ({len(events)} events):")
    for ev in events:
        old_st = ev.old_status.value if ev.old_status else "None"
        print(f"   - [{ev.timestamp}] {ev.event_type.value}: {old_st} -> {ev.new_status.value} (Actor: {ev.actor}) - {ev.notes}")


def main():
    print("================================================================================")
    print("           DATAGUARD INCIDENT MANAGEMENT CLI DEMO (PHASE E)")
    print("================================================================================")

    registry = ContractRegistryService()
    repo = IncidentRepository()
    mgr = IncidentManager(repository=repo, registry_service=registry)
    runner = DataQualityRunner(registry_service=registry, incident_manager=mgr)

    # Scenario 1: Null-value failure
    df_nulls = DatasetCatalog.bad_orders_nulls()
    run_scenario("Scenario 1: Null-Value Invariant Failure", "orders", df_nulls, runner, mgr)

    # Scenario 2: Duplicate primary key
    df_dups = DatasetCatalog.bad_orders_duplicates()
    run_scenario("Scenario 2: Duplicate Primary Key Corruption", "orders", df_dups, runner, mgr)

    # Scenario 3: Invalid enum value
    df_enum = DatasetCatalog.bad_payments_invalid_status()
    run_scenario("Scenario 3: Disallowed Enum Accepted-Value Failure", "payments", df_enum, runner, mgr)

    # Scenario 4: Referential integrity failure
    run_referential_scenario(runner, mgr)

    # Scenario 5: Stale dataset
    df_stale = DatasetCatalog.stale_dataset("orders", hours_old=48)
    run_scenario("Scenario 5: Stale Dataset SLA Violation", "orders", df_stale, runner, mgr)

    # Platform Summary
    print(f"\n================================================================================")
    print("DATAGUARD INCIDENT SUMMARY & METRICS")
    print(f"================================================================================")
    summary = mgr.get_summary()
    print(f"Total Incidents Tracked   : {summary.total_incidents}")
    print(f"Open Incidents            : {summary.open_incidents}")
    print(f"Acknowledged Incidents    : {summary.acknowledged_incidents}")
    print(f"Resolved Incidents        : {summary.resolved_incidents}")
    print(f"Critical Severities       : {summary.critical_incidents}")
    print(f"High Severities           : {summary.high_incidents}")
    print(f"Medium Severities         : {summary.medium_incidents}")
    print(f"Low Severities            : {summary.low_incidents}")
    print(f"MTTA (Mean Time to Ack)   : {summary.mtta_seconds}s" if summary.mtta_seconds is not None else "MTTA: N/A")
    print(f"MTTR (Mean Time to Resolve): {summary.mttr_seconds}s" if summary.mttr_seconds is not None else "MTTR: N/A")
    print("================================================================================")
    print("Demo completed successfully!")


if __name__ == "__main__":
    main()
