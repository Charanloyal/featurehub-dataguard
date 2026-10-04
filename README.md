# FeatureHub & DataGuard: Real-Time Feature Store & Data Reliability Platform

[![CI/CD Pipeline](https://github.com/example/featurehub-dataguard/actions/workflows/ci.yml/badge.svg)](https://github.com/example/featurehub-dataguard/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)

Production-style internal data platform containing two connected systems:
- **FeatureHub**: Real-Time Feature Store & Online ML Serving Engine
- **DataGuard**: Data Quality, Schema Contracts & Column-Level Lineage Platform

---

## Architecture Overview

```
                      +-------------------+
                      | Historical Data   |
                      | PostgreSQL / CSV  |
                      +---------+---------+
                                |
                                v
                      +-------------------+
                      | Feature Compute   |
                      | PySpark / Pandas  |
                      +----+---------+----+
                           |         |
                           v         v
             +---------------+     +------------------+
             | Offline Store |     | Feature Registry |
             | (Parquet/PG)  |     | (Metadata DB)    |
             +-------+-------+     +--------+---------+
                     |                      |
                     v                      v
             +---------------+     +------------------+
             | PIT Join Engine|    | Materialization  |
             +-------+-------+     +--------+---------+
                     |                      |
                     v                      v
             +---------------+     +------------------+
             | Model Training|     | Online Store     |
             | & Evaluation  |     | (Redis)          |
             +-------+-------+     +--------+---------+
                     |                      |
                     +----------+-----------+
                                |
                                v
                     +---------------------+
                     | Real-Time Predict   |
                     | FastAPI Inference   |
                     +---------------------+
```

---

## Key Features

### FeatureHub
- **120+ Real Features**: Customer velocity, merchant risk, temporal transaction window stats, behavioral indicators.
- **Point-In-Time (PIT) Correctness**: Leak-free training dataset generation with entity-timestamp matching.
- **Sub-Millisecond Online Serving**: High-throughput feature retrieval from Redis.
- **Idempotent Materialization**: Full and incremental backfill pipelines with freshness SLA monitoring.

### DataGuard
- **25+ Production Contracts**: Standardized YAML definitions for schemas, constraints, and SLAs in PostgreSQL 16.
- **Schema Diff & Compatibility Engine**: Automated check classifying schema edits into `SAFE`, `WARNING`, and `BREAKING`.
- **Data Quality & Incident System**: Great Expectations suites with automated incident lifecycle tracking (`OPEN`, `ACKNOWLEDGED`, `RESOLVED`).
- **OpenLineage Integration**: Column-level lineage graphs across pipelines and data products.
- **Airflow Data Pipeline Orchestration**: 16 DAGs executing real DataGuard workflows with fast-fail schema checks, automated Great Expectations validation, OpenLineage provenance, SLA audits, and dynamic health tracking. (See [`docs/DATAGUARD_AIRFLOW_VALIDATION.md`](docs/DATAGUARD_AIRFLOW_VALIDATION.md)).
- **GitHub CI/CD Gating**: Deterministic PR pre-merge gate evaluating Contract Validation -> Schema Diff -> Data Quality Regression -> `SAFE` / `WARNING` / `BREAKING` -> Merge or Block Merge (exit code 1). (See [`docs/DATAGUARD_CI_GATING_VALIDATION.md`](docs/DATAGUARD_CI_GATING_VALIDATION.md)).

### Integrated Platform (Phase I)
- **11-Stage End-to-End Flow**: Connects Data Source $\to$ Feature Computation $\to$ DataGuard Contract Validation $\to$ Schema Diff $\to$ Great Expectations $\to$ OpenLineage $\to$ Airflow $\to$ Offline Parquet Store $\to$ Materialization $\to$ Redis $\to$ FeatureHub API $\to$ ML Prediction.
- **Fast-Fail Circuit Breaker**: Malformed features, breaking schema drift, or stale feature vectors abort downstream materialization in `< 1.05s`, logging an OpenLineage `FAIL` RunEvent and filing a prioritized incident (`CRITICAL`/`HIGH`/`MEDIUM`) in PostgreSQL routed to the contract owner. (See [`docs/FEATUREHUB_DATAGUARD_INTEGRATION_VALIDATION.md`](docs/FEATUREHUB_DATAGUARD_INTEGRATION_VALIDATION.md) and [`docs/benchmarks/featurehub-dataguard-integration.md`](docs/benchmarks/featurehub-dataguard-integration.md)).

---

## Quick Start

```bash
# 1. Setup environment
cp .env.example .env

# 2. Start services via Docker Compose
make start

# 3. Seed financial transaction domain data & materialization
make seed

# 4. Train ML model & run benchmarks
make benchmark

# 5. Run tests
make test
```

---

## System Access

| Application / Service | URL | Credentials / Notes |
| :--- | :--- | :--- |
| **FeatureHub Dashboard** | `http://localhost:8501` | Feature Registry, PIT Demo, Online Store Explorer |
| **DataGuard Dashboard** | `http://localhost:8502` | Contracts, Schema Diff, Quality Incidents, Lineage |
| **FeatureHub REST API** | `http://localhost:8000/docs` | OpenAPI Docs |
| **DataGuard REST API** | `http://localhost:8001/docs` | OpenAPI Docs |
| **Airflow UI** | `http://localhost:8080` | `airflow` / `airflow` |
| **Prometheus** | `http://localhost:9090` | System & API Metrics |
| **Grafana** | `http://localhost:3000` | `admin` / `admin` |

---

## Measured Performance & CV Alignment

All performance metrics and CV bullet claims are generated from reproducible benchmark suites.
See [`docs/CV_METRICS.md`](docs/CV_METRICS.md) for execution instructions and verified outputs.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
