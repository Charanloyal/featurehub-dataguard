# DataGuard OpenLineage Data Lineage Architecture

**Stage**: STAGE 3 — PHASE F: OPENLINEAGE DATA LINEAGE  
**Version**: 1.0.0  
**Specification**: OpenLineage 1.0.5 compliant  
**Persistence Backend**: PostgreSQL 16 (`featurehub_dataguard_postgres`)  
**Author**: Data Platform & Reliability Engineering Team  

---

## 1. Overview & System Topology

The **DataGuard OpenLineage Engine** provides end-to-end dataset-level and column-level operational data lineage. In modern machine learning and real-time transaction processing platforms like FeatureHub & DataGuard, determining data provenance, assessing upstream root causes of quality incidents, and calculating the downstream blast radius of schema alterations are paramount.

DataGuard ingests standardized **OpenLineage RunEvents** emitted during pipeline execution, records input/output datasets, persists multi-hop dependency edges, tracks fine-grained column transformations, and indexes everything in PostgreSQL 16.

```
+----------------------------------------------------------------------------------------------------+
|                                    DATAGUARD PHASE F TOPOLOGY                                      |
+----------------------------------------------------------------------------------------------------+
       PostgreSQL Tables                    Airflow DAGs / ETL                  Target Datasets
    (transactions, customers)         (quality_pipelines, compute)          (clean, features, redis)
                │                                    │                                  │
                └───────────────────┬────────────────┘                                  │
                                    │                                                   │
                                    ▼                                                   ▼
                          Pipeline Execution Hook ──────────────────────────► Output Datasets
                             (start_run / complete_run)                     (customer_features)
                                    │                                                   │
                                    ▼                                                   ▼
                           OpenLineage RunEvent                              ColumnLineage Facet
                        (Job, Run, Inputs, Outputs)                      (fields, inputs, transforms)
                                    │                                                   │
                                    └───────────────────┬───────────────────────────────┘
                                                        │
                                                        ▼
                                                LineageCollector
                                            (Prometheus Metrics Hook)
                                                        │
                                                        ▼
                                                LineageRepository
                                           (PostgreSQL 16 Persistence)
                                      ├── lineage_datasets (nodes)
                                      ├── lineage_jobs (pipelines)
                                      ├── lineage_runs (execution history)
                                      ├── lineage_edges (dependency graph)
                                      └── lineage_columns (column transformations)
                                                        │
                                    ┌───────────────────┴───────────────────┐
                                    ▼                                       ▼
                            FastAPI Endpoints                       Incident Correlation
                     (/lineage/graph, /upstream,               (incident.run_id -> lineage
                      /downstream, /columns)                    traversal for root cause)
```

---

## 2. OpenLineage Standard Compatibility

DataGuard implements the OpenLineage standard JSON schema specifications:

### 2.1 RunEvent Structure
- `eventType`: Lifecycle state: `START`, `RUNNING`, `COMPLETE`, `FAIL`, `ABORT`.
- `eventTime`: ISO-8601 UTC timestamp.
- `job`:
  - `namespace`: E.g., `airflow`, `spark`, `dataguard`.
  - `name`: Pipeline or task name (e.g. `feature_compute`, `transaction_quality_pipeline`).
  - `facets`: Custom facets including `pipeline_id` and documentation.
- `run`:
  - `runId`: Deterministic UUID identifying the execution run.
  - `facets`: Execution facets including `errorMessage`, `nominalTime`, and parameters.
- `inputs`:
  - Array of input datasets with `namespace`, `name`, and input facets.
- `outputs`:
  - Array of output datasets with `namespace`, `name`, and output facets, specifically including the `columnLineage` facet.

### 2.2 ColumnLineage Dataset Facet
Column transformations are attached directly to output datasets in the OpenLineage standard format:
```json
{
  "columnLineage": {
    "fields": {
      "cust_txn_amount_sum_30d": {
        "inputFields": [
          {"namespace": "postgres", "name": "transactions", "field": "amount"}
        ],
        "transformationDescription": "SUM(amount) over trailing 30d window",
        "transformationType": "TRANSFORMATION"
      }
    }
  }
}
```

