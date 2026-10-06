# Recruiter & Technical Evaluator Demo Walkthrough
**Platform:** FeatureHub + DataGuard Integrated Data Platform  
**Target Duration:** 3–5 Minutes  
**Objective:** Rapidly demonstrate production data engineering, ML feature serving, pre-materialization contract gating, and operational incident response.

---

## Demo Script & Screen Recording Sequence

### 0:00 — Platform Overview
- **What to click:** Open Unified Dashboard landing page (`1. Platform Overview`).
- **What to show:**
  - Hero header: `⚡🛡️ FEATUREHUB + DATAGUARD — Reliable Data Infrastructure for Production Machine Learning`.
  - Core platform scale KPIs: **122 production features**, **27 data contracts**, **26 pipelines**, and **96.1% quality pass rate**.
  - Platform Architecture Topology:
    `Data Sources → Airflow → DataGuard Core → Feature Computation → Dual Store (Lake + Redis) → Real-Time ML Inference`.
- **Technical point:** Solves the core challenge of production ML systems: preventing garbage data, schema breakage, and train/serve skew from corrupting real-time models.

---

### 0:30 — FeatureHub Registry
- **What to click:** Navigate to `3. FeatureHub` → `Feature Registry Catalog`.
- **What to show:**
  - Feature catalog table containing 122 registered features across 6 business domains (`customer`, `merchant`, `account`, `transaction_window`, `velocity_risk`, `temporal_behavioral`).
  - Filter by `customer_velocity` or search for `cust_txn_count_1h`.
  - Feature metadata: Data type (`INT64`), freshness SLA (`15 mins`), source table (`transactions`), and owner team.
- **Technical point:** Declarative, centralized feature definitions ensure single source of truth across offline training and online serving pipelines.

---

### 1:00 — Point-in-Time (PIT) Correctness
- **What to click:** Switch to `Point-in-Time Demo` tab (under `3. FeatureHub`).
- **What to show:**
  - Observation events table paired with feature change timestamps.
  - Interactive observation slider showing backward-looking ASOF join window ($t_{feature} \le t_{event}$).
  - Verification banner showing **0.0% Temporal Data Leakage**.
- **Technical point:** Eliminates target leakage in training datasets by strictly prohibiting future feature values from joining to historical observation events.

---

### 1:30 — Real-Time ML Prediction
- **What to click:** Navigate to `9. ML Prediction` (or use Public API Gateway `POST /predict`).
- **What to show:**
  - Select customer `cust_000001`, transaction amount `$25.50` → Click **Run Real-Time ML Inference**.
  - Immediate response: **LEGITIMATE (Risk Score: 0.04)** in `< 89 ms` end-to-end HTTP response.
  - Feature vector attribution showing real Redis features (`burst_txn_count_10min = 0`, `cust_failed_txn_count_24h = 0`).
  - Now change transaction amount to `$2,850.00` → Classification dynamically switches to **FRAUD_ALERT (Risk Score: 0.84)**.
- **Technical point:** Sub-2ms Redis key lookups combined with Scikit-Learn inference provide real-time fraud scoring with verified zero-skew feature retrieval.

---

### 2:00 — DataGuard Schema Diff
- **What to click:** Navigate to `6. Schema & Contracts` → `Schema Diff & Compatibility Engine`.
- **What to show:**
  - Select baseline contract `customers v1.0.0` and introduce an incompatible column type change (`integer` $\to$ `string`) or remove an existing field.
  - Click **Compare Schemas**.
  - Immediate classification banner: **BREAKING** with Recommendation: **BLOCK MERGE**.
- **Technical point:** Automated backward-compatibility evaluation prevents breaking upstream schema migrations from silently crashing downstream feature transformation jobs.

---

### 2:30 — Data Quality Failure
- **What to click:** Navigate to `5. Data Quality` (Great Expectations test reports).
- **What to show:**
  - Great Expectations test suite execution over 100,000 synthetic financial rows.
  - Show simulated quality anomaly: NULL rate violation or out-of-bounds amount spike (`amount > 50,000` exceeding expectation).
  - Validation failure banner: `Suite failed: 2 expectations breached`.
- **Technical point:** Declarative data testing verifies business invariants before data is materialized into ML offline or online storage.

---

### 3:00 — Incident Management
- **What to click:** Navigate to `8. Incident Management`.
- **What to show:**
  - Operational incident table in PostgreSQL.
  - Inspect incident `INC-2026-002` (Severity: `HIGH`, Status: `OPEN`, Owner: `Data Engineering`).
  - Automated root cause attribution identifying the exact breaching batch and failed expectation.
- **Technical point:** Closes the operational loop by converting data quality check failures into structured, prioritized engineering incidents with clear team ownership.

---

### 3:30 — OpenLineage Provenance
- **What to click:** Navigate to `7. Lineage`.
- **What to show:**
  - End-to-end dataset lineage DAG for `customer_features`.
  - Visual traversal: `PostgreSQL Raw Tables → Airflow Ingestion → Great Expectations Gate → Feature Views`.
  - Column-level lineage tracing the upstream origins of derived features like `cust_avg_txn_amount_30d`.
- **Technical point:** Standard OpenLineage event emission enables instant blast-radius analysis when an upstream data source experiences an anomaly.

---

### 4:00 — CI/CD Pre-Merge Gate
- **What to click:** Navigate to `6. Schema & Contracts` → `GitHub CI/CD Gating Simulator` (Page 12).
- **What to show:**
  - Simulated GitHub Actions Pull Request run.
  - Evaluation stages: Contract Validation $\to$ Schema Diff Engine $\to$ Data Quality Regression.
  - Breaking pull request result: **BLOCKED (Exit Code 1)** with detailed failure diagnostics.
- **Technical point:** Enforces "shift-left" data governance: 100% of tested breaking schema changes are caught and rejected in GitHub CI before merging to main.

---

### 4:30 — Recovery & Deterministic Reset
- **What to click:** Click **Acknowledge** and **Resolve** on incident `INC-2026-002`.
- **What to show:**
  - Incident status transitions to `RESOLVED` with resolution timestamp.
  - Highlight [`scripts/reset_demo.py`](..\../scripts/reset_demo.py):
    ```bash
    python scripts/reset_demo.py
    ```
  - Demonstrates that the public demo is completely deterministic and recoverable to baseline in seconds.
- **Technical point:** Resilient operational self-healing ensures high platform uptime and repeatable test evaluation.

---

### 5:00 — Final Benchmarks & Architecture Recap
- **What to click:** Navigate to `13. Benchmarks`.
- **What to show:**
  - Verified local benchmark cards: **Redis Online P99 = 1.62 ms**, **ML Inference P99 = 6.62 ms**, **Circuit Breaker Abort = 911 ms**.
  - Explicit distinction banner separating reproducible local hardware benchmarks from live interactive HTTP request latency.
  - Click **Run Live Latency Test** to show current live HTTP round-trip latency.
- **Technical point:** Highlights engineering transparency—local benchmark latencies are never misrepresented as public-cloud production numbers.
