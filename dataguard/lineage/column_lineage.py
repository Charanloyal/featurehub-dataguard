"""
DataGuard Real Column-Level Lineage Definitions.
Maps transformations and lineage between raw sources, cleaned datasets, and FeatureHub feature stores.
Reflects actual feature computations and validations in the repository.
"""

from typing import List, Dict, Any, Optional
from dataguard.lineage.events import ColumnLineageDatasetFacet, ColumnLineageField, ColumnLineageInputField


# Repository-aligned column transformations
PROJECT_COLUMN_MAPPINGS: List[Dict[str, str]] = [
    # 1. Transactions -> Transactions Clean (Quality Pipeline)
    {
        "source_dataset": "postgres.transactions",
        "source_column": "transaction_id",
        "target_dataset": "transactions_clean",
        "target_column": "transaction_id",
        "transformation": "PASSTHROUGH with uniqueness and null verification",
        "pipeline": "transaction_quality_pipeline"
    },
    {
        "source_dataset": "postgres.transactions",
        "source_column": "amount",
        "target_dataset": "transactions_clean",
        "target_column": "amount",
        "transformation": "CAST(amount AS NUMERIC(12,2)) where amount >= 0.0",
        "pipeline": "transaction_quality_pipeline"
    },
    {
        "source_dataset": "postgres.transactions",
        "source_column": "timestamp",
        "target_dataset": "transactions_clean",
        "target_column": "timestamp",
        "transformation": "CONVERT_TIMEZONE(timestamp, 'UTC') with freshness SLA validation",
        "pipeline": "transaction_quality_pipeline"
    },
    {
        "source_dataset": "postgres.transactions",
        "source_column": "status",
        "target_dataset": "transactions_clean",
        "target_column": "status",
        "transformation": "VALIDATE IN ('SETTLED', 'PENDING', 'FAILED', 'REFUNDED')",
        "pipeline": "transaction_quality_pipeline"
    },

    # 2. Transactions Clean -> Customer Features (Feature Computation)
    {
        "source_dataset": "transactions_clean",
        "source_column": "customer_id",
        "target_dataset": "customer_features",
        "target_column": "customer_id",
        "transformation": "GROUP BY customer_id entity key",
        "pipeline": "feature_compute"
    },
    {
        "source_dataset": "transactions_clean",
        "source_column": "amount",
        "target_dataset": "customer_features",
        "target_column": "cust_txn_amount_sum_30d",
        "transformation": "SUM(amount) over trailing 30d window",
        "pipeline": "feature_compute"
    },
    {
        "source_dataset": "transactions_clean",
        "source_column": "amount",
        "target_dataset": "customer_features",
        "target_column": "cust_txn_amount_avg_30d",
        "transformation": "AVG(amount) over trailing 30d window",
        "pipeline": "feature_compute"
    },
    {
        "source_dataset": "transactions_clean",
        "source_column": "transaction_id",
        "target_dataset": "customer_features",
        "target_column": "cust_txn_count_30d",
        "transformation": "COUNT(transaction_id) over trailing 30d window",
        "pipeline": "feature_compute"
    },
    {
        "source_dataset": "transactions_clean",
        "source_column": "status",
        "target_dataset": "customer_features",
        "target_column": "cust_failed_txns_30d",
        "transformation": "SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) over trailing 30d window",
        "pipeline": "feature_compute"
    },
    {
        "source_dataset": "transactions_clean",
        "source_column": "channel",
        "target_dataset": "customer_features",
        "target_column": "cust_wire_amount_sum_30d",
        "transformation": "SUM(amount WHERE channel='WIRE') over trailing 30d window",
        "pipeline": "feature_compute"
    },
    {
        "source_dataset": "transactions_clean",
        "source_column": "timestamp",
        "target_dataset": "customer_features",
        "target_column": "cust_last_txn_timestamp",
        "transformation": "MAX(timestamp) latest transaction occurrence",
        "pipeline": "feature_compute"
    },

    # 3. Transactions Clean -> Transaction Features
    {
        "source_dataset": "transactions_clean",
        "source_column": "customer_id",
        "target_dataset": "transaction_features",
        "target_column": "customer_id",
        "transformation": "GROUP BY customer_id",
        "pipeline": "feature_compute"
    },
    {
        "source_dataset": "transactions_clean",
        "source_column": "amount",
        "target_dataset": "transaction_features",
        "target_column": "total_amount_24h",
        "transformation": "SUM(amount) over trailing 24h window",
        "pipeline": "feature_compute"
    },
    {
        "source_dataset": "transactions_clean",
        "source_column": "timestamp",
        "target_dataset": "transaction_features",
        "target_column": "last_transaction_time",
        "transformation": "MAX(timestamp) over trailing window",
        "pipeline": "feature_compute"
    },

    # 4. Customers -> Customers Clean -> Customer Features
    {
        "source_dataset": "postgres.customers",
        "source_column": "customer_id",
        "target_dataset": "customers_clean",
        "target_column": "customer_id",
        "transformation": "PASSTHROUGH primary key invariant check",
        "pipeline": "customer_quality_pipeline"
    },
    {
        "source_dataset": "postgres.customers",
        "source_column": "email",
        "target_dataset": "customers_clean",
        "target_column": "email",
        "transformation": "LOWER(TRIM(email)) with email regex validation",
        "pipeline": "customer_quality_pipeline"
    },
    {
        "source_dataset": "customers_clean",
        "source_column": "customer_id",
        "target_dataset": "customer_features",
        "target_column": "customer_id",
        "transformation": "INNER JOIN on customer_id",
        "pipeline": "feature_compute"
    },

    # 5. Customer Features -> Redis Online Store (Materialization)
    {
        "source_dataset": "customer_features",
        "source_column": "cust_txn_amount_sum_30d",
        "target_dataset": "redis.online_features",
        "target_column": "cust_txn_amount_sum_30d",
        "transformation": "HSET customer:{customer_id} cust_txn_amount_sum_30d (Float32)",
        "pipeline": "feature_materialization"
    },
    {
        "source_dataset": "customer_features",
        "source_column": "cust_txn_count_30d",
        "target_dataset": "redis.online_features",
        "target_column": "cust_txn_count_30d",
        "transformation": "HSET customer:{customer_id} cust_txn_count_30d (Int64)",
        "pipeline": "feature_materialization"
    },
    {
        "source_dataset": "customer_features",
        "source_column": "cust_last_txn_timestamp",
        "target_dataset": "redis.online_features",
        "target_column": "cust_last_txn_timestamp",
        "transformation": "HSET customer:{customer_id} cust_last_txn_timestamp (ISO-8601)",
        "pipeline": "feature_materialization"
    }
]


