# FeatureHub & DataGuard: Real-Time Feature Store & Data Reliability Platform

[![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-passing-success.svg)](https://github.com/Charanloyal/featurehub-dataguard/actions)
[![Tests](https://img.shields.io/badge/tests-276%20passed%20(100%25)-brightgreen.svg)](docs/FINAL_TEST_RESULTS.md)
[![Live Demo](https://img.shields.io/badge/demo-LIVE%20PUBLIC-blue.svg)](https://90f79d38525429.lhr.life)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade, production-style internal data platform that bridges low-latency ML feature engineering with active pre-materialization data quality gating:
- **FeatureHub**: Real-Time Feature Store (122 features across 6 entity domains), sub-millisecond Redis serving, and 100% leak-free Point-in-Time (PIT) training set generation.
- **DataGuard**: Data Contract enforcement (27 schemas), Schema Diff & Backward Compatibility engine, Great Expectations quality suites, OpenLineage provenance, and automated incident management.

---

## 🌐 Live Public Demo & Source Code

- **Canonical Repository (Source Code)**: [Charanloyal/featurehub-dataguard](https://github.com/Charanloyal/featurehub-dataguard)
- **Live Unified Dashboard (Public Demo)**: [https://sympathy-mesh-microphone-oakland.trycloudflare.com](https://sympathy-mesh-microphone-oakland.trycloudflare.com)
- **Live Public Gateway API**: [https://crafts-leaves-spring-beef.trycloudflare.com](https://crafts-leaves-spring-beef.trycloudflare.com)
- **Public API Health Check**: [https://crafts-leaves-spring-beef.trycloudflare.com/health](https://crafts-leaves-spring-beef.trycloudflare.com/health)
- **Public Platform Status**: [https://crafts-leaves-spring-beef.trycloudflare.com/platform/status](https://crafts-leaves-spring-beef.trycloudflare.com/platform/status)
- **Recruiter 3–5 Minute Walkthrough**: [`docs/demos/recruiter-demo.md`](docs/demos/recruiter-demo.md)

---

## 🏛️ Architecture Overview

The platform supports two deployment architectures:
1. **Local Full Platform**: Complete containerized stack with PostgreSQL 16, Redis 7.2, and Apache Airflow.
2. **Public Demo Mode**: Secure, lightweight public gateway exposing deterministic demo entities and controlled endpoints over HTTPS without exposing internal infrastructure.

```
                      [ Recruiter / Browser Client ]
                                    │
                                    ▼ (HTTPS / TLS 1.3)
       ┌─────────────────────────────────────────────────────────┐
       │                 PUBLIC ACCESS PERIMETER                 │
       │                                                         │
       │   Unified Streamlit Dashboard (Port 8505)              │
       │   Public Gateway API (Port 8000, FastAPI)               │
       └────────────┬─────────────────────────────┬──────────────┘
                    │                             │
        (Safe JSON Proxies)               (Controlled Endpoints)
                    │                             │
       ┌────────────▼─────────────────────────────▼──────────────┐
       │                PRIVATE INTERNAL SERVICES                │
       │                                                         │
       │   • PostgreSQL 16 (Port 5432 - Internal Only)           │
       │   • Redis 7.2 (Port 6379 - Internal Only)               │
       │   • Airflow 2.9 (Port 8080 - Internal Only)             │
       │   • Prometheus 2.51 (Port 9090 - Internal Only)         │
       │   • Grafana (Port 3000 - Internal Only)                 │
       │   • FeatureHub Internal API (Port 8010)                 │
       │   • DataGuard Internal API (Port 8001)                  │
       └─────────────────────────────────────────────────────────┘
```

### End-to-End Data Pipeline Flow
```
Data Sources (Parquet / PostgreSQL)
        ↓
Airflow Orchestration (26 Pipelines / 10 Dedicated DAGs)
        ↓
DataGuard Pre-Materialization Gating
  ├─ Contract Enforcement (27 Datasets)
  ├─ Schema Diff & Compatibility Check (SAFE / WARNING / BREAKING)
  ├─ Great Expectations Validation Suite (344k rows/sec)
  └─ OpenLineage Provenance Emission (START / COMPLETE / FAIL)
        ↓
Feature Computation (Vectorized Rolling Windows ~550ms)
        ↓
Dual Store Engine:
  ├─ Offline Store: Partitioned Parquet Lake (Leak-Free PIT Joins)
  └─ Online Store: Redis 7.2 Key-Value Store (Sub-2ms Lookup)
        ↓
Real-Time ML Inference (FastAPI < 7ms Fraud Scoring API)
```

---

## 🚀 Quickstart: Local Full Platform

Run the complete platform locally using Docker Compose:

```bash
# 1. Clone repository
git clone https://github.com/Charanloyal/featurehub-dataguard.git
cd featurehub-dataguard

# 2. Setup environment variables
cp .env.example .env

# 3. Start local infrastructure containers (PostgreSQL, Redis, Airflow)
docker compose up -d postgres redis airflow-webserver airflow-scheduler

# 4. Install Python dependencies in a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .

# 5. Seed synthetic financial data and baseline contracts
python scripts/seed_data.py
python scripts/register_contracts.py

# 6. Run end-to-end integrated pipeline
python scripts/run_integrated_pipeline.py

# 7. Launch Unified Platform Dashboard
streamlit run apps/unified-dashboard/app.py --server.port 8505
```

Access local interfaces:
- **Unified Dashboard**: `http://localhost:8505`
- **Airflow UI**: `http://localhost:8080` (credentials: `airflow` / `airflow`)
- **Prometheus Metrics**: `http://localhost:9090`
- **Grafana Dashboards**: `http://localhost:3000` (credentials: `admin` / `admin`)

---

## 🛡️ Public Demo Mode

For recruiters and cloud evaluators, the platform provides a standalone, lightweight **Demo Mode**:
- Exposes deterministic entities (`cust_000001`, `cust_000002`), realistic contract diff scenarios, and real Scikit-Learn fraud risk prediction.
- Can be reset to a pristine state at any time via:
  ```bash
  python scripts/reset_demo.py
  ```
- **Controlled Public API Endpoints**:
  - `GET /health` — Distinguishes `HEALTHY`, `DEGRADED`, and `DEMO MODE`
  - `GET /platform/status` — Operational telemetry across services
  - `GET /features` & `GET /features/{name}` — Metadata for 122 registered features
  - `GET /online/features/{entity_id}` — Sub-millisecond online feature vector
  - `POST /predict` — Scikit-Learn fraud probability classification
  - `GET /contracts` — 27 active data contracts
  - `POST /schema/diff` — Pre-merge schema diff with breaking change classification
  - `GET /quality/summary` — Great Expectations validation metrics
  - `GET /lineage/{dataset}` — Column-level OpenLineage DAG
  - `GET /incidents` — Operational data quality incidents
  - `GET /pipelines` — 26 production pipeline definitions

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Core Languages** | Python 3.12 / 3.13, SQL |
| **API & Serving** | FastAPI, Uvicorn, Pydantic v2 |
| **Feature Store & Cache** | Redis 7.2 (Online), Apache Parquet & PyArrow (Offline) |
| **Databases** | PostgreSQL 16 (Contract Registry, Incident Store, Lineage) |
| **Orchestration** | Apache Airflow 2.9 (10 Dedicated DAGs + 16 Dynamic Definitions) |
| **Data Quality & Testing** | Great Expectations 1.x, Pytest |
| **Lineage & Metadata** | OpenLineage Standard, Marquez Schema Compatibility |
| **Machine Learning** | Scikit-Learn (Random Forest & Gradient Boosting), Pandas, NumPy |
| **Dashboard & UI** | Streamlit, Plotly, HTML5/CSS3 Design System |

---

## 📊 Verified Benchmarks & Empirical Audit

All performance claims are derived from reproducible benchmark runs recorded in our test environment:

| Metric Category | Claim / Requirement | Empirically Measured Value | Status | Environment |
|---|---|:---:|:---:|---|
| **Feature Store Scale** | 120+ features | **122 registered features** | **VERIFIED** | SQLite / PostgreSQL |
| **Redis Online Lookup p99** | Sub-12ms SLA | **1.62 ms** (p50: **0.77 ms**) | **VERIFIED** | Dedicated Benchmark Harness (Redis 7.2) |
| **ML Prediction API p99** | Sub-12ms SLA | **6.62 ms** (p50: **4.20 ms**) | **VERIFIED** | FastAPI + Redis + Scikit-Learn |
| **Point-In-Time (PIT) Leakage** | Zero train/serve leakage | **0.0% (Zero Leakage)** | **VERIFIED** | Pytest PIT temporal boundary suite |
| **Production Pipelines** | 25+ pipelines | **26 production pipelines** | **VERIFIED** | PostgreSQL Registry & Airflow DAGs |
| **Schema Breaking Changes Blocked** | High pre-merge gate | **100.0% of tested scenarios in reproducible validation benchmark** | **VERIFIED** | CI Gate Experiment (5/5 blocked) |
| **Data Quality Throughput** | High throughput | **344,340 rows/sec** (290ms / 100k) | **VERIFIED** | Great Expectations 1.x |
| **Lineage Graph Traversal** | Sub-10ms latency | **6.29 ms** (Mean) | **VERIFIED** | OpenLineage Column-Level Engine |
| **Incident Triage Reduction** | 55% MTTR reduction | **~55% workflow reduction** | **UNVERIFIED / DESIGN GOAL** | Design target; multi-human trial unverified |

*Notice: Local benchmark numbers (e.g. Redis p99 = 1.62 ms) represent internal datastore lookups measured in our local benchmark environment, clearly distinguished from live public cloud round-trip latencies.*

For complete benchmark artifacts, see [`docs/CV_METRICS.md`](docs/CV_METRICS.md) and [`docs/FINAL_BENCHMARK_INDEX.md`](docs/FINAL_BENCHMARK_INDEX.md).

---

## 🧪 Tests & Quality Assurance

The platform includes a test suite covering contract parsing, schema diffing, Great Expectations suites, incident lifecycle, Airflow DAG integrity, and PIT temporal boundaries:

```bash
# Run complete test suite
pytest -v

# Run schema breaking change experiment
python scripts/schema_breaking_experiment.py

# Verify deterministic demo baseline
python scripts/reset_demo.py
```

**Verification State**: **276 / 276 tests passed (100% green)** in `132.47s`. Full test report available at [`docs/FINAL_TEST_RESULTS.md`](docs/FINAL_TEST_RESULTS.md).

---

## 🔒 Security & Safe Operations

- **No Committed Secrets**: Source code contains zero hardcoded credentials, API keys, or private tokens. All secrets are loaded through `.env`.
- **Zero Internal Port Exposure**: Internal databases (PostgreSQL `5432`, Redis `6379`, Airflow `8080`, Prometheus `9090`) are isolated to internal Docker bridge networks and are never exposed directly to the public internet.
- **Controlled Public APIs**: The public gateway exposes strictly validated, read-only analytical and demo endpoints. Arbitrary SQL execution and administrative deletions are prohibited.
- **Security Headers**: Injected automatically on all gateway responses (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`).

---

## ⚠️ Limitations & Truth Disclosures

To maintain engineering integrity:
1. **Public Hosting Scope**: The public demo URL provides access to the lightweight Public Gateway and Unified Dashboard with deterministic demo state. The heavy multi-service infrastructure (full Airflow scheduler, 5,000-customer historical backfill pipelines) is intended for local execution via Docker.
2. **Incident Triage Reduction Metric**: While automated root-cause indexing runs in **5.44 ms**, human triage MTTR reduction is labeled **UNVERIFIED / DESIGN GOAL** because validating human operational efficiency requires longitudinal multi-engineer production trials.
3. **Schema Breaking Change Gate**: The 100% blocking rate represents **100% of tested scenarios in our reproducible validation benchmark** (5 breaking evolutions, 3 safe backward-compatible evolutions).

---

## 📄 Documentation Directory

- [`docs/deployment/live-demo.md`](docs/deployment/live-demo.md) — Live public deployment, operations, and rollback guide
- [`docs/demos/recruiter-demo.md`](docs/demos/recruiter-demo.md) — 3–5 minute recruiter demo walkthrough
- [`docs/CV_METRICS.md`](docs/CV_METRICS.md) — Measured performance metrics & audit scorecard
- [`docs/PIPELINE_INVENTORY.md`](docs/PIPELINE_INVENTORY.md) — Inventory of 26 production data pipelines
- [`docs/FINAL_TEST_RESULTS.md`](docs/FINAL_TEST_RESULTS.md) — 276-test execution log and pass verification

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
