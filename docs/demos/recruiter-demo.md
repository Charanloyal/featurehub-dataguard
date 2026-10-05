# Recruiter & Technical Evaluator Demo Walkthrough
**Platform:** FeatureHub + DataGuard Integrated Data Platform  
**Target Duration:** 3–5 Minutes  
**Objective:** Rapidly demonstrate production data engineering, ML feature serving, pre-materialization contract gating, and operational incident response.

---

## Demo Script & Screen Recording Sequence

### STEP 1: Platform Overview & Architecture (0:00 – 0:30)
- **Action:** Open Unified Dashboard landing page (`1. Platform Overview`).
- **Talking Points:**
  - *"Welcome to FeatureHub + DataGuard, an end-to-end enterprise data platform bridging feature stores with active data quality gating."*
  - Point to the top KPIs: **122 production features**, **27 data contracts**, **26 pipelines**, and **96.1% quality pass rate**.
  - Show the **Platform Architecture Topology**:
    `Data Sources → Airflow → DataGuard Core → Feature Computation → Dual Store (Lake + Redis) → Real-Time ML Inference`.

---

### STEP 2: FeatureHub Catalog & 122 Real Features (0:30 – 1:00)
- **Action:** Navigate to `3. FeatureHub` → `Feature Registry Catalog`.
- **Talking Points:**
  - *"Here we have 122 real feature definitions organized across 6 business domains: Customer, Merchant, Transaction, Account, Device, and Risk."*
  - Filter by `Customer Features` or search for `cust_avg_txn_amount_30d`.
  - Highlight the schema, transformation logic, and SLA guarantees registered in code and PostgreSQL.

---

### STEP 3: Point-in-Time (PIT) Correctness (1:00 – 1:30)
- **Action:** Switch to `Point-in-Time Demo` tab.
- **Talking Points:**
  - *"In production ML, data leakage during training set creation destroys model generalization."*
  - Select observation events and show the ASOF join window.
  - Show how features are computed strictly as-of observation timestamp $T_{obs}$ with **0% temporal data leakage**, preventing future data contamination.

---

### STEP 4: Real-Time ML Prediction & Low-Latency Serving (1:30 – 2:00)
- **Action:** Navigate to `9. ML Prediction` (or use Public API `POST /predict`).
- **Talking Points:**
  - *"For real-time fraud scoring, we query the Redis online store and feed the feature vector to a Scikit-Learn fraud classifier."*
  - Select entity `cust_000001` with amount `$25.50` → Click **Run Inference**.
  - Result: **LEGITIMATE (Risk Score: 0.02)**.
  - Now change amount to `$2,500.00` and burst count → Result: **FRAUD_ALERT (Risk Score: 0.84)**.
  - Highlight local benchmark Redis p99 = **1.62 ms** (measured in dedicated benchmark test harness).

---

### STEP 5: DataGuard Contracts & Pre-Materialization Gating (2:00 – 2:30)
- **Action:** Navigate to `4. DataGuard` → `Data Contracts`.
- **Talking Points:**
  - *"DataGuard enforces schema contracts before data enters downstream ML feature pipelines."*
  - Show contract definitions with semantic column types, nullability constraints, and freshness SLAs.

---

### STEP 6: Schema Diff Engine & Breaking Change Detection (2:30 – 3:00)
- **Action:** Navigate to `6. Schema & Contracts` → `Schema Diff & Compatibility Engine`.
- **Talking Points:**
  - *"When an upstream team proposes modifying a dataset schema, DataGuard diffs the contracts."*
  - Select baseline `v1.0.0` and test an incompatible type change (`integer` → `string`) or deleted column.
  - Show immediate classification: **BREAKING** → Recommendation: **BLOCK MERGE**.

---

### STEP 7: GitHub CI/CD Quality Gating (3:00 – 3:30)
- **Action:** Switch to `GitHub CI/CD Gating Simulator`.
- **Talking Points:**
  - *"In our reproducible CI benchmark experiments, DataGuard blocked 100% of tested breaking changes before merge."*
  - Demonstrate a simulated Pull Request: breaking change triggers automated test failure and blocks merge with explicit violation details.

---

### STEP 8: End-to-End Lineage & Upstream/Downstream Provenance (3:30 – 4:00)
- **Action:** Navigate to `7. Lineage`.
- **Talking Points:**
  - *"DataGuard integrates OpenLineage run events across all 26 pipelines."*
  - Select dataset `customer_features`.
  - Walk through the visual DAG: `PostgreSQL Raw Sources → Airflow ETL → Quality Check → Feature Views`.
  - Column-level lineage traces the exact flow of every feature.

---

### STEP 9: Operational Incident Management & Root Cause (4:00 – 4:30)
- **Action:** Navigate to `8. Incident Management`.
- **Talking Points:**
  - *"When Great Expectations detects a data quality anomaly (e.g., null spike, range violation), a PostgreSQL incident is automatically opened."*
  - Inspect incident `INC-2026-002` (Severity: HIGH, Owner: Data Engineering).
  - Show automated root cause attribution and affected downstream features.

---

### STEP 10: Recovery & Deterministic Reset (4:30 – 5:00)
- **Action:** Show incident acknowledgment/resolution, then highlight `scripts/reset_demo.py`.
- **Talking Points:**
  - *"After incident triage, pipelines recover automatically."*
  - *"For reviewers, our public demo maintains deterministic state: `python scripts/reset_demo.py` restores the initial baseline at any time."*
  - Conclude: *"FeatureHub + DataGuard delivers verified, production-grade reliability for mission-critical ML systems."*
