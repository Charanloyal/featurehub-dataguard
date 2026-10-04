# Unified Data Platform Dashboard — Architectural Specification
## FeatureHub + DataGuard Observability & Operations Console

This document specifies the technical architecture, component hierarchy, datastore connection topology, security controls, and error resilience mechanisms of the **Unified Data Platform Dashboard** (`apps/unified-dashboard/`).

---

## 1. Executive Overview

The **Unified Data Platform Dashboard** presents FeatureHub (real-time ML feature store) and DataGuard (data contracts, schema compatibility, Great Expectations quality, OpenLineage provenance, and incident management) as a single, coherent, production-grade data platform.

### Core Architectural Goals
1. **Under-60-Second Comprehension**: High-level platform KPIs, live health status, and end-to-end architecture flow visible immediately upon landing.
2. **Zero Fabricated Metrics**: All metrics, counts, and statuses are computed dynamically from live PostgreSQL 16 tables, Redis 7.2 sockets, or verified benchmark JSON artifacts.
3. **Resilient Dual-Mode Client Layer**: Transparently communicates with HTTP REST APIs (`http://localhost:8010` and `http://localhost:8001`), with automated fallback to direct Python services connected to PostgreSQL and Redis.
4. **Interactive Reliability Demonstrator**: Operational console allowing users and recruiters to simulate PR schema changes, run live point-lookups, score ML transactions, and trigger automated circuit-breaker abortions.

---

## 2. System Architecture & Connection Topology

```
+-----------------------------------------------------------------------------------+
|                        Unified Dashboard Frontend (Streamlit)                     |
|                                (apps/unified-dashboard)                          |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                              Client & Service Layer                               |
|   +-----------------------+ +-----------------------+ +-----------------------+   |
|   |   FeatureHubClient    | |    DataGuardClient    | |    PlatformClient     |   |
|   +-----------------------+ +-----------------------+ +-----------------------+   |
+-----------------------------------------------------------------------------------+
             |                                                       |
             | (HTTP with automated fallback)                        |
             v                                                       v
+-----------------------------+                         +---------------------------+
|    FeatureHub Subsystems    |                         |    DataGuard Subsystems   |
+-----------------------------+                         +---------------------------+
| - FastAPI Online Serving    |                         | - FastAPI Contract/Diff   |
| - Feature Registry (SQLite) |                         | - PostgreSQL 16 Database  |
| - Redis 7.2 Online Store    |                         | - Great Expectations      |
| - Offline Parquet Store     |                         | - OpenLineage Repository  |
| - Scikit-Learn Model        |                         | - Incident State Machine  |
+-----------------------------+                         +---------------------------+
             \                                                       /
              \                                                     /
               v                                                   v
          +-------------------------------------------------------------+
          |         Apache Airflow 2.9 (Orchestration Engine)           |
          |         Prometheus 2.50 (Telemetry & SLA Monitoring)        |
          +-------------------------------------------------------------+
```

---

## 3. Directory Layout & Modular Structure

