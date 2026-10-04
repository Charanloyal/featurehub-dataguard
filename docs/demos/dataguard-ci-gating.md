# DataGuard CI/CD Pull Request Gating Demonstration

This guide demonstrates practical usage of DataGuard Phase H CI/CD gating across 5 common operational scenarios.

---

## Scenario 1: Backward-Compatible Evolution (SAFE)

A developer opens a PR adding an optional customer loyalty field:
```yaml
# diff in dataguard/contracts/customers.yaml
+      - name: loyalty_tier
+        type: string
+        nullable: true
+        unique: false
+        description: Optional loyalty tier level
+        allowed_values: ["BRONZE", "SILVER", "GOLD", "PLATINUM"]
```

### CLI Execution
```bash
python scripts/ci_contract_gate.py --files dataguard/contracts/customers.yaml
```

### Output
```text
===========================================================================
DATAGUARD CI/CD SCHEMA COMPATIBILITY & QUALITY GATING
===========================================================================
Base Target Ref : origin/main
Contracts Dir   : dataguard/contracts
Allow Breaking  : False
---------------------------------------------------------------------------
Evaluating 1 contract(s)...

## ✅ DataGuard CI Gate: MERGE APPROVED (SAFE)

> **All contract changes are backward-compatible.** No breaking modifications or quality regressions detected.

### Summary Overview
- **Overall Verdict**: `SAFE`
- **Merge Status**: `ALLOWED`
- **Contracts Evaluated**: `1`
- **Breaking Changes**: `0`
- **Warning Changes**: `0`
- **Safe Changes**: `1`

### Contract Evaluation Breakdown

| Dataset | File | Verdict | Breaking | Warnings | Safe | Quality Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `customers` | `dataguard/contracts/customers.yaml` | ✅ SAFE | 0 | 0 | 1 | 99.2% |

===========================================================================

[CI RESULT: SAFE] MERGE ALLOWED ✅ (Exit Code: 0)
```
**Result**: Exit code `0`. Pull Request CI check passes; merge button remains enabled.

---

## Scenario 2: Potentially Sensitive Change (WARNING)

A developer opens a PR shortening the freshness SLA for payment authorizations:
```yaml
# diff in dataguard/contracts/payments.yaml
- freshness_sla_minutes: 60
+ freshness_sla_minutes: 15
```

### CLI Execution
```bash
python scripts/ci_contract_gate.py --files dataguard/contracts/payments.yaml
```

### Output
```text
## ⚠️ DataGuard CI Gate: REVIEW REQUIRED (WARNING)

> **Contract changes contain potentially sensitive modifications.** Review column constraints and SLA changes before merging.

### Summary Overview
- **Overall Verdict**: `WARNING`
- **Merge Status**: `ALLOWED`
- **Contracts Evaluated**: `1`
- **Breaking Changes**: `0`
- **Warning Changes**: `1`
- **Safe Changes**: `0`

[CI RESULT: WARNING] MERGE ALLOWED ✅ (Exit Code: 0)
```
**Result**: Exit code `0`. Pull Request CI check passes with a warning annotation for team reviewers.

---

## Scenario 3: Breaking Schema Modification (BREAKING)

A developer opens a PR dropping `account_id` and changing `amount` from numeric to string:
```yaml
# diff in dataguard/contracts/transactions.yaml
-      - name: account_id
-        type: string
-        nullable: false
-        unique: false
-        description: Originating account ID
       - name: amount
-        type: numeric
+        type: string
```

### CLI Execution
```bash
python scripts/ci_contract_gate.py --files dataguard/contracts/transactions.yaml
```

### Output
```text
## ❌ DataGuard CI Gate: MERGE BLOCKED (BREAKING CHANGES)

> **PR contains breaking contract changes.** Merging is blocked to prevent downstream pipeline failures and schema mismatch errors.

### Summary Overview
- **Overall Verdict**: `BREAKING`
- **Merge Status**: `BLOCKED`
- **Contracts Evaluated**: `1`
- **Breaking Changes**: `2`
- **Warning Changes**: `0`
- **Safe Changes**: `0`

### Contract Evaluation Breakdown

| Dataset | File | Verdict | Breaking | Warnings | Safe | Quality Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `transactions` | `dataguard/contracts/transactions.yaml` | ❌ BREAKING | 2 | 0 | 0 | 97.8% |

### Detailed Schema Modifications & Remediation

| Dataset | Column | Severity | Change Type | Description | Recommended Action |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `transactions` | `account_id` | 🔴 BREAKING | `COLUMN_REMOVED` | Column 'account_id' was dropped. | Column removal is BREAKING for downstream consumers. Instead of dropping 'account_id', deprecate it first, maintain nullability, or publish a major version (v2.0.0). |
| `transactions` | `amount` | 🔴 BREAKING | `TYPE_CHANGED` | Incompatible type shift: numeric -> string. | Incompatible type shift on 'amount'. Ensure consumer ETL pipelines and schema registries support the new physical type, or use a non-breaking widening type. |

===========================================================================

[CI RESULT: BREAKING] MERGE BLOCKED ❌ (Exit Code: 1)
Please resolve the breaking changes listed above or seek administrative override.
```
**Result**: Exit code `1`. GitHub Actions check **fails**, blocking the PR merge.

---

## Scenario 4: Administrative Override (`--allow-breaking`)

For emergency production fixes where an engineer intentionally requires a breaking change:
```bash
python scripts/ci_contract_gate.py --files dataguard/contracts/transactions.yaml --allow-breaking
```

### Output
```text
Allow Breaking  : True
...
[CI RESULT: BREAKING] MERGE ALLOWED ✅ (Exit Code: 0)
```
**Result**: Exit code `0`. Administrative override permits merge under authorized emergency protocol.

---

## Scenario 5: REST API Programmatic Gating

Evaluate contract compatibility over HTTP:

### Request
```bash
curl -X POST http://localhost:8000/ci/gate \
  -H "Content-Type: application/json" \
  -d '{
    "baseline_contract": { ... },
    "target_contract": { ... },
    "dataset_name": "orders",
    "validate_quality": false
  }'
```

### Response (JSON)
```json
{
  "dataset_name": "orders",
  "file_path": null,
  "contract_valid": true,
  "contract_errors": [],
  "verdict": "BREAKING",
  "can_merge": false,
  "is_breaking": true,
  "changes": [
    {
      "column": "amount",
      "change_type": "COLUMN_REMOVED",
      "severity": "BREAKING",
      "description": "Column 'amount' was dropped.",
      "remediation": "Column removal is BREAKING for downstream consumers..."
    }
  ],
  "breaking_count": 1,
  "warning_count": 0,
  "safe_count": 0,
  "quality_regression_passed": true,
  "quality_score": null,
  "quality_errors": []
}
```