---

## 3. Relational Lineage Data Model (PostgreSQL 16)

All lineage metadata is stored in dedicated, indexed tables in PostgreSQL 16.

### 3.1 Tables

1. **`lineage_datasets`**:
   - `dataset_id`: Unique identifier (`{namespace}.{name}`).
   - `namespace`: Source system (`postgres`, `airflow`, `featurehub`, `redis`).
   - `name`: Logical dataset name.
   - `description`: Text summary of dataset contents.
   - `schema_facets`: JSON column and type metadata.
2. **`lineage_jobs`**:
   - `job_id`: Unique job identifier (`{namespace}.{name}`).
   - `namespace`: Orchestrator namespace.
   - `name`: Job name.
   - `pipeline_id`: Pipeline grouping identifier.
3. **`lineage_runs`**:
   - `run_id`: Unique run identifier (e.g. `run_a93bfe844645431d`).
   - `job_id`: Job foreign key.
   - `pipeline_id`: Pipeline identifier.
   - `status`: `START`, `RUNNING`, `COMPLETE`, `FAIL`.
   - `start_time`, `end_time`: Execution boundaries.
   - `inputs_json`, `outputs_json`, `facets_json`: Captured context.
4. **`lineage_edges`**:
   - `edge_id`: Unique edge key.
   - `run_id`: Associated pipeline run.
   - `source_dataset`: Source node identifier.
   - `target_dataset`: Destination node identifier.
   - `pipeline_id`: Intermediary pipeline connecting source and target.
   - `edge_type`: `DATA_FLOW`, `INPUT_TO_PIPELINE`, `PIPELINE_TO_OUTPUT`, `DATASET_DEPENDENCY`.
5. **`lineage_columns`**:
   - `column_edge_id`: Unique mapping identifier.
   - `run_id`: Generating pipeline run.
   - `source_dataset`, `source_column`: Upstream origin.
   - `target_dataset`, `target_column`: Downstream destination.
   - `transformation`: Explicit formula/logic.
   - `pipeline_id`: Executing pipeline.

---

## 4. End-to-End Platform Lineage & FeatureHub Integration

DataGuard reflects the real data pipeline topology present in the repository:

### 4.1 Transaction Processing & Feature Store Flow
1. **Raw Database Ingestion**:
   - `postgres.transactions` $\to$ `transaction_quality_pipeline` $\to$ `transactions_clean`
2. **Customer Identity Ingestion**:
   - `postgres.customers` $\to$ `customer_quality_pipeline` $\to$ `customers_clean`
3. **Feature Computation (FeatureHub Offline Store)**:
   - `transactions_clean` + `customers_clean` $\to$ `feature_compute` $\to$ `customer_features` + `transaction_features`
4. **Online Store Materialization**:
   - `customer_features` + `transaction_features` $\to$ `feature_materialization` $\to$ `redis.online_features`

---

## 5. Column-Level Lineage & Transformations

Transformations reflect the actual feature calculations defined in `featurehub/computation/engine.py`:

