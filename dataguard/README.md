# DataGuard: Data Reliability, Contracts & Lineage Platform

**Primary Repository:** [Charanloyal/featurehub-dataguard](https://github.com/Charanloyal/featurehub-dataguard)

DataGuard is a proactive data reliability and governance platform providing declarative data contracts, backward-compatibility schema diffing, Great Expectations suites, column-level OpenLineage graphs, and automated incident response.

---

## 1. Problem

Data platform and ML teams constantly face "silent data failures":
1. **Unannounced Upstream Schema Changes:** An upstream team drops or alters a column, causing batch transformations or feature ingestion to fail silently or crash in production.
2. **Untracked Blast Radius:** When bad data enters a warehouse, engineering lacks instant visibility into which downstream feature tables, models, or dashboards are impacted.
3. **Reactive Firefighting:** Data quality bugs are discovered by downstream stakeholders rather than being gated automatically in CI or aborting pipelines pre-materialization.

DataGuard shifts data reliability left by treating data as a product governed by enforced contracts.

---

## 2. Architecture

```
                    ┌────────────────────────┐
                    │ Upstream Data Releases │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ DataGuard CI/CD Gate   │
                    │ (Schema Diff Engine)   │
                    └───────────┬────────────┘
                                │ (SAFE / APPROVE)
                                ▼
                    ┌────────────────────────┐
                    │ Airflow Ingestion DAGs │
                    └───────────┬────────────┘
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
                 ▼                             ▼
      ┌─────────────────────┐       ┌─────────────────────┐
      │ Great Expectations  │       │ OpenLineage Proven- │
      │ Data Quality Suites │       │ ance Event Graph    │
      └──────────┬──────────┘       └──────────┬──────────┘
                 │                             │
                 ▼                             ▼
      ┌─────────────────────┐       ┌─────────────────────┐
      │ PostgreSQL Incident │       │ Circuit Breaker     │
      │ Management Engine   │       │ (Pre-Materialize)   │
      └─────────────────────┘       └─────────────────────┘
```

---

## 3. Features

- **27 Production Data Contracts:** Standardized YAML definitions for schemas, constraints, freshness SLAs, and owners stored in PostgreSQL 16.
- **Automated Schema Diff Engine:** Evaluates contract evolutions and categorizes changes into `SAFE`, `WARNING`, and `BREAKING`.
- **Pre-Merge CI Quality Gate:** Enforces contract checks in GitHub Actions, blocking pull requests containing breaking changes with exit code 1.
- **Great Expectations Integration:** Executes high-throughput validation suites (344k+ rows/sec) before feature materialization.
- **OpenLineage & Column-Level Provenance:** Emits `START`, `COMPLETE`, and `FAIL` events to construct end-to-end dataset lineage graphs.
- **Operational Incident Tracking:** Automatically files, prioritizes, and routes incidents in PostgreSQL when data expectations breach.

---

## 4. Quickstart

```bash
# 1. Start PostgreSQL datastore
docker compose up -d postgres

# 2. Register all baseline data contracts into PostgreSQL
python scripts/register_contracts.py

# 3. Test schema diff engine
python scripts/schema_diff.py --dataset customers --from-version v1.0.0 --to-version v1.1.0

# 4. Launch DataGuard FastAPI daemon
python -m uvicorn dataguard.api.main:app --port 8001
```

---

## 5. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health status and registered contract counts |
| `GET` | `/contracts` | List all 27 active data contracts |
| `POST` | `/schema/diff` | Compare base and target contracts (`SAFE` / `WARNING` / `BREAKING`) |
| `GET` | `/quality/summary` | Aggregated Great Expectations pass rate and execution stats |
| `GET` | `/lineage/{dataset}` | Column-level and dataset-level upstream/downstream graph |
| `GET` | `/incidents` | Operational data incidents filtered by status or severity |
| `POST` | `/incidents/{id}/ack` | Acknowledge incident (`OPEN` $\to$ `ACKNOWLEDGED`) |
| `POST` | `/incidents/{id}/resolve` | Resolve incident (`ACKNOWLEDGED` $\to$ `RESOLVED`) |
| `GET` | `/pipelines` | Inventory of 26 production pipeline definitions |

### Example Request (`POST /schema/diff`):
```json
{
  "base_contract": {
    "dataset": "orders",
    "version": "1.0.0",
    "columns": [{"name": "id", "type": "integer"}]
  },
  "target_contract": {
    "dataset": "orders",
    "version": "1.1.0",
    "columns": [{"name": "id", "type": "string"}]
  }
}
```

### Example Response:
```json
{
  "classification": "BREAKING",
  "is_breaking": true,
  "recommendation": "BLOCK MERGE",
  "total_changes": 1,
  "breaking_changes": 1,
  "warning_changes": 0,
  "safe_changes": 0
}
```

---

## 6. Benchmarks

Measured on reproducible local benchmark infrastructure:

| Metric | Measured Value | Standard / SLA | Status |
|---|:---:|:---:|:---:|
| **Schema Breaking Changes Blocked in CI** | **100.0%** (5/5 blocked) | Block all breaking PRs | **PASS** |
| **Data Quality Evaluation Throughput** | **344,340 rows/sec** (290ms / 100k) | High throughput batch | **PASS** |
| **Lineage Graph Query Latency** | **6.29 ms** (Mean) | < 25.0 ms | **PASS** |
| **Incident Creation Latency** | **22.09 ms** (P50) | < 50.0 ms | **PASS** |
| **Circuit Breaker Fast-Fail Abort** | **911 ms** | < 1,050 ms | **PASS** |

*Note: The 100% breaking change blocking result represents 100% of tested scenarios in our reproducible validation benchmark suite.*

---

## 7. Testing

```bash
# Run complete DataGuard test suite
pytest dataguard/tests/ -v

# Run reproducible schema-breaking change experiment
python scripts/schema_breaking_experiment.py
```

---

## 8. Interactive Demo

Launch the Unified Platform Dashboard:
```bash
streamlit run apps/unified-dashboard/app.py --server.port 8505
```
1. Open **4. DataGuard** $\to$ **Data Contracts** to inspect 27 registered contracts.
2. Open **6. Schema & Contracts** to simulate breaking schema evolutions and inspect the **BLOCK MERGE** recommendation.
3. Open **7. Lineage** to explore visual DAG dependencies and column mappings.
4. Open **8. Incident Management** to triage and resolve quality incidents.

---

## 9. Limitations

1. **Experimental CI Benchmark:** The 100% schema blocking metric was evaluated on 8 representative evolution scenarios (5 breaking, 3 safe) rather than a multi-year enterprise history.
2. **Incident Triage Reduction Status:** While incident indexing operates in **5.44 ms**, MTTR reduction is labeled **UNVERIFIED / DESIGN GOAL** because validating human triage efficiency requires multi-human team trials.
3. **Local Airflow Topology:** Configured for single-node LocalExecutor rather than Celery or KubernetesExecutor on AWS/GCP.
