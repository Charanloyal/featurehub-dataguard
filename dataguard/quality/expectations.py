"""
DataGuard Contract-to-Expectation Mapping Layer.
Translates DataGuard YAML / dictionary data contracts into Great Expectations suites.
Source of truth is always the DataGuard contract specification.
"""

import uuid
from typing import Dict, Any, List, Optional, Tuple
import great_expectations as gx
from great_expectations.expectations import (
    ExpectColumnToExist,
    ExpectColumnValuesToNotBeNull,
    ExpectColumnValuesToBeUnique,
    ExpectColumnValuesToBeInSet,
    ExpectColumnValuesToBeBetween,
    ExpectTableRowCountToBeBetween,
)

from dataguard.quality.models import QualitySeverity


class ContractExpectationBuilder:
    """
    Constructs a Great Expectations ExpectationSuite directly from a DataGuard contract.
    Preserves severity metadata, threshold configs, and relational constraints.
    """

    @classmethod
    def get_expectation_severity(cls, exp_type: str, col_meta: Optional[Dict[str, Any]] = None) -> QualitySeverity:
        """Determines the severity of a check based on expectation category and column semantics."""
        if exp_type == "expect_column_to_exist":
            return QualitySeverity.CRITICAL
        elif exp_type in {"expect_column_values_to_not_be_null", "expect_column_values_to_be_unique"}:
            return QualitySeverity.HIGH
        elif exp_type in {"expect_table_row_count_to_be_between", "expect_table_row_count_to_equal"}:
            return QualitySeverity.HIGH
        elif exp_type in {"expect_column_values_to_be_in_set", "expect_column_values_to_be_between"}:
            return QualitySeverity.MEDIUM
        return QualitySeverity.MEDIUM

    @classmethod
    def build_suite_for_contract(
        cls,
        context: Any,
        contract: Dict[str, Any],
        suite_name: Optional[str] = None
    ) -> Tuple[Any, Dict[str, QualitySeverity]]:
        """
        Builds and registers an ExpectationSuite in the given GX DataContext.
        Returns (suite, expectation_severities_map).
        """
        dataset_name = contract.get("dataset", "unknown_dataset")
        version = contract.get("version", "v1.0.0")
        name = suite_name or f"suite_{dataset_name}_{version}_{uuid.uuid4().hex[:6]}"

        suite = context.suites.add(gx.ExpectationSuite(name=name))
        severity_map: Dict[str, QualitySeverity] = {}

        # 1. Table-level Constraints: Row Count
        constraints = contract.get("constraints", {})
        min_rows = None
        if isinstance(constraints, dict):
            min_rows = constraints.get("min_rows")
        elif isinstance(constraints, list):
            for c in constraints:
                if isinstance(c, dict) and "min_rows" in c:
                    min_rows = c["min_rows"]

        if min_rows is not None and int(min_rows) > 0:
            exp_row_count = ExpectTableRowCountToBeBetween(min_value=int(min_rows))
            suite.add_expectation(exp_row_count)
            severity_map["expect_table_row_count_to_be_between:(table)"] = QualitySeverity.HIGH
        else:
            # Default safeguard: dataset should have at least 1 record
            exp_row_count = ExpectTableRowCountToBeBetween(min_value=1)
            suite.add_expectation(exp_row_count)
            severity_map["expect_table_row_count_to_be_between:(table)"] = QualitySeverity.HIGH

        # 2. Column-level Invariants
        columns = contract.get("columns", [])
        for col in columns:
            col_name = col.get("name")
            if not col_name:
                continue

            # a. Column existence check
            exp_exist = ExpectColumnToExist(column=col_name)
            suite.add_expectation(exp_exist)
            severity_map[f"expect_column_to_exist:{col_name}"] = QualitySeverity.CRITICAL

            # b. Not-Null constraint
            is_nullable = col.get("nullable", True)
            if not is_nullable:
                exp_not_null = ExpectColumnValuesToNotBeNull(column=col_name)
                suite.add_expectation(exp_not_null)
                severity_map[f"expect_column_values_to_not_be_null:{col_name}"] = QualitySeverity.HIGH

            # c. Uniqueness constraint
            is_unique = col.get("unique", False)
            if is_unique:
                exp_unique = ExpectColumnValuesToBeUnique(column=col_name)
                suite.add_expectation(exp_unique)
                severity_map[f"expect_column_values_to_be_unique:{col_name}"] = QualitySeverity.HIGH

            # d. Allowed Enum Values
            allowed_values = col.get("allowed_values")
            if allowed_values and isinstance(allowed_values, list) and len(allowed_values) > 0:
                exp_in_set = ExpectColumnValuesToBeInSet(column=col_name, value_set=allowed_values)
                suite.add_expectation(exp_in_set)
                severity_map[f"expect_column_values_to_be_in_set:{col_name}"] = QualitySeverity.MEDIUM

            # e. Numeric Bounds (min / max)
            min_val = col.get("min")
            max_val = col.get("max")
            if min_val is not None or max_val is not None:
                exp_between = ExpectColumnValuesToBeBetween(
                    column=col_name,
                    min_value=float(min_val) if min_val is not None else None,
                    max_value=float(max_val) if max_val is not None else None
                )
                suite.add_expectation(exp_between)
                severity_map[f"expect_column_values_to_be_between:{col_name}"] = QualitySeverity.MEDIUM

        return suite, severity_map
