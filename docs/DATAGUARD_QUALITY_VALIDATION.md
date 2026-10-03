# DataGuard Phase D — Data Quality Engine Validation Report

**Phase**: STAGE 3 — PHASE D: DATA QUALITY ENGINE (Phase C was Schema Diff & Compatibility Engine)  
**Date**: October 3, 2026  
**Quality Framework**: Great Expectations 1.23.2  
**Result Store Database**: PostgreSQL 16 Alpine (`featurehub_dataguard_postgres` on `localhost:5432`)  
**Status**: COMPLETE & FULLY VERIFIED  

---

## 1. Executive Summary

Phase D of DataGuard delivers an automated, contract-driven data quality engine powered by **Great Expectations 1.x**.
Contracts act as the definitive source of truth, translating declarative schema definitions and business constraints into native Great Expectations suites. Real datasets (`customers`, `accounts`, `orders`, `order_items`, `payments`, `products`, `merchants`, `transactions`, `fraud_events`) are validated against nullability, uniqueness, allowed sets, numeric boundaries, table row counts, freshness SLAs, and cross-dataset referential integrity. All execution results are persisted in PostgreSQL, queryable via FastAPI endpoints, and monitored with Prometheus metrics.

---

## 2. Test Suite Results

- **Total Test Suite**: **105 tests passed** (0 failures, 0 skipped).
- **Phase D Specific Tests**: **35 tests passed**:
  - `dataguard/tests/test_quality_engine.py`: **30 unit and API tests**
  - `dataguard/tests/test_quality_postgres.py`: **5 live PostgreSQL integration tests**
- **Prior Phases Regression Status**: **0 regressions** (70/70 Phase A, B, and C tests continue to pass).

### Pytest Run Output
```text
============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: featurehub-dataguard
collected 105 items

dataguard/tests/test_contract_registry.py ...........                    [ 10%]
dataguard/tests/test_phase_a_contracts.py ....                           [ 14%]
dataguard/tests/test_postgres_integration.py .....                       [ 19%]
dataguard/tests/test_quality_engine.py ..............................    [ 47%]
dataguard/tests/test_quality_postgres.py .....                           [ 52%]
dataguard/tests/test_schema_diff.py .............                        [ 64%]
dataguard/tests/test_schema_diff_engine.py .......................       [ 86%]
dataguard/tests/test_schema_diff_postgres.py ....                        [ 90%]
dataguard/tests/test_type_compatibility.py ..........                    [100%]

====================== 105 passed, 2 warnings in 11.86s =======================
```

---

## 3. Live PostgreSQL Integration Test Status

Validation flow:
`Real Dataset -> Contract -> ContractExpectationBuilder -> Great Expectations 1.x -> DataQualityRunner -> PostgreSQL Result Store`

Tested against live container `featurehub_dataguard_postgres`:
- `test_1_postgres_quality_connectivity`: **PASSED** (PostgreSQL container online; `quality_runs` and `quality_results` tables confirmed in information schema).
- `test_2_e2e_quality_validation_persists_to_postgres`: **PASSED** (Full clean validation run persisted; SQL queries confirm exact check and run parity).
- `test_3_postgres_bad_dataset_failure_recorded`: **PASSED** (Failures and diagnostics accurately saved to PostgreSQL with overall status `FAIL`).
- `test_4_postgres_retrieval_and_summary`: **PASSED** (Latest run and dynamic platform summary queried directly from PostgreSQL).
- `test_5_api_e2e_postgres`: **PASSED** (FastAPI endpoints return live PostgreSQL persisted data).

---

## 4. Datasets Validated

Nine core datasets matching platform contracts were validated:

1. **`customers`**: Evaluated for ID uniqueness, KYC status enum set, risk tiers, and countries.
2. **`accounts`**: Evaluated for balance ranges, account types, and foreign key link to `customers`.
3. **`merchants`**: Evaluated for merchant risk score bounds ($[0.01, 0.95]$), merchant categories, and countries.
4. **`products`**: Evaluated for price ranges, stock quantities, and product catalog uniqueness.
5. **`orders`**: Evaluated for order total boundaries ($0.0 \le \text{total} \le 100,000.0$), currency sets (`USD`, `EUR`, `GBP`, `CAD`), row count constraints ($\ge 10$), and referential link to `customers`.
6. **`order_items`**: Evaluated for item quantity ranges ($1 \le q \le 100$), unit prices, and dual foreign keys (`orders`, `products`).
7. **`payments`**: Evaluated for payment methods, settlement statuses (`SETTLED`, `PENDING`, `REFUNDED`), and foreign key to `orders`.
8. **`transactions`**: Evaluated for amount bounds, channel sets, fraud flags, and triple foreign keys (`customers`, `accounts`, `merchants`).
9. **`fraud_events`**: Evaluated for fraud typologies (`ACCOUNT_TAKEOVER`, `CARD_TESTING`, etc.), and foreign key to `transactions`.