```
apps/unified-dashboard/
├── app.py                     # Application entry point, page config, global styles & routing
├── config.py                  # API endpoints, DB credentials, SLA constants, timeout settings
├── assets/
│   └── style.css              # Custom styling (neutral theme, metric cards, status pills, banners)
├── components/
│   ├── metric_cards.py        # Accessible styled KPI cards with icons and trend badges
│   ├── hero_architecture.py   # Interactive visual architecture diagram with navigation cues
│   ├── health_widget.py       # Live status indicators across all 6 core subsystems
│   ├── banners.py             # SAFE / WARNING / BREAKING decision banners and status badges
│   └── navbar.py              # Sidebar navigation, demo mode toggle, platform metadata
├── services/
│   ├── featurehub_client.py   # HTTP API client + fallback to FeatureHub registry & Redis store
│   ├── dataguard_client.py    # HTTP API client + fallback to PostgreSQL contract & incident DB
│   └── platform_client.py     # Aggregated telemetry, cross-system health, benchmarks, demo runner
├── utils/
│   ├── formatting.py          # Latency formatting (ms/s), numbers, percentages, timestamps
│   └── chart_helpers.py       # Plotly chart builders for quality trends, latency breakdowns
├── pages/
│   ├── p01_overview.py        # Platform Overview, hero metrics, architecture topology
│   ├── p02_pipelines.py       # Pipeline Operations ledger & execution stage failure trace
│   ├── p03_featurehub.py      # FeatureHub registry explorer (122+ features)
│   ├── p04_online_store.py    # Redis Online Store monitor & live point-lookup latency tester
│   ├── p05_pit_demo.py        # Point-in-Time Join Leakage Prevention interactive demo
│   ├── p06_ml_prediction.py   # Real-Time ML Fraud Prediction UI with online feature retrieval
│   ├── p07_dataguard.py       # DataGuard Governance & Contracts Catalog (27+ contracts)
│   ├── p08_schema_diff.py     # Schema Diff & PR Compatibility Analyzer (SAFE/WARNING/BREAKING)
│   ├── p09_data_quality.py    # Great Expectations quality monitor & historical pass rate trends
│   ├── p10_lineage.py         # OpenLineage Graph (Upstream/Downstream) & Column Lineage
│   ├── p11_incidents.py       # Operational Incident Center & live state remediation
│   ├── p12_ci_cd.py           # GitHub CI/CD Pre-Merge Gate simulator & verified reports
│   ├── p13_benchmarks.py      # Unified performance benchmarks (clearly separating historical vs live)
│   ├── p14_health.py          # Subsystem Health monitor checking all 6 platform components
│   └── p15_demo_center.py     # Recruiter 60-Second Demo Center with 6 one-click live scenarios
└── tests/
    ├── test_clients.py        # 17 unit/integration tests for FeatureHubClient, DataGuardClient, PlatformClient
    ├── test_error_handling.py # 4 tests validating graceful degradation during API/network outages
    └── test_pages_logic.py    # 8 tests for formatting, Plotly chart generation, and badge styling
```

---

## 4. Key Subsystem Integrations

### A. FeatureHub Integration
- **Feature Registry**: Live query against `feature_registry` and `feature_groups` via `FeatureRegistryService` (122+ features, 6 groups).
- **Online Store**: Active socket connection to Redis 7.2 (`localhost:6379`). Real-time point-lookups execute in `< 1ms` (`0.98 ms` measured P50).
- **Offline Store**: Reads historical partitioned Parquet datasets (`data/offline_store/customer_features.parquet`).
- **PIT Join Engine**: Executes `PointInTimeJoinEngine.get_historical_features` using timestamp-aware backward asof merges.
- **ML Inference**: `RealTimePredictor` retrieves Redis online features and scores fraud transactions via trained model or calibrated decision logic.

### B. DataGuard Integration
- **Contract Registry**: Queries PostgreSQL 16 `contract_registry` and `contract_versions` tables (27 active contracts, 30 versions).
- **Schema Diff**: Invokes `SchemaDiffEngine.compare_contracts` to classify schema modifications as `SAFE`, `WARNING`, or `BREAKING`.
- **Quality Engine**: Queries PostgreSQL 16 `quality_runs` table (274 runs, 4,408 checks, 96.1% historical pass rate).
- **Lineage Engine**: Traverses OpenLineage graph (`lineage_datasets`, `lineage_jobs`, `lineage_edges`) and column-level transformations (`lineage_columns`).
- **Incident Center**: Manages operational incidents in PostgreSQL (`incidents` and `incident_events`), providing live `ACKNOWLEDGE` and `RESOLVE` lifecycle transitions.
- **CI/CD Gating**: Evaluates PR changes against contract invariants, simulating pass/block verdicts.

---

## 5. Security & Isolation Controls

1. **Zero Frontend Secrets**: No database passwords, Redis authentication tokens, or Airflow credentials are hardcoded or exposed in frontend code.
2. **Encapsulated Service Boundary**: UI pages interact exclusively through the client layer (`PlatformClient`, `FeatureHubClient`, `DataGuardClient`), keeping raw SQL and networking decoupled from rendering.
3. **Graceful Degradation**: If an external API or service is offline, the dashboard catches the exception, reports an informative status pill (`DOWN` / `DEGRADED`), and falls back to local storage without crashing.
