"""
DataGuard Incident Severity Policy.
Defines explicit, deterministic mapping from data quality failures to incident severities.
"""

from typing import Dict, Any, Optional
from dataguard.incidents.models import IncidentSeverity


class IncidentSeverityPolicy:
    """
    Centralized severity policy for all data quality incidents.
    Deterministic rule:
    - CRITICAL: Primary key corruption, referential integrity failures, severe freshness breaches, missing required schema columns.
    - HIGH: Null rate breaches on non-nullable fields, uniqueness failures on secondary columns, severe distribution anomalies.
    - MEDIUM: Moderate freshness delay (WARNING), accepted value set / enum violations, numeric range violations, row count deviations.
    - LOW: Minor threshold or formatting deviations.
    - INFO: Informational checks.
    """

    PRIMARY_KEY_COLUMNS = {
        "order_id",
        "customer_id",
        "account_id",
        "transaction_id",
        "merchant_id",
        "payment_id",
        "item_id",
        "product_id",
        "event_id",
        "entity_id"
    }

    @classmethod
    def determine_severity(
        cls,
        expectation_type: str,
        column: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        observed_value: Optional[str] = None,
        is_primary_key: bool = False
    ) -> IncidentSeverity:
        """Determines the IncidentSeverity for a failed expectation."""
        details = details or {}
        col_lower = (column or "").lower()

        # 1. Critical Category
        # A. Referential Integrity
        if expectation_type == "expect_column_values_to_match_foreign_key":
            return IncidentSeverity.CRITICAL

        # B. Critical schema violation (missing column)
        if expectation_type == "expect_column_to_exist":
            return IncidentSeverity.CRITICAL

        # C. Primary key corruption (uniqueness failure on PK)
        if expectation_type == "expect_column_values_to_be_unique":
            if is_primary_key or col_lower in cls.PRIMARY_KEY_COLUMNS or "id" in col_lower:
                return IncidentSeverity.CRITICAL
            return IncidentSeverity.HIGH

        # D. Freshness SLA evaluations
        if expectation_type == "expect_dataset_freshness_within_sla":
            status_str = str(details.get("status", "")).upper()
            if "STALE" in status_str:
                return IncidentSeverity.CRITICAL
            elif "WARNING" in status_str:
                return IncidentSeverity.MEDIUM
            return IncidentSeverity.CRITICAL

        # 2. High Category
        if expectation_type == "expect_column_values_to_not_be_null":
            return IncidentSeverity.HIGH

        # 3. Medium Category
        if expectation_type in {
            "expect_column_values_to_be_in_set",
            "expect_column_values_to_be_between",
            "expect_table_row_count_to_be_between",
            "expect_table_row_count_to_equal"
        }:
            return IncidentSeverity.MEDIUM

        # Default fallback
        return IncidentSeverity.MEDIUM
