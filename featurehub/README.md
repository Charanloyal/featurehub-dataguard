# FeatureHub – Real-Time Feature Store Platform

FeatureHub is an enterprise-grade real-time feature store that manages feature definitions, point-in-time (PIT) correct training dataset generation, offline Parquet storage, Redis online materialization, and real-time ML inference.

---

## Key Capabilities

- **120+ Real Features**: Windowed statistics across 6 financial feature groups (customer velocity, merchant risk, geo-distance, behavioral flags, etc.).
- **Point-in-Time (PIT) Joins**: Guaranteed zero data leakage during historical training dataset generation.
- **Sub-Millisecond Redis Materialization**: Offline-to-online sync engine providing `< 1ms` point-lookups for live inference.
- **Integrated DataGuard Circuit Breaker**: Pre-materialization validation enforcing data contracts, backward-compatible schema drift detection, and Great Expectations suites.

---

## Integrated Platform Flow (FeatureHub + DataGuard)

When executing an integrated feature pipeline, FeatureHub delegates data validation directly to DataGuard before committing any features to storage:

```
Data Source
    ↓
Feature Computation
    ↓
DataGuard Contract Validation
    ↓
DataGuard Schema Validation
    ↓
Great Expectations Quality Suite
    ↓
OpenLineage Provenance Emission
    ↓
Airflow Orchestration Heartbeat
    ↓
FeatureHub Offline Store (Parquet)
    ↓
Materialization Engine
    ↓
Redis Online Store
    ↓
FeatureHub REST API (/features/get)
    ↓
Live ML Fraud Predictor
```

### Circuit Breaker on Failure
If corrupted data, breaking schema modifications, or stale features are detected:
1. DataGuard aborts the pipeline immediately (< 1.05s).
2. An OpenLineage `FAIL` RunEvent is emitted.
3. An operational incident is logged in PostgreSQL with severity (`CRITICAL`, `HIGH`, `MEDIUM`) and routed to the contract owner.
4. Downstream materialization to Redis is completely skipped, protecting the ML model from bad feature vectors.

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check for FeatureHub API |
| `POST` | `/features/get` | Retrieve online feature vector for an entity |
| `POST` | `/predict` | Real-time fraud prediction using online features |
| `POST` | `/pipeline/integrated-run` | Trigger integrated FeatureHub + DataGuard end-to-end pipeline |
| `GET` | `/pipeline/integrated-run/latest` | Retrieve diagnostics of latest integrated pipeline execution |

---

## CLI Execution

```bash
# Run successful integrated pipeline
python scripts/run_integrated_pipeline.py --dataset customer_features

# Simulate breaking schema failure
python scripts/run_integrated_pipeline.py --dataset customer_features --anomaly BREAKING_SCHEMA

# Simulate null violation failure
python scripts/run_integrated_pipeline.py --dataset customer_features --anomaly NULL_VIOLATION
```
