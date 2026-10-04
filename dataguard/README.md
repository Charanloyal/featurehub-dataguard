# DataGuard – Data Quality, Contracts & Lineage Platform

DataGuard enforces schema contracts, detects breaking schema edits pre-merge in CI, tracks quality validation suites, and generates OpenLineage graph topologies.

## Key Capabilities
- **25 Data Contracts**: Standardized YAML definitions with data types, nullability, freshness SLAs, and allowed enum values.
- **Persistent Contract Registry**: PostgreSQL schema registry storing full contract versions (`v1`, `v2`, etc.), complete raw YAMLs, metadata, and owner attribution.
- **Contract Loading & Validation**: CLI automation (`python scripts/register_contracts.py`) to discover, structurally validate, and store contracts.
- **Contract Catalog CLI**: CLI utility (`python scripts/list_contracts.py`) to search and list registered contract versions.
- **FastAPI Contract Endpoints**: Production REST API (`/contracts`, `/contracts/{name}`, `/contracts/{name}/versions`, `/contracts/{name}/validate`).
- **Schema Diff Engine**: Classifies schema edits into `SAFE`, `WARNING`, and `BREAKING`, detecting added/removed columns, type drift, nullability changes, enum shifts, and constraint modifications.
- **Physical Table Schema Drift Detection**: Directly inspects live PostgreSQL database tables against data contracts.
- **Diff CLI Utility**: `python scripts/diff_contracts.py` supports file-to-file, version-to-version, and contract-to-table comparisons with `--strict` CI gating.
- **FastAPI Diff Endpoints**: Production endpoints `/schema/diff`, `/contracts/{name}/diff`, and `/contracts/{name}/diff/table`.
- **Prometheus Observability**: Tracks registered contract counts, validation pass/fail counters, schema diff evaluations, and HTTP request latencies.

## Contract Registry & Schema Diff Architecture

```
  dataguard/contracts/*.yaml
             │
             ▼
   scripts/register_contracts.py
             │
             ▼
      ContractValidator (Phase A)
             │
             ▼
   ContractRegistryService (PostgreSQL)
        ├── contract_registry (dataset metadata)
        └── contract_versions (version history & YAMLs)
             │
             ▼
   SchemaDiffEngine (Phase C) ◄─── Physical Database Tables
        ├── Compare Contract Versions
        └── Compare Contract vs Live Table
             │
             ▼
      FastAPI REST API (/contracts, /schema/diff)
```

## CLI Usage

### Register All Contracts
```bash
python scripts/register_contracts.py
```
Discovers all `.yaml` files in `dataguard/contracts/`, validates structural integrity, and persists new versions to the database.

### List Contract Catalog
```bash
python scripts/list_contracts.py
```
Displays registered datasets, active version, owner, and freshness SLA.

### Compare Contract Schemas
```bash
# Compare two versions of a registered contract from PostgreSQL
python scripts/schema_diff.py --dataset orders --from-version v1.0.0 --to-version v1.1.0

# Compare two YAML contract files
python scripts/schema_diff.py --file1 dataguard/tests/fixtures/schema_v1.yaml --file2 dataguard/tests/fixtures/schema_breaking.yaml

# Output machine-readable JSON
python scripts/schema_diff.py --dataset orders --from-version v1.0.0 --to-version v1.1.0 --json

# Strict CI/CD mode (exit code 1 on WARNING or BREAKING)
python scripts/schema_diff.py --dataset orders --from-version v1.0.0 --to-version v1.1.0 --strict
```

## Compatibility Policies

| Severity | Description | CI Recommendation | Typical Triggers |
| :--- | :--- | :--- | :--- |
| **`SAFE`** | Completely backward-compatible modifications | **`APPROVE`** | Adding nullable columns, description edits, range expansions, enum additions, SLA relaxations, safe type widening. |
| **`WARNING`** | Invariant modifications requiring producer/consumer sync | **`APPROVE WITH WARNING`** | Adding non-nullable columns, tightening freshness SLAs, tightening numeric ranges, adding check constraints. |
| **`BREAKING`** | Incompatible modifications that fail queries or reject data | **`BLOCK MERGE`** | Removing columns, incompatible type changes, narrowing type conversions, tightening nullability (`nullable: false`), removing enum values, unique constraint additions. |

## API Endpoints

