# DataGuard Schema Diff & Compatibility Engine Architecture

## Overview
The DataGuard Schema Diff & Compatibility Engine provides deterministic schema drift detection and backward-compatibility classification for production data contracts. It compares either two versions of a contract stored in the PostgreSQL Contract Registry or ad-hoc YAML definitions, classifying detected modifications into **`SAFE`**, **`WARNING`**, or **`BREAKING`** tiers with automated CI/CD gating recommendations (`APPROVE`, `APPROVE WITH WARNING`, or `BLOCK MERGE`).

---

## 1. Comparison Model

The schema diff engine evaluates contract state across five dimensions:
1. **Root Metadata & SLAs**: Dataset description and `freshness_sla_minutes`.
2. **Column Set Evolution**: Columns added or removed, with column rename heuristics.
3. **Data Type Compatibility**: Deep domain and precision evaluation (widening vs narrowing).
4. **Column Constraints**: Nullability shifts, uniqueness constraints, enum allowed values, and numeric ranges (`min`/`max`).
5. **Table-level Constraints**: Relational check constraints and table invariants.

The comparison yields a structured `SchemaDiffResult` containing:
- `dataset`: Target dataset identifier
- `from_version`: Baseline version
- `to_version`: Target version
- `classification`: Highest severity across all changes (`SAFE`, `WARNING`, or `BREAKING`)
- `is_breaking`: Boolean flag indicating if any change broke backward-compatibility
- `total_changes`: Total modifications identified
- `changes`: Detailed array of `SchemaChange` objects
- `recommendation`: Automated gate decision (`BLOCK MERGE`, `APPROVE WITH WARNING`, or `APPROVE`)

---

## 2. Compatibility Policy & Severity Tiers

The engine implements a deterministic 3-tier severity matrix:

### 🟢 SAFE
Modifications that are completely backward-compatible with downstream consumer queries and existing ingestion pipelines.
- **Adding a nullable column**: Downstream consumers will simply ignore it or receive NULLs.
- **Updating dataset or column descriptions**: Pure metadata documentation changes.
- **Expanding numeric maximum or reducing minimum**: `min` relaxed (e.g. `0.0` -> `-5.0`) or `max` increased (e.g. `10,000` -> `50,000`).
- **Adding allowed enum values**: Expanding allowed state set (e.g. `['pending', 'paid']` -> `['pending', 'paid', 'refunded']`).
- **Relaxing non-nullable column to nullable**: `nullable: false` -> `nullable: true`. Existing non-null records remain fully compliant.
- **Relaxing freshness SLA**: `freshness_sla_minutes` increased (e.g. `60m` -> `120m`).
- **Safe type widening**: Promoting `integer` -> `bigint`, `integer` -> `numeric`, or `float` -> `numeric`.

### 🟡 WARNING
Modifications that alter contract invariants in a way that requires upstream producers or downstream consumers to adjust, but does not immediately invalidate valid existing records.
- **Adding a non-nullable column**: Requires upstream producers to supply a non-null value immediately.
- **Tightening freshness SLA**: `freshness_sla_minutes` reduced (e.g. `60m` -> `30m`). Pipelines must guarantee lower latency.
- **Tightening numeric bounds**: `min` increased or `max` decreased. New records may be rejected by stricter filters.
- **Adding or modifying custom check constraints**: New table validation rules.

### 🔴 BREAKING
Modifications that break consumer queries, truncate data, or invalidate existing valid records.
- **Removing an existing column**: Downstream queries referencing the deleted column will fail with SQL syntax/projection errors.
- **Incompatible type change**: Cross-domain changes (e.g. `integer` -> `string`, `string` -> `integer`, `boolean` -> `string`).
- **Narrowing type conversion**: Converting `float` -> `integer` (truncates decimals) or `bigint` -> `integer` (causes integer overflow).
- **Tightening nullability**: `nullable: true` -> `nullable: false`. Existing NULL rows in the dataset immediately fail validation.
- **Removing an allowed enum value**: Values previously valid (e.g. removing `paid`) are rejected.
- **Tightening uniqueness**: `unique: false` -> `unique: true`. Existing duplicate keys violate constraint.
- **Column renames**: Detected via rename heuristic (simultaneous 1-column drop and 1-column add with identical type).

---

## 3. Type Compatibility Rules

Implemented in `dataguard.schema.type_compatibility.TypeCompatibilityEngine`:

| Old Type | New Type | Severity | Rationale |
| :--- | :--- | :--- | :--- |
| `integer` | `bigint` | **SAFE** | Safe widening: 64-bit int accommodates all 32-bit values without precision loss. |
| `integer` | `numeric` | **SAFE** | Safe widening: Arbitrary precision numeric accommodates all integers. |
| `float` | `numeric` | **SAFE** | Safe widening: Decimal numbers fit into numeric representations. |
| `bigint` | `integer` | **BREAKING** | Narrowing conversion: Values exceeding 2^31 - 1 cause overflow errors. |
| `float` | `integer` | **BREAKING** | Narrowing conversion: Fractional precision is truncated. |
| `integer` | `string` | **BREAKING** | Incompatible domain: Arithmetic operations and downstream numeric aggregations will fail. |
| `string` | `integer` | **BREAKING** | Incompatible domain: Arbitrary text strings cannot be cast to integer. |
| `boolean` | `string` | **BREAKING** | Incompatible domain: Boolean logic and type expectations break. |

---

## 4. Nullability & Constraint Rules

1. **Nullability Shifts**:
   - `nullable: true` -> `nullable: false`: **`BREAKING`**. Upstream systems may produce null values that cause immediate pipeline failures.
   - `nullable: false` -> `nullable: true`: **`SAFE`**. Consumers expecting non-null data might receive NULL, but historical producer data remains compliant.
2. **Enum Drift**:
   - Added enum items: **`SAFE`**. Extends domain without rejecting existing states.
   - Removed enum items: **`BREAKING`**. Valid historical records bearing removed values will fail validation.
3. **Range Constraints**:
   - Relaxed bounds (`min` lower, `max` higher): **`SAFE`**.
   - Tightened bounds (`min` higher, `max` lower): **`WARNING`**.

---

## 5. API Endpoints

### `POST /schema/diff`
Supports two execution modes:

#### Mode 1: Registry-backed Comparison
```http
POST /schema/diff HTTP/1.1
Content-Type: application/json

{
  "dataset": "orders",
  "from_version": "v1.0.0",
  "to_version": "v1.1.0"
}
```

#### Mode 2: Direct YAML/JSON Payload Comparison
```http
POST /schema/diff HTTP/1.1
Content-Type: application/json

{
  "baseline_contract": { ... },
  "target_contract": { ... }
}
```

#### Response Example
```json
{
  "dataset": "orders",
  "from_version": "v1.0.0",
  "to_version": "v1.1.0",
  "classification": "SAFE",
  "is_breaking": false,
  "total_changes": 2,
  "changes": [
    {
      "column": "customer_tier",
      "change_type": "COLUMN_ADDED",
      "old_value": null,
      "new_value": "string",
      "severity": "SAFE",
      "description": "Added nullable column 'customer_tier' (string). Backward-compatible with existing consumers."
    }
  ],
  "summary": "SAFE: 2 modification(s) detected between v1.0.0 and v1.1.0.",
  "recommendation": "APPROVE"
}
```

---

## 6. CLI Usage

Command: `scripts/schema_diff.py`

### Comparing PostgreSQL Contract Registry Versions
```bash
python scripts/schema_diff.py --dataset orders --from-version v1.0.0 --to-version v1.1.0
```

### Comparing Local YAML Contract Files
```bash
python scripts/schema_diff.py --file1 dataguard/tests/fixtures/schema_v1.yaml --file2 dataguard/tests/fixtures/schema_breaking.yaml
```

### CLI Output Format
```text
Dataset: orders
From: v1.0.0
To: v2.0.0

Changes:
~ (root) [DESCRIPTION_CHANGED] [SAFE] - Dataset description updated.
- notes [REMOVED] [BREAKING] - Removed column 'notes'. Downstream consumers expecting this column will fail.
~ customer_id [TYPE_CHANGED] [BREAKING] - Incompatible cross-domain type change: 'integer' -> 'string'.

Overall Classification:
BREAKING

Recommendation: BLOCK MERGE
```

### CI/CD Integration & Exit Codes
- Exit `0`: Classification is `SAFE` or `WARNING`.
- Exit `1`: Classification is `BREAKING` (or `WARNING` if `--strict` flag is passed).

---

## 7. Performance Benchmark Methodology

Evaluated using `scripts/benchmark_schema_diff.py` across 100 runs per scale with 10 warmup executions:

| Column Count | p50 Latency | p95 Latency | p99 Latency | Mean Latency | Changes Detected |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **10 columns** | **0.067 ms** | 0.181 ms | 0.244 ms | 0.103 ms | 4 |
| **50 columns** | **0.195 ms** | 0.305 ms | 0.334 ms | 0.206 ms | 9 |
| **100 columns** | **0.372 ms** | 0.419 ms | 0.525 ms | 0.382 ms | 16 |
| **250 columns** | **0.877 ms** | 1.479 ms | 1.617 ms | 0.952 ms | 39 |

Even large-scale contracts with 250 columns evaluate in under **1 millisecond** (p50: 0.88 ms), providing negligible latency for pre-commit hooks and CI pipelines.
