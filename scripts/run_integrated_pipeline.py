#!/usr/bin/env python3
"""
FeatureHub + DataGuard Integrated End-to-End Pipeline CLI Runner.
Demonstrates genuine end-to-end data platform flow:
Data Source -> Feature Computation -> DataGuard Contract Validation ->
DataGuard Schema Validation -> Great Expectations -> OpenLineage ->
Airflow -> FeatureHub Offline Store -> Materialization -> Redis ->
FeatureHub API -> ML Prediction.

And the failure path:
Bad Data / Breaking Schema / Stale Features -> DataGuard -> FAILED ->
OpenLineage FAILED RUN + Operational Incident (owner + severity).
"""

import sys
import argparse
from pathlib import Path

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Reconfigure stdout/stderr for unicode emojis on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from featurehub.integration.service import FeatureHubDataGuardIntegrator
from featurehub.integration.models import StageStatus, IntegrationStage


def main():
    parser = argparse.ArgumentParser(description="FeatureHub + DataGuard End-to-End Platform Pipeline")
    parser.add_argument("--dataset", default="customer_features", help="Dataset name to process")
    parser.add_argument("--customer-id", default="cust_0001", help="Target customer entity ID for ML prediction")
    parser.add_argument("--anomaly", choices=["BREAKING_SCHEMA", "NULL_VIOLATION", "RANGE_VIOLATION", "STALE_FEATURES"], help="Inject failure anomaly")
    parser.add_argument("--allow-breaking", action="store_true", help="Allow breaking schema modifications")

    args = parser.parse_args()

    print("=" * 80)
    print("FEATUREHUB + DATAGUARD INTEGRATED DATA PLATFORM")
    print("STAGE 3 — PHASE I: END-TO-END FLOW ORCHESTRATION")
    print("=" * 80)
    print(f"Target Dataset    : {args.dataset}")
    print(f"Customer Entity   : {args.customer_id}")
    print(f"Injected Anomaly  : {args.anomaly or 'None (Happy Path)'}")
    print(f"Allow Breaking    : {args.allow_breaking}")
    print("-" * 80)

    integrator = FeatureHubDataGuardIntegrator()
    result = integrator.run_e2e_pipeline(
        dataset_name=args.dataset,
        target_customer_id=args.customer_id,
        inject_anomaly=args.anomaly,
        allow_breaking=args.allow_breaking
    )

    print("\n" + "=" * 80)
    print(f"EXECUTION PIPELINE SUMMARY: [{result.status.value}]")
    print(f"Run ID: {result.run_id} | Total Duration: {result.duration_ms:.2f}ms")
    print("=" * 80)

    print("\n| # | Pipeline Stage | Status | Duration | Stage Details |")
    print("|---|:---|:---:|---:|:---|")

    stage_icons = {
        StageStatus.SUCCESS: "✅ SUCCESS",
        StageStatus.FAILED: "❌ FAILED ",
        StageStatus.SKIPPED: "⏭️ SKIPPED"
    }

    for idx, s in enumerate(result.stages, 1):
        icon = stage_icons.get(s.status, s.status.value)
        details_str = str(s.details) if s.details else (s.error or "")
        if len(details_str) > 50:
            details_str = details_str[:47] + "..."
        print(f"| {idx:02d} | {s.stage.value:<22} | {icon} | {s.duration_ms:7.2f}ms | {details_str} |")

    print("\n" + "-" * 80)

    if result.status == StageStatus.SUCCESS:
        print("\n🎉 END-TO-END DATA PLATFORM FLOW COMPLETED SUCCESSFULLY!")
        print(f"  • Features Computed      : {result.features_computed_count} entities")
        print(f"  • Quality Score          : {result.quality_score:.1f}%")
        print(f"  • OpenLineage Run ID     : {result.openlineage_run_id}")
        print(f"  • Records in Redis Store : {result.records_materialized_count}")
        if result.ml_prediction:
            pred = result.ml_prediction
            print("\n🤖 REAL-TIME ML INFERENCE FROM REDIS ONLINE STORE:")
            print(f"  • Customer ID            : {args.customer_id}")
            print(f"  • Fraud Risk Score       : {pred.get('risk_score')}")
            print(f"  • Prediction Decision    : {'🚨 FRAUD ALERT' if pred.get('prediction') == 1 else '🛡️ LEGITIMATE'}")
            print(f"  • Model Version          : {pred.get('model_version')}")
            print(f"  • Feature Timestamp      : {pred.get('feature_timestamp')}")
            print(f"  • Features Used          : {len(pred.get('features_used', {}))} features")
        sys.exit(0)
    else:
        print("\n🛑 PIPELINE EXECUTION HALTED (DATA INTEGRITY PROTECTION ACTIVATED)!")
        print(f"  • Failing Reason         : {result.error_message}")
        print(f"  • OpenLineage Status     : FAILED RUN EVENT EMITTED")
        if result.incident_id:
            print("\n🚨 OPERATIONAL INCIDENT FILED IN POSTGRESQL:")
            print(f"  • Incident ID            : {result.incident_id}")
            print(f"  • Assigned Owner         : {result.incident_owner}")
            print(f"  • Severity Classification: {result.incident_severity}")
            print(f"  • State                  : OPEN")
        print("  • Online Store Status    : PROTECTED (Corrupted features blocked from Redis)")
        sys.exit(1)


if __name__ == "__main__":
    main()
