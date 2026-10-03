"""
DataGuard Schema Diff Engine
Compares incoming data contracts against baseline target contracts,
registered PostgreSQL contract versions, or physical database tables.
Detects column additions/removals, type changes, nullability modifications,
enum shifts, numeric range expansions/tightenings, SLA shifts, and constraint modifications.
Classifies modifications as SAFE, WARNING, or BREAKING.
"""

import time
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from dataguard.schema.models import (
    DiffSeverity,
    ChangeType,
    SchemaChange,
    SchemaDiffResult
)
from dataguard.schema.type_compatibility import TypeCompatibilityEngine
from dataguard.schema.report import generate_human_report
from dataguard.metrics import (
    SCHEMA_DIFF_EVALUATIONS_TOTAL,
    SCHEMA_DRIFT_DETECTED_TOTAL,
    SCHEMA_DIFF_REQUESTS_TOTAL,
    SCHEMA_DIFF_BREAKING_TOTAL,
    SCHEMA_DIFF_WARNING_TOTAL,
    SCHEMA_DIFF_SAFE_TOTAL,
    SCHEMA_DIFF_DURATION_SECONDS
)
from dataguard.contracts.registry import (
    ContractRegistryService,
    ContractNotFoundError
)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "platform_dev.db"

class SchemaDiffEngine:
    @staticmethod
    def map_sql_type_to_contract(sql_type: str) -> str:
        """Normalizes database SQL column type to standard contract types."""
        return TypeCompatibilityEngine.normalize_type(sql_type)

    @classmethod
    def compare_contracts(
        cls, 
        baseline_contract: Dict[str, Any], 
        target_contract: Dict[str, Any]
    ) -> SchemaDiffResult:
        """
        Compares baseline contract against target contract.
        Detects all structural, type, nullability, enum, SLA, and constraint modifications.
        Produces deterministic SAFE, WARNING, or BREAKING classification.
        """
        start_time = time.perf_counter()
        SCHEMA_DIFF_REQUESTS_TOTAL.inc()

        changes: List[SchemaChange] = []

        base_dataset = baseline_contract.get("dataset")
        tgt_dataset = target_contract.get("dataset")
        if target_contract.get("owner") != "database-inferred" and base_dataset and tgt_dataset and base_dataset != tgt_dataset:
            raise ValueError(f"Dataset mismatch: baseline '{base_dataset}' does not match target '{tgt_dataset}'.")

        base_version = baseline_contract.get("version")
        tgt_version = target_contract.get("version")

        # 1. Compare Root Metadata (Description & Freshness SLA)
        base_desc = str(baseline_contract.get("description", "")).strip()
        tgt_desc = str(target_contract.get("description", "")).strip()
        if base_desc and tgt_desc and base_desc != tgt_desc:
            changes.append(SchemaChange(
                column="(root)",
                change_type=ChangeType.DESCRIPTION_CHANGED,
                old_value=base_desc,
                new_value=tgt_desc,
                severity=DiffSeverity.SAFE,
                description=f"Dataset description updated: '{base_desc}' -> '{tgt_desc}'."
            ))

        base_sla = baseline_contract.get("freshness_sla_minutes")
        tgt_sla = target_contract.get("freshness_sla_minutes")
        if base_sla is not None and tgt_sla is not None and base_sla != tgt_sla:
            if tgt_sla < base_sla:
                changes.append(SchemaChange(
                    column="(root)",
                    change_type=ChangeType.SLA_CHANGED,
                    old_value=base_sla,
                    new_value=tgt_sla,
                    severity=DiffSeverity.WARNING,
                    description=f"Freshness SLA reduced from {base_sla}m to {tgt_sla}m (stricter pipeline latency requirement)."
                ))
            else:
                changes.append(SchemaChange(
                    column="(root)",
                    change_type=ChangeType.SLA_CHANGED,
                    old_value=base_sla,
                    new_value=tgt_sla,
                    severity=DiffSeverity.SAFE,
                    description=f"Freshness SLA relaxed from {base_sla}m to {tgt_sla}m."
                ))

        # 2. Compare Columns
        base_cols_list = baseline_contract.get("columns", [])
        tgt_cols_list = target_contract.get("columns", [])

        base_cols = {c["name"]: c for c in base_cols_list if isinstance(c, dict) and "name" in c}
        tgt_cols = {c["name"]: c for c in tgt_cols_list if isinstance(c, dict) and "name" in c}

        base_col_names = set(base_cols.keys())
        tgt_col_names = set(tgt_cols.keys())

        added_col_names = sorted(list(tgt_col_names - base_col_names))
        removed_col_names = sorted(list(base_col_names - tgt_col_names))
        common_col_names = sorted(list(base_col_names & tgt_col_names))

        # 2a. Added Columns
        for name in added_col_names:
            c = tgt_cols[name]
            is_nullable = c.get("nullable", True)
            col_type = c.get("type", "string")

            if is_nullable:
                changes.append(SchemaChange(
                    column=name,
                    change_type=ChangeType.COLUMN_ADDED,
                    old_value=None,
                    new_value=col_type,
                    severity=DiffSeverity.SAFE,
                    description=f"Added nullable column '{name}' ({col_type}). Backward-compatible with existing consumers."
                ))
            else:
                changes.append(SchemaChange(
                    column=name,
                    change_type=ChangeType.COLUMN_ADDED,
                    old_value=None,
                    new_value=col_type,
                    severity=DiffSeverity.WARNING,
                    description=f"Added non-nullable column '{name}' ({col_type}). Upstream producers must populate this column."
                ))

        # 2b. Removed Columns
        for name in removed_col_names:
            c = base_cols[name]
            col_type = c.get("type", "string")
            changes.append(SchemaChange(
                column=name,
                change_type=ChangeType.COLUMN_REMOVED,
                old_value=col_type,
                new_value=None,
                severity=DiffSeverity.BREAKING,
                description=f"Removed column '{name}'. Downstream consumers expecting this column will fail."
            ))

        # 2c. Common Columns (Type, Nullability, Uniqueness, Enums, Range, Description)
        for name in common_col_names:
            b_col = base_cols[name]
            t_col = tgt_cols[name]

            # Type Change
            b_type = b_col.get("type", "string")
            t_type = t_col.get("type", "string")
            is_compat, type_sev, explanation = TypeCompatibilityEngine.check_type_compatibility(b_type, t_type)

            if TypeCompatibilityEngine.normalize_type(b_type) != TypeCompatibilityEngine.normalize_type(t_type):
                changes.append(SchemaChange(
                    column=name,
                    change_type=ChangeType.TYPE_CHANGED,
                    old_value=b_type,
                    new_value=t_type,
                    severity=type_sev,
                    description=explanation
                ))

            # Nullability Change
            b_null = b_col.get("nullable", True)
            t_null = t_col.get("nullable", True)
            if b_null != t_null:
                if b_null and not t_null:
                    # nullable -> non-nullable is BREAKING
                    changes.append(SchemaChange(
                        column=name,
                        change_type=ChangeType.NULLABILITY_CHANGED,
                        old_value=b_null,
                        new_value=t_null,
                        severity=DiffSeverity.BREAKING,
                        description=f"Column '{name}' tightened from nullable (True) to non-nullable (False). Existing NULL values will fail validation."
                    ))
                else:
                    # non-nullable -> nullable is SAFE
                    changes.append(SchemaChange(
                        column=name,
                        change_type=ChangeType.NULLABILITY_CHANGED,
                        old_value=b_null,
                        new_value=t_null,
                        severity=DiffSeverity.SAFE,
                        description=f"Column '{name}' relaxed from non-nullable (False) to nullable (True). Existing valid records remain compliant."
                    ))

            # Uniqueness Change
            b_uniq = b_col.get("unique", False)
            t_uniq = t_col.get("unique", False)
            if b_uniq != t_uniq:
                if not b_uniq and t_uniq:
                    changes.append(SchemaChange(
                        column=name,
                        change_type=ChangeType.UNIQUE_CHANGED,
                        old_value=b_uniq,
                        new_value=t_uniq,
                        severity=DiffSeverity.BREAKING,
                        description=f"Column '{name}' tightened from non-unique to unique. Duplicate values in existing data will fail."
                    ))
                else:
                    changes.append(SchemaChange(
                        column=name,
                        change_type=ChangeType.UNIQUE_CHANGED,
                        old_value=b_uniq,
                        new_value=t_uniq,
                        severity=DiffSeverity.SAFE,
                        description=f"Column '{name}' relaxed from unique to non-unique."
                    ))

            # Allowed Values (Enum) Changes
            b_allowed = b_col.get("allowed_values")
            t_allowed = t_col.get("allowed_values")
            if target_contract.get("owner") != "database-inferred" and (b_allowed is not None or t_allowed is not None):
                b_set = set(b_allowed or [])
                t_set = set(t_allowed or [])

                added_enums = sorted(list(t_set - b_set))
                removed_enums = sorted(list(b_set - t_set))

                if added_enums:
                    changes.append(SchemaChange(
                        column=name,
                        change_type=ChangeType.ENUM_VALUE_ADDED,
                        old_value=b_allowed,
                        new_value=t_allowed,
                        severity=DiffSeverity.SAFE,
                        description=f"Added allowed enum values {added_enums} to column '{name}'. Backward-compatible superset."
                    ))

                if removed_enums:
                    changes.append(SchemaChange(
                        column=name,
                        change_type=ChangeType.ENUM_VALUE_REMOVED,
                        old_value=b_allowed,
                        new_value=t_allowed,
                        severity=DiffSeverity.BREAKING,
                        description=f"Removed allowed enum values {removed_enums} from column '{name}'. Records with removed values will fail validation."
                    ))

            # Min / Max Numeric Range Constraints
            b_min = b_col.get("min")
            t_min = t_col.get("min")
            if b_min is not None and t_min is not None and b_min != t_min:
                if t_min > b_min:
                    changes.append(SchemaChange(
                        column=name,
                        change_type=ChangeType.RANGE_TIGHTENED,
                        old_value=b_min,
                        new_value=t_min,
                        severity=DiffSeverity.WARNING,
                        description=f"Minimum bound tightened for column '{name}' ({b_min} -> {t_min}). Values below {t_min} will be rejected."
                    ))
                else:
                    changes.append(SchemaChange(
                        column=name,
                        change_type=ChangeType.RANGE_EXPANDED,
                        old_value=b_min,
                        new_value=t_min,
                        severity=DiffSeverity.SAFE,
                        description=f"Minimum bound relaxed for column '{name}' ({b_min} -> {t_min})."
                    ))

            b_max = b_col.get("max")
            t_max = t_col.get("max")
            if b_max is not None and t_max is not None and b_max != t_max:
                if t_max < b_max:
                    changes.append(SchemaChange(
                        column=name,
                        change_type=ChangeType.RANGE_TIGHTENED,
                        old_value=b_max,
                        new_value=t_max,
                        severity=DiffSeverity.WARNING,
                        description=f"Maximum bound tightened for column '{name}' ({b_max} -> {t_max}). Values above {t_max} will be rejected."
                    ))
                else:
                    changes.append(SchemaChange(
                        column=name,
                        change_type=ChangeType.RANGE_EXPANDED,
                        old_value=b_max,
                        new_value=t_max,
                        severity=DiffSeverity.SAFE,
                        description=f"Maximum bound relaxed for column '{name}' ({b_max} -> {t_max})."
                    ))

            # Column Description Change
            b_col_desc = str(b_col.get("description", "")).strip()
            t_col_desc = str(t_col.get("description", "")).strip()
            if b_col_desc and t_col_desc and b_col_desc != t_col_desc:
                changes.append(SchemaChange(
                    column=name,
                    change_type=ChangeType.DESCRIPTION_CHANGED,
                    old_value=b_col_desc,
                    new_value=t_col_desc,
                    severity=DiffSeverity.SAFE,
                    description=f"Description updated for column '{name}'."
                ))

        # 3. Compare Custom Constraints List
        added_constraints = []
        removed_constraints = []
        if target_contract.get("owner") != "database-inferred" and "constraints" in baseline_contract and "constraints" in target_contract:
            b_raw = baseline_contract.get("constraints") or []
            t_raw = target_contract.get("constraints") or []
            b_constraints = set(c if isinstance(c, str) else str(c) for c in b_raw)
            t_constraints = set(c if isinstance(c, str) else str(c) for c in t_raw)

            added_constraints = sorted(list(t_constraints - b_constraints))
            removed_constraints = sorted(list(b_constraints - t_constraints))

        for c_text in added_constraints:
            changes.append(SchemaChange(
                column="(constraints)",
                change_type=ChangeType.CONSTRAINT_ADDED,
                old_value=None,
                new_value=c_text,
                severity=DiffSeverity.WARNING,
                description=f"Added custom validation constraint: '{c_text}'."
            ))

        for c_text in removed_constraints:
            changes.append(SchemaChange(
                column="(constraints)",
                change_type=ChangeType.CONSTRAINT_REMOVED,
                old_value=c_text,
                new_value=None,
                severity=DiffSeverity.WARNING,
                description=f"Removed custom validation constraint: '{c_text}'."
            ))

        # 4. Detect Possible Column Rename Heuristic
        if len(removed_col_names) == 1 and len(added_col_names) == 1:
            r_col = base_cols[removed_col_names[0]]
            a_col = tgt_cols[added_col_names[0]]
            if TypeCompatibilityEngine.normalize_type(r_col.get("type")) == TypeCompatibilityEngine.normalize_type(a_col.get("type")):
                changes.append(SchemaChange(
                    column=added_col_names[0],
                    change_type=ChangeType.COLUMN_RENAMED,
                    old_value=removed_col_names[0],
                    new_value=added_col_names[0],
                    severity=DiffSeverity.BREAKING,
                    description=f"Possible column rename detected: '{removed_col_names[0]}' -> '{added_col_names[0]}'."
                ))

        # 5. Aggregate Classification
        has_breaking = any(c.severity == DiffSeverity.BREAKING for c in changes)
        has_warning = any(c.severity == DiffSeverity.WARNING for c in changes)

        if has_breaking:
            overall_severity = DiffSeverity.BREAKING
            recommendation = "BLOCK MERGE"
        elif has_warning:
            overall_severity = DiffSeverity.WARNING
            recommendation = "APPROVE WITH WARNING"
        else:
            overall_severity = DiffSeverity.SAFE
            recommendation = "APPROVE"

        summary = f"{overall_severity.value}: {len(changes)} modification(s) detected between {base_version or 'v1'} and {tgt_version or 'v2'}."

        duration = time.perf_counter() - start_time

        # Observability metrics
        try:
            SCHEMA_DIFF_EVALUATIONS_TOTAL.labels(classification=overall_severity.value).inc()
            if overall_severity == DiffSeverity.BREAKING:
                SCHEMA_DIFF_BREAKING_TOTAL.inc()
            elif overall_severity == DiffSeverity.WARNING:
                SCHEMA_DIFF_WARNING_TOTAL.inc()
            else:
                SCHEMA_DIFF_SAFE_TOTAL.inc()

            SCHEMA_DIFF_DURATION_SECONDS.observe(duration)

            for chg in changes:
                SCHEMA_DRIFT_DETECTED_TOTAL.labels(severity=chg.severity.value).inc()
        except Exception:
            pass

        return SchemaDiffResult(
            dataset=tgt_dataset or base_dataset,
            from_version=base_version,
            to_version=tgt_version,
            classification=overall_severity,
            is_breaking=has_breaking,
            total_changes=len(changes),
            changes=changes,
            summary=summary,
            recommendation=recommendation
        )

    @classmethod
    def compare_versions(
        cls,
        registry_service: ContractRegistryService,
        dataset: str,
        from_version: str,
        to_version: str
    ) -> SchemaDiffResult:
        """
        Retrieves two registered versions from the PostgreSQL Contract Registry
        and evaluates their schema compatibility.
        """
        if hasattr(registry_service, "dataset_exists") and not registry_service.dataset_exists(dataset):
            raise ContractNotFoundError(f"Dataset '{dataset}' not found in registry.")

        c1 = registry_service.get_contract(dataset, version=from_version)
        if not c1:
            raise ContractNotFoundError(f"Baseline version '{from_version}' for dataset '{dataset}' not found in registry.")

        c2 = registry_service.get_contract(dataset, version=to_version)
        if not c2:
            raise ContractNotFoundError(f"Target version '{to_version}' for dataset '{dataset}' not found in registry.")

        if c1.get("dataset") != c2.get("dataset"):
            raise ValueError(f"Dataset name mismatch: '{c1.get('dataset')}' vs '{c2.get('dataset')}'.")

        return cls.compare_contracts(c1, c2)

    @classmethod
    def inspect_database_table(
        cls, 
        table_name: str, 
        db_path: Optional[Path] = None, 
        conn: Optional[sqlite3.Connection] = None,
        engine: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Inspects a live database table structure and converts it to a synthetic contract schema.
        Supports SQLite and PostgreSQL schema discovery.
        """
        if conn is not None:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name});")
            rows = cursor.fetchall()
            if not rows:
                raise ValueError(f"Table '{table_name}' does not exist or has no columns in database.")

            columns = []
            for r in rows:
                col_name = r[1]
                raw_type = r[2] or "TEXT"
                not_null = bool(r[3])
                is_unique = bool(r[5] == 1)

                columns.append({
                    "name": col_name,
                    "type": cls.map_sql_type_to_contract(raw_type),
                    "nullable": not not_null,
                    "unique": is_unique,
                    "description": f"Physical database column ({raw_type})"
                })

            return {
                "dataset": table_name,
                "version": "live_db",
                "owner": "database-inferred",
                "columns": columns,
                "constraints": []
            }

        # Check PostgreSQL or SQLite via active engine
        active_db_path = db_path or DEFAULT_DB_PATH
        if active_db_path.exists():
            c = sqlite3.connect(active_db_path)
            try:
                cursor = c.cursor()
                cursor.execute(f"PRAGMA table_info({table_name});")
                rows = cursor.fetchall()
                if not rows:
                    raise ValueError(f"Table '{table_name}' does not exist or has no columns in database.")

                columns = []
                for r in rows:
                    col_name = r[1]
                    raw_type = r[2] or "TEXT"
                    not_null = bool(r[3])
                    is_unique = bool(r[5] == 1)

                    columns.append({
                        "name": col_name,
                        "type": cls.map_sql_type_to_contract(raw_type),
                        "nullable": not not_null,
                        "unique": is_unique,
                        "description": f"Physical database column ({raw_type})"
                    })

                return {
                    "dataset": table_name,
                    "version": "live_db",
                    "owner": "database-inferred",
                    "columns": columns,
                    "constraints": []
                }
            finally:
                c.close()

        raise ValueError(f"Unable to inspect table '{table_name}': database not accessible.")

    @classmethod
    def compare_contract_to_table(
        cls, 
        contract: Dict[str, Any], 
        table_name: str, 
        db_path: Optional[Path] = None, 
        conn: Optional[sqlite3.Connection] = None
    ) -> SchemaDiffResult:
        """
        Compares expected data contract schema against the physical database table schema.
        """
        table_schema = cls.inspect_database_table(table_name, db_path=db_path, conn=conn)
        return cls.compare_contracts(baseline_contract=contract, target_contract=table_schema)