| Target Dataset | Target Column | Source Dataset | Source Column | Transformation Logic |
| :--- | :--- | :--- | :--- | :--- |
| `customer_features` | `customer_id` | `transactions_clean` | `customer_id` | `GROUP BY customer_id entity key` |
| `customer_features` | `cust_txn_amount_sum_30d`| `transactions_clean` | `amount` | `SUM(amount) over trailing 30d window` |
| `customer_features` | `cust_txn_amount_avg_30d`| `transactions_clean` | `amount` | `AVG(amount) over trailing 30d window` |
| `customer_features` | `cust_txn_count_30d` | `transactions_clean` | `transaction_id` | `COUNT(transaction_id) over trailing 30d window` |
| `customer_features` | `cust_failed_txns_30d` | `transactions_clean` | `status` | `SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) over 30d` |
| `customer_features` | `cust_wire_amount_sum_30d`| `transactions_clean` | `channel` | `SUM(amount WHERE channel='WIRE') over 30d` |
| `customer_features` | `cust_last_txn_timestamp`| `transactions_clean` | `timestamp` | `MAX(timestamp) latest transaction occurrence` |
| `transaction_features`| `total_amount_24h` | `transactions_clean` | `amount` | `SUM(amount) over trailing 24h window` |
| `transaction_features`| `last_transaction_time` | `transactions_clean` | `timestamp` | `MAX(timestamp) over trailing window` |
| `redis.online_features`| `cust_txn_amount_sum_30d`| `customer_features`| `cust_txn_amount_sum_30d`| `HSET customer:{id} cust_txn_amount_sum_30d (Float32)`|

---

## 6. Graph Traversal Algorithms

The repository implements Breadth-First Search (BFS) graph traversal with configurable depth limits ($D_{\text{max}} = 5$):

### 6.1 Upstream Traversal (Root Cause Discovery)
Traverses reverse edges ($\text{target} \to \text{source}$) to uncover all direct and indirect ancestor datasets and producing pipelines feeding into a given asset.

### 6.2 Downstream Traversal (Impact & Blast Radius)
Traverses forward edges ($\text{source} \to \text{target}$) to identify all downstream consumer datasets, downstream ML features, and online stores impacted by a change or failure.

---

## 7. Quality Incident & Pipeline Run Correlation

DataGuard links quality check results directly to the execution pipeline run:
1. `QualityCheckResult` records `run_id` and `pipeline`.
2. When a validation check fails, `IncidentManager` persists `run_id` and `pipeline_id` into the `incidents` table.
3. The API endpoint `GET /incidents/{incident_id}/lineage` immediately resolves:
   - Which pipeline run produced the data that failed validation.
   - All upstream datasets that contributed inputs to that run.

---

## 8. REST API Specifications

| Endpoint | Method | Params | Description |
| :--- | :--- | :--- | :--- |
| `GET /lineage/graph` | `GET` | None | Returns complete machine-readable nodes and edges graph structure. |
| `GET /lineage/{dataset}` | `GET` | `dataset` | Returns summary including producing/consuming pipelines and immediate IO. |
| `GET /lineage/{dataset}/upstream`| `GET` | `dataset`, `depth` | Traverses upstream tree discovering root datasets and pipelines. |
| `GET /lineage/{dataset}/downstream`| `GET` | `dataset`, `depth` | Traverses downstream tree discovering consumer datasets and pipelines. |
| `GET /lineage/{dataset}/columns` | `GET` | `dataset`, `column` | Returns column-level mappings and mathematical transformations. |
| `GET /lineage/runs/{run_id}` | `GET` | `run_id` | Retrieves execution metadata, start/end timestamps, inputs, outputs, and facets. |
| `GET /lineage/pipelines/{pipeline_id}`| `GET` | `pipeline_id`, `limit`| Lists historical execution runs for a specific pipeline. |
| `POST /lineage/events` | `POST` | `RunEvent` payload | Ingests an OpenLineage standard compliant event into PostgreSQL. |
| `GET /incidents/{incident_id}/lineage`| `GET` | `incident_id` | Correlates incident to upstream lineage context for triage. |

---

## 9. Prometheus Observability Metrics

Exported dynamically at `/metrics`:
- `lineage_events_total{event_type, pipeline_id}`: Total ingested events.
- `lineage_event_failures_total{pipeline_id}`: Failed event processing count.
- `lineage_runs_total{pipeline_id, status}`: Total runs by pipeline and status.
- `lineage_failed_runs_total{pipeline_id}`: Failed runs count.
- `lineage_datasets_total`: Gauge tracking total unique datasets in graph.
- `lineage_edges_total`: Gauge tracking total dependency edges.
- `lineage_processing_duration_seconds{event_type}`: Histogram measuring ingestion latency.
