# FeatureHub + DataGuard Integrated Platform Walkthrough

This interactive guide demonstrates the unified FeatureHub + DataGuard data platform across both the Happy Path and the Failure Protection Paths.

---

## 1. Full End-to-End Success Path (CLI)

Run the full 11-stage pipeline for `customer_features`:

```bash
python scripts/run_integrated_pipeline.py --dataset customer_features --customer-id cust_000001
```

### Terminal Output
```text
================================================================================
FEATUREHUB + DATAGUARD INTEGRATED DATA PLATFORM
STAGE 3 — PHASE I: END-TO-END FLOW ORCHESTRATION
================================================================================
Target Dataset    : customer_features
Customer Entity   : cust_000001
Injected Anomaly  : None (Happy Path)
Allow Breaking    : False
--------------------------------------------------------------------------------
Computing offline feature datasets (Vectorized Engine)...
  [+] Vectorizing Customer Feature Group Aggregations...
  [+] Vectorizing Merchant Feature Group Aggregations...
Offline feature calculation finished successfully.

================================================================================
EXECUTION PIPELINE SUMMARY: [SUCCESS]
Run ID: run_e2e_a1b2c3d4 | Total Duration: 12450.80ms
================================================================================

| # | Pipeline Stage | Status | Duration | Stage Details |
|---|:---|:---:|---:|:---|
| 01 | DATA_SOURCE            | ✅ SUCCESS |    0.48ms | {'transactions_path': 'data/raw/transactions... |
| 02 | FEATURE_COMPUTATION    | ✅ SUCCESS |  580.12ms | {'rows_computed': 3672, 'feature_columns': ['... |
| 03 | CONTRACT_VALIDATION    | ✅ SUCCESS |   12.30ms | {'version': 'v1.0.0', 'owner': 'featurestore-... |
| 04 | SCHEMA_VALIDATION      | ✅ SUCCESS |    5.20ms | {'schema_changes_count': 0}                     |
| 05 | DATA_QUALITY           | ✅ SUCCESS | 4850.40ms | {'quality_score': 100.0, 'passed_checks': 15}   |
| 06 | OPENLINEAGE            | ✅ SUCCESS |    3.80ms | {'run_id': 'run_e2e_a1b2c3d4', 'event_type':... |
| 07 | AIRFLOW_ORCHESTRATION  | ✅ SUCCESS |    2.10ms | {'pipeline_id': 'integrated_feature_store_pi... |
| 08 | OFFLINE_STORE          | ✅ SUCCESS |   24.50ms | {'file_path': 'data/offline_store/customer_fe... |
| 09 | MATERIALIZATION        | ✅ SUCCESS | 6940.20ms | {'records_materialized': 3672}                  |
| 10 | REDIS_ONLINE_STORE     | ✅ SUCCESS |    0.85ms | {'entity_id': 'cust_000001', 'retrieved': True...|
| 11 | ML_PREDICTION          | ✅ SUCCESS |   30.85ms | {'prediction': 0, 'risk_score': 0.0375, ...}    |

--------------------------------------------------------------------------------

🎉 END-TO-END DATA PLATFORM FLOW COMPLETED SUCCESSFULLY!
  • Features Computed      : 3672 entities
  • Quality Score          : 100.0%
  • OpenLineage Run ID     : run_e2e_a1b2c3d4
  • Records in Redis Store : 3672

🤖 REAL-TIME ML INFERENCE FROM REDIS ONLINE STORE:
  • Customer ID            : cust_000001
  • Fraud Risk Score       : 0.0375
  • Prediction Decision    : 🛡️ LEGITIMATE
  • Model Version          : v1.0.0
  • Feature Timestamp      : 2026-10-04T10:00:00Z
  • Features Used          : 8 features
```

---

## 2. Breaking Schema Drift Protection Path

Simulate an accidental dropped column in the feature engineering code:

```bash
python scripts/run_integrated_pipeline.py --anomaly BREAKING_SCHEMA
```

### Terminal Output
```text
================================================================================
EXECUTION PIPELINE SUMMARY: [FAILED]
Run ID: run_e2e_5e65317d | Total Duration: 934.18ms
================================================================================

| # | Pipeline Stage | Status | Duration | Stage Details |
|---|:---|:---:|---:|:---|
| 01 | DATA_SOURCE            | ✅ SUCCESS |    0.52ms | {'transactions_path': 'data/raw/transactions... |
| 02 | FEATURE_COMPUTATION    | ✅ SUCCESS |  594.13ms | {'rows_computed': 3672, 'feature_columns': ['... |
| 03 | CONTRACT_VALIDATION    | ✅ SUCCESS |   13.57ms | {'version': 'v1.0.0', 'owner': 'featurestore-... |
| 04 | SCHEMA_VALIDATION      | ❌ FAILED  |    6.74ms | {'changes': ["column='cust_txn_count_24h', s... |
| 05 | DATA_QUALITY           | ⏭️ SKIPPED |    0.00ms | {'reason': 'Execution halted due to failure ... |
| 06 | OPENLINEAGE            | ⏭️ SKIPPED |    0.00ms | {'reason': 'Execution halted due to failure ... |
| 07 | AIRFLOW_ORCHESTRATION  | ⏭️ SKIPPED |    0.00ms | {'reason': 'Execution halted due to failure ... |
| 08 | OFFLINE_STORE          | ⏭️ SKIPPED |    0.00ms | {'reason': 'Execution halted due to failure ... |
| 09 | MATERIALIZATION        | ⏭️ SKIPPED |    0.00ms | {'reason': 'Execution halted due to failure ... |
| 10 | REDIS_ONLINE_STORE     | ⏭️ SKIPPED |    0.00ms | {'reason': 'Execution halted due to failure ... |
| 11 | ML_PREDICTION          | ⏭️ SKIPPED |    0.00ms | {'reason': 'Execution halted due to failure ... |

--------------------------------------------------------------------------------

🛑 PIPELINE EXECUTION HALTED (DATA INTEGRITY PROTECTION ACTIVATED)!
  • Failing Reason         : Breaking schema drift detected in computed features 'customer_features'.
  • OpenLineage Status     : FAILED RUN EVENT EMITTED

🚨 OPERATIONAL INCIDENT FILED IN POSTGRESQL:
  • Incident ID            : inc_b02f52f03afe
  • Assigned Owner         : featurestore-team
  • Severity Classification: CRITICAL
  • State                  : OPEN
  • Online Store Status    : PROTECTED (Corrupted features blocked from Redis)
```

---

## 3. Bad Data (Illegal Nulls / Out-of-Bounds Range) Protection Path

Simulate an ETL calculation failure producing NULL values in required attributes:

```bash
python scripts/run_integrated_pipeline.py --anomaly NULL_VIOLATION
```

### Result
- Great Expectations catches NULL in `customer_id` / non-nullable column.
- Pipeline status = `FAILED`.
- OpenLineage emits `FAIL` RunEvent.
- Operational incident filed with severity `HIGH` or `CRITICAL` assigned to `featurestore-team`.
- Materialization is skipped; Redis online store remains safe.

---

## 4. REST API End-to-End Execution

Trigger the integrated pipeline programmatically over HTTP:

```bash
curl -X POST http://localhost:8000/pipeline/integrated-run \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "customer_features",
    "target_customer_id": "cust_000001"
  }'
```

Query the latest recorded run:

```bash
curl http://localhost:8000/pipeline/integrated-run/latest
```
