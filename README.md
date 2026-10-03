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
- **25+ Production Contracts**: Standardized YAML definitions for schemas, constraints, and SLAs.
- **Schema Diff Engine**: Automated CI check classifying schema edits into `SAFE`, `WARNING`, and `BREAKING`.
- **Data Quality & Incident System**: Great Expectations suites with automated incident lifecycle tracking (`OPEN`, `ACKNOWLEDGED`, `RESOLVED`).
- **OpenLineage Integration**: Column-level lineage graphs across pipelines and data products.

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