---

## 5. Checks Executed & Pass/Fail Matrix

| Check Type | Expectation Implementation | Clean Dataset | Bad Fixture | Detected Diagnostic |
| :--- | :--- | :--- | :--- | :--- |
| **Not-Null** | `expect_column_values_to_not_be_null` | **PASS** | **FAIL** | Unexpected null values detected |
| **Uniqueness** | `expect_column_values_to_be_unique` | **PASS** | **FAIL** | Duplicate primary keys detected |
| **Accepted Values** | `expect_column_values_to_be_in_set` | **PASS** | **FAIL** | Unrecognized enum values identified |
| **Numeric Bounds** | `expect_column_values_to_be_between` | **PASS** | **FAIL** | Negative amounts or out-of-bounds metrics flagged |
| **Row Count** | `expect_table_row_count_to_be_between` | **PASS** | **FAIL** | Row count below contract minimum flagged |
| **Referential Integrity** | `expect_column_values_to_match_foreign_key`| **PASS** | **FAIL** | Orphan count, orphan %, and sample orphan keys |
| **Freshness SLA** | `expect_dataset_freshness_within_sla` | **PASS** (FRESH) | **FAIL** (STALE)| SLA delay $> 2\times$ SLA limit detected |

---

## 6. Transparent Quality Score Calculation

DataGuard applies a deterministic mathematical definition for data quality scores:

$$\text{Quality Score} = \left( \frac{\text{Passed Checks}}{\text{Total Checks}} \right) \times 100.0$$

- **Clean Datasets**: $\frac{16}{16} \times 100.0 = \mathbf{100.0\%}$ (Status: `PASS`)
- **Null Injections**: $\frac{14}{16} \times 100.0 = \mathbf{87.50\%}$ (Status: `FAIL`)
- **Negative Transactions**: $\frac{15}{16} \times 100.0 = \mathbf{93.75\%}$ (Status: `FAIL`)
- **No Static/Mocked Scores**: Every score is derived dynamically from evaluated Great Expectations results.

---

## 7. Freshness Evaluation Results

Freshness is computed as $\Delta_{\text{latency}} = T_{\text{current}} - \max(T_{\text{record}})$:

| Scenario | Record Age | Contract SLA | Latency ($\Delta$) | Result Status |
| :--- | :--- | :--- | :--- | :--- |
| **Live Incoming Stream** | 15 minutes ago | 60 minutes | 15.0m | **`FRESH`** |
| **Approaching Delay** | 90 minutes ago | 60 minutes | 90.0m | **`WARNING`** |
| **Stale Pipeline** | 72 hours ago | 60 minutes | 4,320.0m | **`STALE`** |

---

## 8. Performance Benchmark Results

Benchmarked across 1,000, 10,000, and 100,000 rows (`orders` contract suite with 15 Great Expectations checks):

| Dataset Size | Number of Checks | Mean Latency (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (rows/sec) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1,000 rows** | 15 checks | **143.24 ms** | 143.19 ms | 146.12 ms | 146.36 ms | **6,981.52 rows/s** |
| **10,000 rows** | 15 checks | **186.26 ms** | 162.78 ms | 259.11 ms | 278.11 ms | **53,687.16 rows/s** |
| **100,000 rows** | 15 checks | **276.84 ms** | 274.44 ms | 283.32 ms | 284.11 ms | **361,223.04 rows/s** |

---

## 9. Known Limitations & Next Steps

1. **Airflow Orchestration**: In-line validation is exposed via CLI and REST API; Airflow DAG sensor automation will be introduced in subsequent orchestration phases.
2. **OpenLineage Emitters**: Validation results are persisted in PostgreSQL and Prometheus; OpenLineage dataset facet integration is delivered in Phase F.
3. **Cross-Database Foreign Keys**: Referential integrity is evaluated efficiently in-memory via Pandas hash joins; for multi-million row parent tables, pushdown SQL JOIN queries can be utilized.
