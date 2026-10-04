# DataGuard Architecture — Apache Airflow Data Pipeline Orchestration (Phase G)

## 1. Overview & Architectural Philosophy

Phase G establishes Apache Airflow as the centralized execution and scheduling backbone for DataGuard. Rather than embedding bespoke governance logic or shell scripts inside individual Airflow DAG files, DataGuard implements an **Inversion-of-Control Governance Architecture**:

```
                     ┌────────────────────────────────────────────────────────┐
                     │          Apache Airflow 2.9 (Scheduler & Workers)      │
                     └───────────────────────────┬────────────────────────────┘
                                                 │ invokes
                                                 ▼
                     ┌────────────────────────────────────────────────────────┐
                     │         DataGuard Quality & Orchestration Plugin       │
                     │  (DataGuardQualityOperator / Airflow Task Callables)   │
                     └───────────────────────────┬────────────────────────────┘
                                                 │ executes
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                DataGuard Unified Pipeline Execution Lifecycle                                │
├──────────────────────┬──────────────────────┬──────────────────────┬──────────────────┬──────────────────────┤
│ 1. Contract Fetch    │ 2. Schema Diff       │ 3. Quality Validation│ 4. Provenance    │ 5. Alerting & State  │
│ (PostgreSQL 16)      │ (Breaking Gate)      │ (Great Expectations) │ (OpenLineage)    │ (Incidents & Metrics)│
└──────────────────────┴──────────────────────┴──────────────────────┴──────────────────┴──────────────────────┘
```

Every pipeline run undergoes a deterministic, verifiable gate. Silent data corruptions and upstream schema breakages are intercepted before corrupt records propagate to analytical models or downstream consumers.

---

## 2. Airflow DAG Architecture & Repository Organization

The pipeline layout decouples orchestration definitions from operational logic:

```
pipelines/
└── airflow/
    ├── dags/
    │   ├── customer_quality_pipeline.py       # Hourly KYC, credit score, null validation
    │   ├── transaction_quality_pipeline.py    # 15-minute monetary ranges, currency, settlement checks
    │   ├── feature_quality_pipeline.py        # FeatureHub feature store freshness & distribution drift
    │   ├── schema_validation_pipeline.py      # Automated contract vs physical schema drift audit
    │   ├── freshness_monitoring_pipeline.py   # SLA compliance monitoring across platform datasets
    │   └── demo_test_pipelines.py             # 7 deterministic test pipelines (clean, defects, breaking)
    ├── plugins/
    │   └── dataguard_plugin.py                # DataGuardQualityOperator and Airflow UI integration
    ├── utils/
    │   └── task_helpers.py                    # Reusable XCom task handlers, lifecycle callbacks
    └── shim.py                                # Offline execution shim for local parsing and CI without Docker
```

### DAG Task Breakdown (Standard Pipeline)
Each core data quality DAG executes 8 standard, idempotent task stages:

1. `start_pipeline`: Generates unique execution UUID (`run_uuid`), verifies pipeline registration in `pipeline_metadata`, and records run in `RUNNING` state.
2. `load_contract`: Fetches authoritative YAML contract definition and active schema from PostgreSQL Contract Registry.
3. `validate_contract`: Evaluates syntactic contract validity and SLA thresholds.
4. `validate_schema`: Runs `SchemaDiffEngine` comparing physical schema vs declared contract; triggers fast-fail if breaking drift is detected.
5. `run_quality_checks`: Compiles Great Expectations expectation suite and runs dataset-level and referential validations.
6. `persist_quality_results`: Stores check-by-check diagnostic results and computed quality scores into `quality_runs` and `quality_checks`.
7. `emit_lineage`: Emits OpenLineage `COMPLETE` run event with input/output datasets and column-level facets.
8. `create_incident_if_required`: Evaluates check failures, de-duplicates open alerts, and opens an actionable incident in PostgreSQL with assigned owner routing.
9. `finalize_pipeline`: Updates `pipeline_runs` to `SUCCESS` and records duration metrics.

---

## 3. Retries, Fast-Fail, and Idempotency Policies

### Fast-Fail vs Transient Retries
DataGuard differentiates deterministic data quality bugs from transient infrastructure faults:
- **Deterministic Defects (Fast-Fail)**: Schema breakages, schema type narrowing, primary key duplicate violations, illegal enum values, and null constraint violations fail immediately without wasteful retries.
- **Transient Failures (Retryable)**: Network timeouts, database connection limits, and lock contentions trigger standard Airflow retries (configured via `default_args["retries"] = 1` and `retry_delay = timedelta(seconds=30)`).

### Idempotent Reruns
Every execution run is keyed by `run_id`. Successive runs with the same `run_id` update existing PostgreSQL rows in `pipeline_runs` without primary key collisions or duplicate incident creation.

---

## 4. Metadata Persistence & Analytics Model

DataGuard tracks operational orchestration telemetry in PostgreSQL 16 via two relational tables:

```sql
-- Pipeline Catalog
CREATE TABLE pipeline_metadata (
    pipeline_id VARCHAR(128) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    owner VARCHAR(128) NOT NULL,
    dataset VARCHAR(128) NOT NULL,
    contract VARCHAR(255) NOT NULL,
    freshness_sla_minutes INTEGER DEFAULT 60,
    description TEXT,
    schedule VARCHAR(64),
    status VARCHAR(32) DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_run_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    last_failure_at TIMESTAMP WITH TIME ZONE,
    tags_json JSONB DEFAULT '[]'::jsonb
);

-- Execution History
CREATE TABLE pipeline_runs (
    run_id VARCHAR(128) PRIMARY KEY,
    pipeline_id VARCHAR(128) REFERENCES pipeline_metadata(pipeline_id),
    dataset VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_ms DOUBLE PRECISION DEFAULT 0.0,
    quality_run_id VARCHAR(128),
    incident_id VARCHAR(128),
    lineage_run_id VARCHAR(128),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    metrics_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. FeatureHub Feature Store Quality Integration

`feature_quality_pipeline` specifically bridges DataGuard with FeatureHub:
- Validates offline feature tables (`customer_features`, `merchant_features`) before materialization to Redis.
- Audits feature freshness against inference SLAs.
- Asserts feature null rates remain below 5%.
- Verifies feature distribution row counts meet expected minimum batch volumes.
- Emits OpenLineage edges linking source entity tables (`customers`, `transactions`) to target feature views.