- `GET /health`: Health status and total registered contracts.
- `POST /contracts`: Register a new contract payload (returns `201 Created`, `409` on duplicate version, `422` on invalid structure).
- `GET /contracts`: List registered contracts (supports `owner`, `status`, `dataset`, `version` query parameters).
- `GET /contracts/{name}`: Get latest version of dataset contract.
- `GET /contracts/{name}/versions`: Get version history for a dataset.
- `GET /contracts/{name}/versions/{version}`: Get specific version of a contract.
- `POST /contracts/{name}/validate`: Validate contract payload structure.
- `POST /schema/diff`: Compare two arbitrary contract schemas (`SAFE`, `WARNING`, `BREAKING`).
- `GET /contracts/{name}/diff`: Compare two versions of a dataset contract from registry.
- `POST /contracts/{name}/diff/table`: Compare contract against live physical database table.
- `POST /quality/validate/{dataset}`: Run automated Great Expectations validation against dataset.
- `GET /quality/results`: Query granular check results with dataset/status/pipeline filtering.
- `GET /quality/summary`: Dynamically computed system-wide quality overview.
- `GET /quality/{dataset}`: Latest quality run for dataset.
- `GET /quality/{dataset}/latest`: Explicit latest quality run for dataset.
- `GET /quality/{dataset}/history`: Chronological historical quality runs for dataset.
- `GET /incidents`: List incidents with dataset, status, pipeline, severity, and owner filters.
- `GET /incidents/{incident_id}`: Retrieve single incident with full audit event history.
- `POST /incidents/{incident_id}/ack`: Acknowledge an open incident (`OPEN` -> `ACKNOWLEDGED`).
- `POST /incidents/{incident_id}/resolve`: Resolve an incident (`ACKNOWLEDGED`/`OPEN` -> `RESOLVED`).
- `GET /incidents/{incident_id}/events`: Retrieve chronological audit events for an incident.
- `GET /incidents/summary`: Dynamic operational incident summary including counts and MTTA/MTTR.
- `GET /incidents/{incident_id}/lineage`: Correlates quality incidents to upstream pipeline runs and data.
- `GET /lineage/graph`: Dynamic machine-readable graph topology (`nodes` and `edges`) from PostgreSQL.
- `GET /lineage/{dataset}`: Complete lineage summary for dataset including producing/consuming pipelines.
- `GET /lineage/{dataset}/upstream`: Traverses upstream directed dependencies using BFS.
- `GET /lineage/{dataset}/downstream`: Traverses downstream directed dependencies using BFS.
- `GET /lineage/{dataset}/columns`: Fine-grained column-level lineage transformations and formulas.
- `GET /lineage/runs/{run_id}`: Pipeline run metadata, execution status, and IO facets.
- `GET /lineage/pipelines/{pipeline_id}`: Historical execution runs for a specific pipeline.
- `POST /lineage/events`: Ingests OpenLineage 1.0.5 compliant RunEvent payloads.
- `GET /metrics`: Prometheus observability metrics (including quality, incident, and lineage counters/histograms).

## Data Quality Engine (Phase D)

DataGuard converts declarative contracts into native **Great Expectations 1.x** test suites:
- **Contract-to-Expectations Mapping**: Automatically translates nullability, uniqueness, sets/enums, numeric bounds, and row counts into GX expectations.
- **Freshness Evaluation**: Evaluates timestamp latency vs contract SLA minutes ($\text{Latency} = T_{\text{current}} - T_{\text{last\_record}}$), classifying into `FRESH`, `WARNING`, or `STALE`.
- **Referential Integrity**: Verifies cross-dataset foreign key relationships (e.g. `orders.customer_id` $\to$ `customers.customer_id`), reporting orphan counts, orphan percentages, and sample orphan IDs.
- **Transparent Quality Score**: Calculated dynamically as $\frac{\text{Passed Checks}}{\text{Total Checks}} \times 100.0$.
- **Persistent Storage**: All runs and check results persist in PostgreSQL (`quality_runs` and `quality_results` tables).

## Incident Management System (Phase E)

