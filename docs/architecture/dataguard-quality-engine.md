# DataGuard Data Quality Engine Architecture

**Stage**: STAGE 3 — PHASE D  
**Version**: 1.0.0  
**Engine**: Great Expectations 1.23.2 + PostgreSQL 16 + FastAPI  
**Author**: Data Platform & Reliability Engineering Team  

---

## 1. Overview

The **DataGuard Data Quality Engine** delivers automated, contract-driven data quality validation across all production datasets in the platform. Rather than relying on static scripts or disconnected rule definitions, DataGuard transforms declarative **Data Contracts** directly into native **Great Expectations 1.x suites**, evaluates them against actual dataset batches, assesses dataset freshness SLAs and cross-dataset referential integrity, calculates transparent quality scores, and records historical results in PostgreSQL.

```
+-----------------------------------------------------------------------------------+
|                                DATAGUARD PIPELINE                                 |
+-----------------------------------------------------------------------------------+
  Data Contract (YAML/DB)           Target Dataset (DataFrame/Table)
         │                                       │
         ▼                                       ▼
  ContractExpectationBuilder          DatasetBatch Definition
  (Maps schema constraints)           (Whole dataframe batch)
         │                                       │
         └───────────────────┬───────────────────┘
                             │
                             ▼
               Great Expectations 1.x Runner
               (Executes native validations)
                             │
         ┌───────────────────┴───────────────────┐
         ▼                                       ▼
  FreshnessValidator                ReferentialIntegrityValidator
  (now - max_record_time)           (Cross-dataset foreign keys)
         │                                       │
         └───────────────────┬───────────────────┘
                             │
                             ▼
                    QualityRunResult
         (Status: PASS/FAIL/WARN, Score: passed/total * 100)
                             │
         ┌───────────────────┴───────────────────┐
         ▼                                       ▼
  PostgreSQL Result Store                 Prometheus Metrics
  (quality_runs & quality_results)       (Counters & Histograms)
         │
         ▼
  FastAPI Endpoints
  (/quality/validate, /results, /summary, /latest, /history)
```

---

## 2. Great Expectations Architecture Integration

DataGuard integrates natively with **Great Expectations (GX) 1.x** using ephemeral data contexts:

1. **Context Initialization**: `gx.get_context(mode="ephemeral")` provides an isolated, performant evaluation workspace per execution.
2. **Suite Compilation**: An `ExpectationSuite` is created dynamically for the target contract.
3. **Data Source & Asset Registration**:
   - A Pandas data source is added: `ctx.data_sources.add_pandas(f"ds_{run_id}")`
   - A dataframe asset is defined: `data_source.add_dataframe_asset(f"asset_{dataset_name}")`
   - A whole-dataframe batch definition is attached: `data_asset.add_batch_definition_whole_dataframe(f"bd_{run_id}")`
4. **Validation Definition**:
   ```python
   val_def = ctx.validation_definitions.add(
       gx.ValidationDefinition(name=f"val_{run_id}", data=batch_def, suite=suite)
   )
   results = val_def.run(batch_parameters={"dataframe": active_df})
   ```
5. **No Mocking / Zero Fakes**: Real metrics are calculated over real dataset rows.

---

## 3. Contract-to-Expectation Mapping Layer

The mapping engine (`ContractExpectationBuilder`) translates declarative contract rules into native Great Expectations:

| Contract Rule | Great Expectations 1.x Expectation | Severity |
| :--- | :--- | :--- |
| `column.name` | `expect_column_to_exist(column=col)` | `CRITICAL` |
| `nullable: false` | `expect_column_values_to_not_be_null(column=col)` | `HIGH` |
| `unique: true` | `expect_column_values_to_be_unique(column=col)` | `HIGH` |
| `allowed_values: [...]` | `expect_column_values_to_be_in_set(column=col, value_set=[...])` | `MEDIUM` |
| `min: X, max: Y` | `expect_column_values_to_be_between(column=col, min_value=X, max_value=Y)` | `MEDIUM` |
| `constraints.min_rows: N`| `expect_table_row_count_to_be_between(min_value=N)` | `HIGH` |

---

## 4. Freshness SLA Validation Model

Freshness is computed dynamically from actual record timestamps:

$$\Delta_{\text{latency}} = T_{\text{current\_utc}} - \max(T_{\text{record\_utc}})$$

Classification Policy against Contract SLA ($SLA_{\text{minutes}}$):

