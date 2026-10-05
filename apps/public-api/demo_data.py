"""
Deterministic Public Demo Data Store
Provides verified snapshots of platform metadata, contracts, and sample feature vectors.
Used by Public API in PUBLIC_DEMO mode to guarantee reliable, deterministic recruiter demonstrations
without exposing internal database credentials or risk of external database connection drops.
"""

from typing import Dict, Any, List

DEMO_CUSTOMER_FEATURES: Dict[str, Dict[str, Any]] = {
    "cust_000001": {
        "cust_txn_count_30d": 14,
        "cust_txn_amount_sum_30d": 1845.50,
        "cust_avg_txn_amount_30d": 131.82,
        "cust_max_txn_amount_30d": 420.00,
        "cust_std_txn_amount_30d": 88.40,
        "cust_unique_merchants_30d": 6,
        "cust_unique_categories_30d": 3,
        "cust_weekend_ratio_30d": 0.28,
        "cust_night_owl_ratio_30d": 0.07,
        "cust_failed_txn_count_30d": 0,
        "cust_rapid_fire_count_30d": 0,
        "cust_card_velocity_30d": 1.0,
        "cust_cross_border_ratio_30d": 0.0,
        "cust_online_ratio_30d": 0.85,
        "cust_device_count_30d": 2,
        "cust_ip_country_count_30d": 1,
        "feature_timestamp": "2026-10-04T12:00:00Z"
    },
    "cust_000002": {
        "cust_txn_count_30d": 89,
        "cust_txn_amount_sum_30d": 14250.00,
        "cust_avg_txn_amount_30d": 160.11,
        "cust_max_txn_amount_30d": 2500.00,
        "cust_std_txn_amount_30d": 320.15,
        "cust_unique_merchants_30d": 24,
        "cust_unique_categories_30d": 8,
        "cust_weekend_ratio_30d": 0.45,
        "cust_night_owl_ratio_30d": 0.62,
        "cust_failed_txn_count_30d": 7,
        "cust_rapid_fire_count_30d": 12,
        "cust_card_velocity_30d": 5.4,
        "cust_cross_border_ratio_30d": 0.78,
        "cust_online_ratio_30d": 0.98,
        "cust_device_count_30d": 7,
        "cust_ip_country_count_30d": 5,
        "feature_timestamp": "2026-10-04T12:00:00Z"
    }
}

DEMO_CONTRACTS: List[Dict[str, Any]] = [
    {
        "dataset": "customers",
        "version": "v1.0.0",
        "owner": "customer-risk-team",
        "freshness_sla_minutes": 60,
        "description": "Customer demographic and risk attributes master dataset.",
        "columns_count": 6
    },
    {
        "dataset": "transactions",
        "version": "v1.0.0",
        "owner": "payments-data-team",
        "freshness_sla_minutes": 30,
        "description": "Financial settlement records and credit card authorization streams.",
        "columns_count": 6
    },
    {
        "dataset": "customer_features",
        "version": "v1.0.0",
        "owner": "featurestore-team",
        "freshness_sla_minutes": 120,
        "description": "FeatureHub engineered customer risk and velocity feature vectors.",
        "columns_count": 17
    },
    {
        "dataset": "accounts",
        "version": "v1.0.0",
        "owner": "core-banking-team",
        "freshness_sla_minutes": 180,
        "description": "Deposit and checking account balances and status master table.",
        "columns_count": 5
    },
    {
        "dataset": "merchants",
        "version": "v1.0.0",
        "owner": "merchant-operations-team",
        "freshness_sla_minutes": 1440,
        "description": "Registered merchant accounts, MCC codes, and historical dispute rates.",
        "columns_count": 5
    }
]

DEMO_INCIDENTS: List[Dict[str, Any]] = [
    {
        "incident_id": "inc_demo_001",
        "dataset": "transactions",
        "pipeline_id": "transaction_quality_pipeline",
        "check_name": "expect_column_values_to_be_between",
        "severity": "CRITICAL",
        "status": "OPEN",
        "owner": "payments-data-team",
        "observed_value": -45.0,
        "expected_value": "min: 0.00",
        "error_message": "Negative transaction amounts detected in production settlement feed.",
        "created_at": "2026-10-04T10:15:00Z",
        "age_hours": 2.5
    },
    {
        "incident_id": "inc_demo_002",
        "dataset": "customer_features",
        "pipeline_id": "feature_quality_pipeline",
        "check_name": "expect_column_values_to_not_be_null",
        "severity": "HIGH",
        "status": "ACKNOWLEDGED",
        "owner": "featurestore-team",
        "observed_value": "12 nulls found (1.2%)",
        "expected_value": "0 nulls",
        "error_message": "Null values found in non-nullable feature column 'cust_txn_count_30d'.",
        "created_at": "2026-10-04T08:00:00Z",
        "age_hours": 4.8
    }
]

DEMO_LINEAGE_MAP: Dict[str, Dict[str, Any]] = {
    "customer_features": {
        "dataset": "customer_features",
        "upstream_sources": ["PostgreSQL.public.customers", "PostgreSQL.public.transactions"],
        "downstream_sinks": ["Redis.online_features", "MLInferenceService.fraud_predictor"],
        "pipeline": "feature_quality_pipeline",
        "columns": [
            {
                "target_column": "cust_txn_count_30d",
                "source_columns": ["transactions.txn_id"],
                "transformation": "COUNT(txn_id) OVER 30d sliding window"
            },
            {
                "target_column": "cust_txn_amount_sum_30d",
                "source_columns": ["transactions.amount"],
                "transformation": "SUM(amount) OVER 30d sliding window"
            },
            {
                "target_column": "cust_night_owl_ratio_30d",
                "source_columns": ["transactions.created_at"],
                "transformation": "COUNT(IF hour between 00 and 06) / COUNT(total)"
            }
        ]
    }
}