DataGuard automatically turns real quality check failures into actionable, persistent operational incidents:
- **Real Quality Failures Only**: Purely failure-driven; successful validation checks never trigger incidents.
- **Persistent Storage**: Incidents and append-only audit trail stored in PostgreSQL 16 (`incidents` and `incident_events` tables).
- **Deterministic Deduplication**: Computes SHA-256 failure signature over `(dataset, check_name, expectation_type, column, pipeline)`. Active unresolved incidents suppress duplicate generation.
- **Severity Classification Policy**: Centralized policy mapping failures to `CRITICAL` (PK corruption, referential foreign key breaches, severe freshness SLA breaches), `HIGH` (null non-nullable values, numeric range breaches), `MEDIUM` (enum mismatches, moderate delay), `LOW`, and `INFO`.
- **Contract Owner Routing**: Automatically routes incidents to the dataset owner declared in the contract metadata (e.g. `e-commerce-data-team`, `payments-team`).
- **Finite State Machine Lifecycle**: Validates lifecycle transitions (`OPEN` $\to$ `ACKNOWLEDGED` $\to$ `RESOLVED`) while rejecting invalid backwards transitions (e.g. `RESOLVED` $\to$ `ACKNOWLEDGED`).
- **Operational SRE Metrics**: Dynamically calculates Mean Time To Acknowledge (MTTA) and Mean Time To Resolve (MTTR) from database timestamps.
- **Full Observability**: Prometheus metrics export counters (`incidents_created_total`, `incidents_open_total`, etc.) and transition duration histograms.
- **Interactive CLI Demo**: `python scripts/incident_demo.py` executes 5 production failure scenarios.

## OpenLineage Data Lineage Engine (Phase F)

DataGuard captures and exposes fine-grained dataset and column-level lineage using OpenLineage standard events:
- **Standard RunEvent Ingestion**: Ingests `START`, `RUNNING`, `COMPLETE`, and `FAIL` execution events from Airflow DAGs and platform services into PostgreSQL 16 (`lineage_datasets`, `lineage_jobs`, `lineage_runs`, `lineage_edges`, `lineage_columns`).
- **FeatureHub Topology**: Maps end-to-end provenance from raw PostgreSQL tables (`transactions`, `customers`) $\to$ quality pipelines $\to$ FeatureHub offline feature datasets (`customer_features`, `transaction_features`) $\to$ Redis online feature stores (`redis.online_features`).
- **Column-Level Lineage**: Preserves fine-grained mathematical transformations (e.g. `SUM(amount) over trailing 24h window`, `GROUP BY customer_id entity key`, `MAX(timestamp)`) attached via standard `columnLineage` output dataset facets.
- **Multi-Hop BFS Traversal**: Sub-10ms graph algorithms for upstream root-cause diagnosis and downstream blast radius impact analysis.
- **Incident Lineage Correlation**: Quality failures and incidents link directly to `run_id` and pipeline definitions, providing upstream provenance for fast incident resolution.
- **Prometheus Observability**: Tracks ingested events (`lineage_events_total`), failure counters, run statuses, and processing duration histograms.
- **Performance Benchmarks**: Evaluated on live PostgreSQL 16 with sub-10ms query latencies (`scripts/benchmark_lineage.py`).
- **Interactive CLI Demo**: `python scripts/lineage_demo.py` demonstrates end-to-end graph traversal and column-level inspection.

## Apache Airflow Data Pipeline Orchestration (Phase G)

DataGuard integrates Apache Airflow as the execution backbone orchestrating real data governance workflows:
- **16 Production & Test DAGs**: Loaded with 0 import errors in Dockerized Airflow (`customer_quality_pipeline`, `transaction_quality_pipeline`, `feature_quality_pipeline`, `schema_validation_pipeline`, `freshness_monitoring_pipeline`, and 7 deterministic test pipelines).
- **Core Orchestrator Flow**: Every pipeline sequentially executes Contract Loading -> Schema Diff Gate -> Great Expectations Validation -> OpenLineage Emission -> Incident Management -> State Persistence.
- **Fast-Fail vs Retries**: Deterministic defects (breaking schema drift, null violations, primary key collisions) fail fast without retries; transient infrastructure faults trigger exponential backoff.
- **Idempotent Reruns**: Repeated runs with identical `run_id` update cleanly in PostgreSQL without duplicate key collisions.
- **Relational Run History & Catalog**: `pipeline_metadata` tracks 26 production pipeline configurations; `pipeline_runs` logs duration, status, and diagnostic metrics.
- **FastAPI Pipeline Endpoints**: Production REST endpoints (`/pipelines`, `/pipelines/summary`, `/pipelines/{id}`, `/pipelines/{id}/runs`, `/pipelines/{id}/latest`, `/pipelines/{id}/health`).
- **Prometheus Telemetry**: Real-time counters (`pipeline_runs_total`, `pipeline_failure_total`, `pipeline_retries_total`, `pipeline_stale_total`) and execution duration histograms (`pipeline_duration_seconds`).
- **Automated Validation**: 28 automated tests in `dataguard/tests/test_airflow_pipelines.py` with full benchmark report in `dataguard/benchmarks/airflow_results.json` (See [`docs/DATAGUARD_AIRFLOW_VALIDATION.md`](../docs/DATAGUARD_AIRFLOW_VALIDATION.md)).
