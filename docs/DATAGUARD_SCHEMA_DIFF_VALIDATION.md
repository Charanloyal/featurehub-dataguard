# DataGuard Schema Diff & Compatibility Engine Validation Report

**Phase**: STAGE 3 — PHASE C: SCHEMA DIFF & COMPATIBILITY ENGINE  
**Date**: October 3, 2026  
**Registry Database**: PostgreSQL 16 Alpine (`featurehub_dataguard_postgres` on `localhost:5432`)  
**Status**: COMPLETE & FULLY VERIFIED  

---

## 1. Test Suite Results

- **Total Test Suite**: 70 tests passed (0 failures, 0 skipped)
- **Phase C Specific Tests**: 50 tests passed:
  - `dataguard/tests/test_schema_diff_engine.py`: 23 tests
  - `dataguard/tests/test_type_compatibility.py`: 10 tests
  - `dataguard/tests/test_schema_diff.py`: 13 tests
  - `dataguard/tests/test_schema_diff_postgres.py`: 4 tests (Real PostgreSQL integration)
- **Phase A & Phase B Regressions**: 0 (20/20 Phase A & B tests continue to pass)

### Pytest Run Summary
```text
============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: featurehub-dataguard
collected 70 items

dataguard/tests/test_contract_registry.py ...........                    [ 15%]
dataguard/tests/test_phase_a_contracts.py ....                           [ 21%]
dataguard/tests/test_postgres_integration.py .....                       [ 28%]
dataguard/tests/test_schema_diff.py .............                        [ 47%]
dataguard/tests/test_schema_diff_engine.py .......................       [ 80%]
dataguard/tests/test_schema_diff_postgres.py ....                        [ 85%]
dataguard/tests/test_type_compatibility.py ..........                    [100%]

======================= 70 passed, 2 warnings in 2.50s ========================
```

---

## 2. Real PostgreSQL Integration Test Results

Integration flow:
`PostgreSQL 16 -> Registered Contract v1 -> Registered Contract v2 -> Schema Diff Engine -> Compatibility Result`

Tested against live container `featurehub_dataguard_postgres`:
- `test_postgres_schema_diff_safe_evolution`: **PASSED** (`v1.0.0` vs `v1.1.0` -> `SAFE`, `APPROVE`)
- `test_postgres_schema_diff_warning_evolution`: **PASSED** (`v1.0.0` vs `v1.2.0` -> `WARNING`, `APPROVE WITH WARNING`)
- `test_postgres_schema_diff_breaking_evolution`: **PASSED** (`v1.0.0` vs `v2.0.0` -> `BREAKING`, `BLOCK MERGE`)
- `test_fastapi_schema_diff_against_real_postgres`: **PASSED** (all HTTP codes verified against real PostgreSQL registry)

---

## 3. Scenarios Evaluated & Verified

### A. SAFE Scenarios Tested
1. **Adding a nullable column**: Added `customer_tier` / `discount_code` with `nullable: true` (SAFE, APPROVE).
2. **Updating description**: Root and column-level description updates (SAFE, APPROVE).
3. **Relaxing Freshness SLA**: Increased SLA from 60m to 120m (SAFE, APPROVE).
4. **Relaxing Numeric Range**: Expanded `max` from 10,000 to 20,000 or decreased `min` (SAFE, APPROVE).
5. **Adding Allowed Enum Values**: Added `refunded` to `[pending, paid, cancelled]` (SAFE, APPROVE).
6. **Relaxing Uniqueness**: Changed `unique: true` to `unique: false` (SAFE, APPROVE).
7. **Relaxing Nullability**: Changed `nullable: false` to `nullable: true` (SAFE, APPROVE).
8. **Safe Type Widening**:
   - `integer` -> `bigint` (SAFE)
   - `integer` -> `numeric` (SAFE)
   - `float` -> `numeric` (SAFE)

