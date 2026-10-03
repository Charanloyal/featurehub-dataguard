"""
DataGuard Referential Integrity Validation Engine.
Evaluates cross-dataset foreign key relationships and flags orphaned records.
"""

import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Callable

from dataguard.quality.models import (
    QualityCheckResult,
    QualityStatus,
    QualitySeverity
)


class ReferentialIntegrityValidator:
    """
    Validates foreign key relationships between datasets.
    Ensures child records reference valid parent entity primary keys.
    """

    # Catalog of standard production entity relationships
    # child_dataset -> list of (child_fk_column, parent_dataset, parent_pk_column)
    FOREIGN_KEY_RELATIONSHIPS: Dict[str, List[Tuple[str, str, str]]] = {
        "orders": [
            ("customer_id", "customers", "customer_id")
        ],
        "order_items": [
            ("order_id", "orders", "order_id"),
            ("product_id", "products", "product_id")
        ],
        "payments": [
            ("order_id", "orders", "order_id")
        ],
        "accounts": [
            ("customer_id", "customers", "customer_id")
        ],
        "transactions": [
            ("customer_id", "customers", "customer_id"),
            ("account_id", "accounts", "account_id"),
            ("merchant_id", "merchants", "merchant_id")
        ],
        "fraud_events": [
            ("transaction_id", "transactions", "transaction_id")
        ],
        "user_sessions": [
            ("customer_id", "customers", "customer_id")
        ],
        "card_tokens": [
            ("customer_id", "customers", "customer_id")
        ],
        "chargeback_disputes": [
            ("transaction_id", "transactions", "transaction_id")
        ]
    }

    @classmethod
    def get_relationships(cls, dataset_name: str) -> List[Tuple[str, str, str]]:
        """Returns list of foreign key specifications for a dataset: (fk_col, parent_ds, parent_pk_col)."""
        return cls.FOREIGN_KEY_RELATIONSHIPS.get(dataset_name, [])

    @classmethod
    def validate_referential_integrity(
        cls,
        run_id: str,
        child_dataset: str,
        child_df: pd.DataFrame,
        parent_dataset: str,
        parent_df: pd.DataFrame,
        child_fk_col: str,
        parent_pk_col: str,
        pipeline: str = "default_pipeline"
    ) -> QualityCheckResult:
        """
        Validates that all non-null values in child_df[child_fk_col] exist in parent_df[parent_pk_col].
        """
        check_name = f"foreign_key_{child_dataset}_{child_fk_col}_in_{parent_dataset}_{parent_pk_col}"

        if child_fk_col not in child_df.columns:
            return QualityCheckResult(
                run_id=run_id,
                dataset=child_dataset,
                check_name=check_name,
                column=child_fk_col,
                expectation_type="expect_column_values_to_match_foreign_key",
                status=QualityStatus.FAIL,
                severity=QualitySeverity.CRITICAL,
                observed_value="Column missing",
                expected_value=f"Column '{child_fk_col}' exists in '{child_dataset}'",
                success=False,
                pipeline=pipeline,
                details={"error": f"Child column '{child_fk_col}' not found in dataframe."}
            )

        if parent_pk_col not in parent_df.columns:
            return QualityCheckResult(
                run_id=run_id,
                dataset=child_dataset,
                check_name=check_name,
                column=child_fk_col,
                expectation_type="expect_column_values_to_match_foreign_key",
                status=QualityStatus.FAIL,
                severity=QualitySeverity.CRITICAL,
                observed_value="Parent PK missing",
                expected_value=f"Column '{parent_pk_col}' exists in '{parent_dataset}'",
                success=False,
                pipeline=pipeline,
                details={"error": f"Parent column '{parent_pk_col}' not found in parent dataframe."}
            )

        child_values = child_df[child_fk_col].dropna()
        if len(child_values) == 0:
            return QualityCheckResult(
                run_id=run_id,
                dataset=child_dataset,
                check_name=check_name,
                column=child_fk_col,
                expectation_type="expect_column_values_to_match_foreign_key",
                status=QualityStatus.PASS,
                severity=QualitySeverity.CRITICAL,
                observed_value="0 child records",
                expected_value="All values exist in parent",
                success=True,
                pipeline=pipeline,
                details={"orphan_count": 0, "total_records": 0}
            )

        parent_keys = set(parent_df[parent_pk_col].dropna().astype(str).unique())
        child_keys = child_values.astype(str)

        is_valid = child_keys.isin(parent_keys)
        orphan_count = int((~is_valid).sum())
        total_count = len(child_keys)
        orphan_percent = round((orphan_count / total_count) * 100.0, 2)

        success = orphan_count == 0
        status = QualityStatus.PASS if success else QualityStatus.FAIL

        orphans_sample = list(child_keys[~is_valid].unique()[:5])

        return QualityCheckResult(
            run_id=run_id,
            dataset=child_dataset,
            check_name=check_name,
            column=child_fk_col,
            expectation_type="expect_column_values_to_match_foreign_key",
            status=status,
            severity=QualitySeverity.CRITICAL,
            observed_value=f"{orphan_count} orphan(s) ({orphan_percent}%)",
            expected_value="0 orphans (100% referential match)",
            success=success,
            pipeline=pipeline,
            details={
                "parent_dataset": parent_dataset,
                "parent_pk_column": parent_pk_col,
                "total_child_records": total_count,
                "orphan_count": orphan_count,
                "orphan_percent": orphan_percent,
                "sample_orphan_keys": orphans_sample
            }
        )
