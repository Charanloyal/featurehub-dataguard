# DataGuard OpenLineage Demonstration & Verification Guide

**Stage**: STAGE 3 — PHASE F: OPENLINEAGE DATA LINEAGE  
**Script**: `scripts/lineage_demo.py` & `scripts/populate_lineage.py`  
**Database**: PostgreSQL 16 (`featurehub_dataguard_postgres`)  

---

## 1. Overview

The DataGuard OpenLineage demo verifies real pipeline event emission, dataset graph generation, column-level lineage tracking, multi-hop BFS graph traversal, and quality incident correlation against live PostgreSQL infrastructure.

To run the interactive demonstration:

```bash
python scripts/lineage_demo.py
```

To re-seed or simulate full pipeline execution:

```bash
python scripts/populate_lineage.py
```

---

## 2. Walkthrough of Verification Scenarios

### Scenario 1: Full End-to-End Dataset Lineage Graph

Validates complete graph connectivity across raw sources, transformation pipelines, feature stores, and caching layers:

- **Total Graph Nodes**: `26` (Datasets and Pipelines)
- **Total Dependency Edges**: `54`
- **Verified Directed Dependency Paths**:
  ```
  postgres.customers           ---(customer_quality_pipeline)---> customer_quality_pipeline
  customer_quality_pipeline    ---(customer_quality_pipeline)---> airflow.customers_clean
  postgres.transactions       ---(transaction_quality_pipeline)---> transaction_quality_pipeline
  transaction_quality_pipeline ---(transaction_quality_pipeline)---> airflow.transactions_clean
  airflow.transactions_clean   ---(feature_compute)-------------> customer_features
  airflow.customers_clean      ---(feature_compute)-------------> customer_features
  customer_features            ---(feature_materialization)-----> redis.online_features
  ```

---

### Scenario 2: Upstream Traversal (Root Cause Tracing)

When an analyst or on-call engineer investigates an issue in `customer_features`, DataGuard traverses upstream directed edges using BFS:

- **Target Dataset**: `customer_features`
- **Discovered Upstream Ancestors**:
  - `airflow.customers_clean`
  - `airflow.transactions_clean`
  - `postgres.customers`
  - `postgres.transactions`
- **Contributing Pipelines**:
  - `customer_quality_pipeline`
  - `transaction_quality_pipeline`
  - `feature_compute`

---

### Scenario 3: Downstream Traversal (Impact & Blast Radius)

Before altering or migrating a raw table (`postgres.transactions`), DataGuard computes all downstream dependents:

- **Source Dataset**: `postgres.transactions`
- **Dependent Downstream Assets**:
  - `airflow.transactions_clean`
  - `customer_features` (FeatureHub Offline Store)
  - `transaction_features`
  - `redis.online_features` (FeatureHub Online Store)
- **Consuming Pipelines**:
  - `transaction_quality_pipeline`
  - `feature_compute`
  - `feature_materialization`

---

### Scenario 4: Column-Level Lineage & Transformations

Validates that column transformations are tracked with explicit formulas rather than blind pass-throughs:

- **Target Dataset**: `transaction_features`

1. **`customer_id`**:
   - Source: `transactions_clean.customer_id`
   - Transformation: `GROUP BY customer_id`
   - Pipeline: `feature_compute`
2. **`total_amount_24h`**:
   - Source: `transactions_clean.amount`
   - Transformation: `SUM(amount) over trailing 24h window`
   - Pipeline: `feature_compute`
3. **`last_transaction_time`**:
   - Source: `transactions_clean.timestamp`
   - Transformation: `MAX(timestamp) over trailing window`
   - Pipeline: `feature_compute`

- **Target Dataset**: `customer_features`
1. **`cust_txn_amount_sum_30d`**:
   - Source: `transactions_clean.amount`
   - Transformation: `SUM(amount) over trailing 30d window`
2. **`cust_failed_txns_30d`**:
   - Source: `transactions_clean.status`
   - Transformation: `SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) over trailing 30d window`

---

### Scenario 5: Incident & Failed Pipeline Lineage Correlation

Simulates a real pipeline failure, records a quality check failure, creates an incident, and correlates it with upstream data lineage:

1. **Pipeline Execution**: `reconciliation_pipeline` runs and terminates with status `FAIL` due to debit/credit variance.
2. **Quality Validation**: Registers failure for check `ledger_balance_reconciliation` on dataset `transactions`.
3. **Incident Creation**: Creates persistent incident `inc_5adf13dcff18` with severity `MEDIUM` and references `run_id: run_fail_737362e67965`.
4. **Lineage Correlation**:
   - Querying `GET /incidents/{incident_id}/lineage` immediately returns:
     - The exact failed pipeline name (`reconciliation_pipeline`).
     - The exact failed run identifier (`run_fail_737362e67965`).
     - The upstream inputs (`transactions_clean`, `postgres.accounts`) to triage the failure.
