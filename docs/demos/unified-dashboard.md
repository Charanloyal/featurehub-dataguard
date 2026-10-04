# Unified Data Platform Dashboard — Recruiter Demo Runbook

This guide provides an interactive, step-by-step runbook for demonstrating the unified **FeatureHub + DataGuard** data platform in **60 seconds or in depth**.

---

## 1. Quick Start / Launching the Dashboard

```bash
# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Verify infrastructure services are active
docker compose ps

# 3. Launch Unified Dashboard
streamlit run apps/unified-dashboard/app.py --server.port 8505
```

Navigate to: `http://localhost:8505`

---

## 2. 60-Second Recruiter Tour

### Minute 0:00 – Landing Page (Platform Overview)
1. **Notice the Hero Header**: "FEATUREHUB + DATAGUARD: Reliable Data Infrastructure for Production Machine Learning".
2. **Observe Real Live Metrics**:
   - **122+ Production Features** across **6 Feature Groups**
   - **27 Data Contracts** across **30 Version Baselines**
   - **274 Great Expectations Runs** with **96.1% Pass Rate**
   - **Sub-1.0ms Redis Serving SLA**
3. **Inspect the Architecture Flow**:
   - Trace data moving through: Data Sources $\to$ Airflow $\to$ DataGuard $\to$ Feature Compute $\to$ FeatureHub (Offline/Redis) $\to$ ML Inference.
4. **Platform Health Widget**:
   - Confirm all 6 subsystems (PostgreSQL 16, Redis 7.2, Airflow 2.9, FeatureHub API, DataGuard API, Prometheus) report `HEALTHY` status with measured socket response times.

---

## 3. Deep-Dive Subsystem Walkthroughs

### Subsystem 1: Pipeline Operations (Page 2)
- **What to show**: Complete execution ledger of Airflow pipeline runs.
- **Action**: Select `customer_features_pipeline`.
- **Key Observation**: Point out the 6-stage execution graph (`Contract` $\to$ `Schema` $\to$ `Quality` $\to$ `Compute` $\to$ `Lineage` $\to$ `Materialization`). Point out how failing stages are highlighted in red while downstream stages are cleanly skipped.

### Subsystem 2: FeatureHub & Online Store (Pages 3 & 4)
- **What to show**: Dynamic feature catalog with 122+ features (windowed customer transaction velocity, merchant risk metrics, etc.).
- **Action**: Go to "Redis Online Store Monitor" and click **🚀 Run Live Latency Test**.
- **Key Observation**: The test performs 10 live Redis lookups and displays `0.98 ms` P50 latency. Point out that historical benchmarks are explicitly labeled as `<span class='benchmark-badge'>BENCHMARK RESULT</span>`.

### Subsystem 3: Point-in-Time Join Demo (Page 5)
- **What to show**: Real-time prevention of target leakage during training dataset construction.
- **Action**: Click **🚀 Evaluate Point-in-Time Join vs Naive Join**.
- **Key Observation**:
  - Event: `12:00:00 UTC`
  - Valid PIT Feature: `11:55:00 UTC` (12 txns) $\to$ `VALID`
  - Naive Future Feature: `12:30:00 UTC` (45 txns) $\to$ `REJECTED (LEAKAGE PREVENTED)`

### Subsystem 4: Real-Time ML Inference (Page 6)
- **What to show**: Live fraud risk scoring using Redis online features.
- **Action**: Enter a transaction amount (e.g. `$285.50`) and click **⚡ Score Transaction with ML Model**.
- **Key Observation**: Real-time inference score (e.g. `0.0428 LEGITIMATE`) returned in `< 10ms`. Point out the feature attribution table showing which features were pulled from Redis versus request-time inputs.

### Subsystem 5: Schema Diff & PR Gate (Page 8)
- **What to show**: Automated Pull Request compatibility analysis.
- **Action**: Toggle between "Scenario 1: SAFE" and "Scenario 2: BREAKING".
- **Key Observation**: Notice the dynamic decision banner:
  - Scenario 1 shows: `✅ COMPATIBLE — SAFE TO MERGE & MATERIALIZE`
  - Scenario 2 shows: `❌ MERGE BLOCKED — BREAKING CHANGES DETECTED`

### Subsystem 6: OpenLineage & Column Lineage (Page 10)
- **What to show**: End-to-end data provenance tracking.
- **Action**: Select `customer_features` and inspect column lineage for `customer_id`.
- **Key Observation**: Displays 9 upstream sources, 2 downstream sinks (`redis.online_features`), and exact mathematical transformation logic (`GROUP BY customer_id entity key`).

### Subsystem 7: Incident Management & Remediation (Page 11)
- **What to show**: Operational incident response.
- **Action**: Select an open incident and click **🟡 Acknowledge Incident** or **🟢 Resolve Incident**.
- **Key Observation**: Real-time state transition executed in PostgreSQL with updated audit trail.

---

## 4. The 6 Demo Scenarios (Demo Center — Page 15)

In **12. Demo Center**, click any of the 6 one-click demonstration scenarios:
1. **DEMO 1: Healthy Feature Pipeline**: Full 11-stage run (3,672 rows materialized in Redis, live ML score generated).
2. **DEMO 2: Breaking Schema Drift**: Injected column drop triggers DataGuard circuit breaker in `< 1.0s`, emits OpenLineage `FAIL` event, and files a `CRITICAL` incident. Redis is protected.
3. **DEMO 3: Bad Data (Null Violation)**: 5% null values trigger Great Expectations failure; pipeline halts before Redis write.
4. **DEMO 4: Stale Features (SLA Breach)**: 48h timestamp lag violates 60-minute freshness SLA; ingestion blocked.
5. **DEMO 5: Incident Investigation & Resolution**: Transitions incident to `ACKNOWLEDGED` and `RESOLVED` in PostgreSQL.
6. **DEMO 6: Point-in-Time Leakage Prevention**: Evaluates backward asof join to exclude future feature updates.