1. **`FRESH`**: $\Delta_{\text{latency}} \le SLA_{\text{minutes}}$
2. **`WARNING`**: $SLA_{\text{minutes}} < \Delta_{\text{latency}} \le 2 \times SLA_{\text{minutes}}$ (Approaching stale state)
3. **`STALE`**: $\Delta_{\text{latency}} > 2 \times SLA_{\text{minutes}}$ (Unacceptable latency breach)
4. **`UNKNOWN`**: No parseable timestamp column or empty dataset.

---

## 5. Referential Integrity Engine

Cross-dataset relational constraints are evaluated without relying on database-level foreign key enforcement:

- **Orders $\to$ Customers**: `orders.customer_id` must resolve to a valid `customers.customer_id`.
- **Order Items $\to$ Orders**: `order_items.order_id` must resolve to `orders.order_id`.
- **Order Items $\to$ Products**: `order_items.product_id` must resolve to `products.product_id`.
- **Payments $\to$ Orders**: `payments.order_id` must resolve to `orders.order_id`.
- **Transactions $\to$ Accounts/Merchants/Customers**: Foreign keys in transactions must exist in parents.
- **Fraud Events $\to$ Transactions**: `fraud_events.transaction_id` must reference valid transactions.

When orphaned records are detected:
- Check status is set to `FAIL` (Severity: `CRITICAL`).
- Orphan count, percentage, and a sample of orphan keys (up to 5) are recorded in `details`.

---

## 6. Transparent Quality Score

DataGuard avoids opaque, black-box scores. The quality score is transparently and deterministically defined:

$$\text{Quality Score} = \left( \frac{\text{Passed Checks}}{\text{Total Checks}} \right) \times 100.0$$

Overall run status aggregation:
- `FAIL`: Any check failed ($\ge 1$ check with `status = FAIL`).
- `WARNING`: No checks failed, but at least 1 check is in `WARNING` state.
- `PASS`: 100% of checks passed.

---

## 7. PostgreSQL Persistence Architecture

Validation runs and granular check results persist across two relational tables in PostgreSQL:

### `quality_runs` Table
```sql
CREATE TABLE quality_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    dataset_name VARCHAR(128) NOT NULL,
    contract_version VARCHAR(64) DEFAULT 'v1.0.0',
    pipeline_name VARCHAR(128) DEFAULT 'default_pipeline',
    overall_status VARCHAR(32) NOT NULL,
    total_checks INTEGER DEFAULT 0,
    passed_checks INTEGER DEFAULT 0,
    failed_checks INTEGER DEFAULT 0,
    warning_checks INTEGER DEFAULT 0,
    quality_score DOUBLE PRECISION DEFAULT 100.0,
    duration_ms DOUBLE PRECISION DEFAULT 0.0,
    freshness_status VARCHAR(32) DEFAULT 'FRESH',
    freshness_delay_minutes DOUBLE PRECISION,
    last_record_timestamp VARCHAR(64),
    row_count INTEGER DEFAULT 0,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT
);
```

### `quality_results` Table
```sql
CREATE TABLE quality_results (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES quality_runs(run_id) ON DELETE CASCADE,
    dataset_name VARCHAR(128) NOT NULL,
    check_name VARCHAR(256) NOT NULL,
    column_name VARCHAR(128),
    expectation_type VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    success BOOLEAN NOT NULL,
    observed_value TEXT,
    expected_value TEXT,
    duration_ms DOUBLE PRECISION DEFAULT 0.0,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    pipeline_name VARCHAR(128) DEFAULT 'default_pipeline',
    details_json TEXT
);
```

---

## 8. REST API Endpoints

The engine is exposed via DataGuard FastAPI service:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/quality/validate/{dataset}` | Executes validation suite against dataset; accepts optional JSON payload. |
| `GET` | `/quality/results` | Returns individual check records with `dataset`, `status`, `pipeline` filters. |
| `GET` | `/quality/summary` | Returns platform-wide dynamic quality summary. |
| `GET` | `/quality/{dataset}` | Returns latest validation run for dataset. |
| `GET` | `/quality/{dataset}/latest`| Explicit latest validation run for dataset. |
| `GET` | `/quality/{dataset}/history`| Returns chronological run history for dataset. |
| `GET` | `/metrics` | Exposes Prometheus metrics including all quality engine counters and histograms. |

---

## 9. Prometheus Observability Metrics

The engine exports six dedicated Prometheus metrics:

- `quality_validation_total{dataset, status}`: Total validation runs executed.
- `quality_validation_failures_total{dataset}`: Total failed validation runs.
- `quality_checks_total{dataset, expectation_type}`: Total individual checks executed.
- `quality_check_failures_total{dataset, expectation_type, severity}`: Total failed individual checks.
- `quality_validation_duration_seconds{dataset}`: Histogram of validation latency in seconds.
- `freshness_violations_total{dataset}`: Total freshness SLA breaches.