def get_column_mappings_for_pipeline(pipeline: str) -> List[Dict[str, str]]:
    """Returns all declared column transformations for a specific pipeline."""
    return [m for m in PROJECT_COLUMN_MAPPINGS if m["pipeline"] == pipeline]


def get_column_mappings_for_target(target_dataset: str) -> List[Dict[str, str]]:
    """Returns all column transformations contributing to a target dataset."""
    target_clean = target_dataset.lower().replace("postgres.", "")
    return [
        m for m in PROJECT_COLUMN_MAPPINGS 
        if m["target_dataset"].lower().replace("postgres.", "") == target_clean
    ]


def build_column_lineage_facet(target_dataset: str, pipeline: str) -> ColumnLineageDatasetFacet:
    """Builds an OpenLineage ColumnLineageDatasetFacet for a given target dataset and pipeline."""
    mappings = [
        m for m in PROJECT_COLUMN_MAPPINGS 
        if m["target_dataset"] == target_dataset and m["pipeline"] == pipeline
    ]
    fields_dict: Dict[str, ColumnLineageField] = {}
    
    for m in mappings:
        tgt_col = m["target_column"]
        src_ds = m["source_dataset"]
        src_ns = "postgres" if src_ds.startswith("postgres.") else "default"
        src_name = src_ds.replace("postgres.", "")
        
        input_field = ColumnLineageInputField(
            namespace=src_ns,
            name=src_name,
            field=m["source_column"]
        )
        
        if tgt_col in fields_dict:
            fields_dict[tgt_col].inputFields.append(input_field)
        else:
            fields_dict[tgt_col] = ColumnLineageField(
                inputFields=[input_field],
                transformationDescription=m["transformation"],
                transformationType="TRANSFORMATION"
            )
            
    return ColumnLineageDatasetFacet(fields=fields_dict)
