# FeatureHub: Real-Time Feature Store Platform

**Primary Repository:** [Charanloyal/featurehub-dataguard](https://github.com/Charanloyal/featurehub-dataguard)

FeatureHub is an enterprise-grade real-time feature store that unifies offline historical training data with low-latency online serving, eliminating training-serving skew and preventing temporal target leakage.

---

## 1. Problem

Production machine learning teams face two major feature engineering bottlenecks:
1. **Training-Serving Skew:** Offline features computed with SQL/Pandas frequently differ from real-time features re-implemented in Java/Go for production serving, causing silent performance degradation.
2. **Temporal Target Leakage:** Naive historical feature joins pull data from the future relative to observation timestamps, artificially inflating cross-validation scores while failing in production.

FeatureHub solves this by providing a single declarative feature catalog, idempotent offline-to-online materialization, and strictly leak-free Point-in-Time (PIT) joining.

---

## 2. Architecture

```
                    ┌────────────────────────┐
                    │ Raw Transaction Events │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Feature Compute Engine │
                    │ (Rolling Time Windows) │
                    └───────────┬────────────┘
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
                 ▼                             ▼
      ┌─────────────────────┐       ┌─────────────────────┐
      │    Offline Store    │       │ Redis Online Store  │
      │ (Partitioned Lake)  │       │   (Port 6379 Key)   │
      └──────────┬──────────┘       └──────────┬──────────┘
                 │                             │
                 ▼                             ▼
      ┌─────────────────────┐       ┌─────────────────────┐
      │   PIT Join Engine   │       │ Real-Time Fast-API  │
      │  (Zero-Leakage ML)  │       │ (Sub-7ms Inference) │
      └─────────────────────┘       └─────────────────────┘
```

---

## 3. Features & Catalog Scale

- **122 Registered Features:** Spans 6 critical financial risk domains:
  - `customer_features` (velocity, transaction frequency, spend aggregation)
  - `merchant_features` (category risk scoring, volume history)
  - `account_features` (balance ratios, account age, limits)
  - `transaction_window_features` (1h, 6h, 24h, 30d sliding windows)
  - `velocity_risk_features` (rapid-fire attempts, failed-transaction bursts)
  - `temporal_behavioral_features` (weekend ratios, night-owl flags)
- **Point-in-Time Correctness:** Exact ASOF timestamp joining ($t_{feature} \le t_{obs}$) preventing any forward-looking leakage.
- **Low-Latency Online Serving:** Sub-2ms key retrieval from Redis 7.2.
- **Idempotent Materialization:** Scheduled batch and incremental sync from offline Parquet partitions into Redis.

---

## 4. Quickstart

```bash
# 1. Start Redis container
docker compose up -d redis

# 2. Materialize features into Redis online store
python scripts/seed_data.py
python featurehub/materialization/engine.py

# 3. Launch FeatureHub FastAPI serving daemon
python -m uvicorn featurehub.api.main:app --port 8010
```

---

## 5. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health and Redis connectivity status |
| `GET` | `/features` | List all 122 registered feature definitions |
| `GET` | `/features/{name}` | Retrieve schema and SLA metadata for a specific feature |
| `GET` | `/online/features/{entity_id}` | Low-latency entity feature vector retrieval |
| `POST` | `/predict` | Scikit-Learn real-time ML fraud classification |
| `GET` | `/materialization/status` | Current materialization watermark and row counts |

### Example Request (`POST /predict`):
```json
{
  "customer_id": "cust_000001",
  "transaction_amount": 25.50,
  "merchant_id": "merch_401"
}
```

### Example Response:
```json
{
  "prediction": 0,
  "risk_score": 0.0428,
  "decision": "LEGITIMATE",
  "model_version": "v1.0.0",
  "latency_ms": 4.12
}
```

---

## 6. Benchmarks

Measured in our reproducible local benchmark harness (Windows 11 x86_64, Redis 7.2, Python 3.13):

| Metric | Empirical Value | Target SLA | Status |
|---|:---:|:---:|:---:|
| **Redis Online Lookup (P99)** | **1.62 ms** | < 12.0 ms | **PASS** |
| **Redis Online Lookup (P50)** | **0.77 ms** | < 2.0 ms | **PASS** |
| **ML Prediction API (P99)** | **6.62 ms** | < 12.0 ms | **PASS** |
| **API Serving Throughput** | **228.5 req/s** | > 100 req/s | **PASS** |
| **Point-in-Time Data Leakage** | **0.0%** | 0.0% | **PASS** |

*Notice: Redis p99 = 1.62 ms is measured in our local benchmark environment (loopback socket) and is not claimed as public cloud WAN latency.*

---

## 7. Testing

```bash
# Run unit tests for feature registry, online store, and PIT engine
pytest featurehub/tests/ -v

# Run PIT temporal leakage verification
pytest featurehub/tests/test_pit.py -v
```

---

## 8. Interactive Demo

Launch the Unified Platform Dashboard to inspect FeatureHub interactively:
```bash
streamlit run apps/unified-dashboard/app.py --server.port 8505
```
1. Open **3. FeatureHub** $\to$ **Feature Registry Catalog** to inspect all 122 definitions.
2. Select **Point-in-Time Demo** to step through timestamp matching and verify zero leakage.
3. Open **9. ML Prediction** to execute real-time inference with live Redis features.

---

## 9. Limitations

1. **Local Benchmark Environment:** Benchmarks were recorded on dedicated local hardware; cloud virtualization and multi-region WAN topologies will exhibit higher network latency.
2. **Synthetic Feature Data:** Entity behavior is generated via realistic synthetic statistical distributions, not proprietary customer bank logs.
3. **Single-Cluster Redis:** Currently tested on a single-node Redis 7.2 instance; production deployment recommends Redis Sentinel or Redis Enterprise Cluster for multi-AZ failover.