### B. WARNING Scenarios Tested
1. **Adding a non-nullable column**: Added `currency` with `nullable: false` (WARNING, APPROVE WITH WARNING).
2. **Tightening Freshness SLA**: Reduced SLA from 60m to 30m (WARNING, APPROVE WITH WARNING).
3. **Tightening Numeric Range**: Tightened `min` from 0.01 to 1.0 or `max` from 10,000 to 5,000 (WARNING, APPROVE WITH WARNING).
4. **Custom Table Check Constraints**: Added new table validation constraint expressions (WARNING, APPROVE WITH WARNING).

### C. BREAKING Scenarios Tested
1. **Removing an existing column**: Deleted `notes` column (BREAKING, BLOCK MERGE).
2. **Incompatible Cross-Domain Type Changes**:
   - `integer` -> `string` (BREAKING)
   - `string` -> `integer` (BREAKING)
   - `boolean` -> `string` (BREAKING)
3. **Narrowing Type Conversions**:
   - `float` -> `integer` (BREAKING)
   - `bigint` -> `integer` (BREAKING)
4. **Tightening Nullability**: Changed `notes` from `nullable: true` to `nullable: false` (BREAKING, BLOCK MERGE).
5. **Removing Allowed Enum Values**: Removed `paid` from `[pending, paid, cancelled]` (BREAKING, BLOCK MERGE).
6. **Tightening Uniqueness**: Changed `unique: false` to `unique: true` on existing column (BREAKING, BLOCK MERGE).
7. **Column Rename Heuristic**: Simultaneous drop and add of identical type column classified as rename (BREAKING, BLOCK MERGE).
8. **Multiple Mixed Changes**: Combination of SAFE + WARNING + BREAKING yields highest severity: `BREAKING` (BLOCK MERGE).

---

## 4. Benchmark Performance Results

Benchmarked with 100 iterations per scale (10 warmups) on Windows 11 (AMD64 / Intel Core):

| Column Count | p50 Latency | p95 Latency | p99 Latency | Mean Latency | Changes Evaluated |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **10 columns** | **0.067 ms** | 0.181 ms | 0.244 ms | 0.103 ms | 4 |
| **50 columns** | **0.195 ms** | 0.305 ms | 0.334 ms | 0.206 ms | 9 |
| **100 columns** | **0.372 ms** | 0.419 ms | 0.525 ms | 0.382 ms | 16 |
| **250 columns** | **0.877 ms** | 1.479 ms | 1.617 ms | 0.952 ms | 39 |

Raw results persisted in: `dataguard/benchmarks/schema_diff_results.json`

---

## 5. Live Endpoints and CLI Verification

### CLI Commands Verified:
```bash
# Safe Comparison
python scripts/schema_diff.py --dataset pg_diff_orders --from-version v1.0.0 --to-version v1.1.0
-> Exit 0, Overall Classification: SAFE, Recommendation: APPROVE

# Warning Comparison
python scripts/schema_diff.py --dataset pg_diff_orders --from-version v1.0.0 --to-version v1.2.0
-> Exit 0, Overall Classification: WARNING, Recommendation: APPROVE WITH WARNING

# Breaking Comparison
python scripts/schema_diff.py --dataset pg_diff_orders --from-version v1.0.0 --to-version v2.0.0
-> Exit 1, Overall Classification: BREAKING, Recommendation: BLOCK MERGE
```

### HTTP REST API Endpoints Verified:
- `POST /schema/diff` with valid version pair: HTTP 200 OK
- `POST /schema/diff` with unknown dataset: HTTP 404 Not Found
- `POST /schema/diff` with unknown version: HTTP 404 Not Found
- `POST /schema/diff` with same version (`v1.0.0` vs `v1.0.0`): HTTP 400 Bad Request
- `POST /schema/diff` with malformed payload: HTTP 422 Unprocessable Content
- `GET /metrics`: Exports `schema_diff_requests_total`, `schema_diff_breaking_total`, `schema_diff_warning_total`, `schema_diff_safe_total`, and `schema_diff_duration_seconds`.
