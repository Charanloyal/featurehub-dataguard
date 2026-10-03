"""
DataGuard Pipeline Catalog & Registry (Phase G).
Maintains standard definitions for 25+ data pipelines across the platform.
Provides automated registration into PostgreSQL pipeline_metadata.
"""

from typing import List, Dict, Optional, Any
from dataguard.pipelines.models import PipelineConfig, PipelineStatus
from dataguard.pipelines.repository import PipelineRepository


# Predefined configurations across all 25+ platform contracts
STANDARD_PIPELINES: List[Dict[str, Any]] = [
    # Core Primary Pipelines
    {
        "pipeline_id": "customer_quality_pipeline",
        "name": "Customer Quality Validation Pipeline",
        "owner": "customer-risk-team",
        "dataset": "customers",
        "contract": "customers.yaml",
        "freshness_sla_minutes": 60,
        "description": "Validates customer master records against KYC, credit score constraints, and null checks.",
        "schedule": "0 * * * *",
        "tags": ["core", "quality", "customers"]
    },
    {
        "pipeline_id": "transaction_quality_pipeline",
        "name": "Transaction Quality Validation Pipeline",
        "owner": "payments-data-team",
        "dataset": "transactions",
        "contract": "transactions.yaml",
        "freshness_sla_minutes": 30,
        "description": "Continuous validation of transaction records for amount ranges, currency, and settlement states.",
        "schedule": "*/15 * * * *",
        "tags": ["core", "quality", "transactions", "financial"]
    },
    {
        "pipeline_id": "feature_quality_pipeline",
        "name": "FeatureHub Feature Quality Pipeline",
        "owner": "mlops-platform-team",
        "dataset": "customer_features",
        "contract": "customer_features.yaml",
        "freshness_sla_minutes": 120,
        "description": "Audits computed FeatureHub feature store tables for drift, null rates, and distribution shifts.",
        "schedule": "0 2 * * *",
        "tags": ["featurehub", "mlops", "features"]
    },
    {
        "pipeline_id": "schema_validation_pipeline",
        "name": "Schema Compatibility & Drift Pipeline",
        "owner": "data-platform-team",
        "dataset": "accounts",
        "contract": "accounts.yaml",
        "freshness_sla_minutes": 180,
        "description": "Validates live physical table schemas against registered contract versions to block breaking changes.",
        "schedule": "0 6 * * *",
        "tags": ["schema", "compatibility", "governance"]
    },
    {
        "pipeline_id": "freshness_monitoring_pipeline",
        "name": "Dataset Freshness SLA Monitoring Pipeline",
        "owner": "data-operations-team",
        "dataset": "fraud_events",
        "contract": "fraud_events.yaml",
        "freshness_sla_minutes": 60,
        "description": "Evaluates dataset freshness against configured SLAs and triggers operational incidents on breach.",
        "schedule": "*/30 * * * *",
        "tags": ["freshness", "sla", "monitoring"]
    },
    # Secondary & Domain Pipelines across the 25+ Contract Catalog
    {
        "pipeline_id": "order_quality_pipeline",
        "name": "Order Processing Quality Pipeline",
        "owner": "commerce-data-team",
        "dataset": "orders",
        "contract": "orders.yaml",
        "freshness_sla_minutes": 60,
        "description": "Validates e-commerce order headers and order lifecycles.",
        "schedule": "0 * * * *",
        "tags": ["commerce", "orders"]
    },
    {
        "pipeline_id": "order_items_quality_pipeline",
        "name": "Order Items Quality Pipeline",
        "owner": "commerce-data-team",
        "dataset": "order_items",
        "contract": "order_items.yaml",
        "freshness_sla_minutes": 60,
        "description": "Validates line items, quantities, and price integrity.",
        "schedule": "0 * * * *",
        "tags": ["commerce", "order_items"]
    },
    {
        "pipeline_id": "payment_processing_pipeline",
        "name": "Payment Processing Quality Pipeline",
        "owner": "payments-data-team",
        "dataset": "payments",
        "contract": "payments.yaml",
        "freshness_sla_minutes": 30,
        "description": "Validates payment settlement and processor reconciliations.",
        "schedule": "*/15 * * * *",
        "tags": ["payments", "financial"]
    },
    {
        "pipeline_id": "fraud_detection_pipeline",
        "name": "Fraud Events Ingestion Quality Pipeline",
        "owner": "fraud-intelligence-team",
        "dataset": "fraud_events",
        "contract": "fraud_events.yaml",
        "freshness_sla_minutes": 15,
        "description": "Validates confirmed fraud events and categorization integrity.",
        "schedule": "*/10 * * * *",
        "tags": ["fraud", "security"]
    },
    {
        "pipeline_id": "merchant_validation_pipeline",
        "name": "Merchant Master Quality Pipeline",
        "owner": "merchant-operations-team",
        "dataset": "merchants",
        "contract": "merchants.yaml",
        "freshness_sla_minutes": 1440,
        "description": "Validates merchant profiles, MCC codes, and risk tiers.",
        "schedule": "0 1 * * *",
        "tags": ["merchants"]
    },
    {
        "pipeline_id": "products_catalog_pipeline",
        "name": "Product Catalog Quality Pipeline",
        "owner": "catalog-data-team",
        "dataset": "products",
        "contract": "products.yaml",
        "freshness_sla_minutes": 720,
        "description": "Validates product SKU catalogs, descriptions, and category mappings.",
        "schedule": "0 4 * * *",
        "tags": ["products", "catalog"]
    },
    {
        "pipeline_id": "user_sessions_pipeline",
        "name": "User Session Telemetry Pipeline",
        "owner": "analytics-engineering-team",
        "dataset": "user_sessions",
        "contract": "user_sessions.yaml",
        "freshness_sla_minutes": 60,
        "description": "Audits user web and mobile session analytics data.",
        "schedule": "0 * * * *",
        "tags": ["telemetry", "sessions"]
    },
    {
        "pipeline_id": "device_fingerprint_pipeline",
        "name": "Device Fingerprint Verification Pipeline",
        "owner": "fraud-intelligence-team",
        "dataset": "device_fingerprints",
        "contract": "device_fingerprints.yaml",
        "freshness_sla_minutes": 60,
        "description": "Audits device telemetry for bot detection and spoofing.",
        "schedule": "0 * * * *",
        "tags": ["security", "devices"]
    },
    {
        "pipeline_id": "ip_geolocation_pipeline",
        "name": "IP Geolocation Ingestion Pipeline",
        "owner": "infrastructure-data-team",
        "dataset": "ip_geolocation",
        "contract": "ip_geolocation.yaml",
        "freshness_sla_minutes": 1440,
        "description": "Validates IP subnet to country and ASN mapping data.",
        "schedule": "0 3 * * *",
        "tags": ["network", "geolocation"]
    },
    {
        "pipeline_id": "card_tokens_pipeline",
        "name": "PCI Card Tokenization Pipeline",
        "owner": "security-compliance-team",
        "dataset": "card_tokens",
        "contract": "card_tokens.yaml",
        "freshness_sla_minutes": 60,
        "description": "Validates token vault mappings without exposing plaintext PAN.",
        "schedule": "0 * * * *",
        "tags": ["security", "compliance", "pci"]
    },
    {
        "pipeline_id": "chargeback_dispute_pipeline",
        "name": "Chargeback & Dispute Pipeline",
        "owner": "risk-operations-team",
        "dataset": "chargeback_disputes",
        "contract": "chargeback_disputes.yaml",
        "freshness_sla_minutes": 720,
        "description": "Validates chargeback claims, dispute stages, and liability shifts.",
        "schedule": "0 5 * * *",
        "tags": ["disputes", "risk"]
    },
    {
        "pipeline_id": "kyc_verification_pipeline",
        "name": "KYC Verification Pipeline",
        "owner": "compliance-data-team",
        "dataset": "kyc_verification_logs",
        "contract": "kyc_verification_logs.yaml",
        "freshness_sla_minutes": 360,
        "description": "Validates identity document checks and sanctions screening logs.",
        "schedule": "0 */6 * * *",
        "tags": ["kyc", "compliance"]
    },
    {
        "pipeline_id": "audit_trail_pipeline",
        "name": "Platform Audit Trail Pipeline",
        "owner": "security-compliance-team",
        "dataset": "audit_trail_events",
        "contract": "audit_trail_events.yaml",
        "freshness_sla_minutes": 60,
        "description": "Validates immutable security logs and privileged access events.",
        "schedule": "0 * * * *",
        "tags": ["security", "audit"]
    },
    {
        "pipeline_id": "model_predictions_pipeline",
        "name": "Model Predictions Inference Pipeline",
        "owner": "mlops-platform-team",
        "dataset": "model_predictions_log",
        "contract": "model_predictions_log.yaml",
        "freshness_sla_minutes": 60,
        "description": "Validates real-time inference scores, latencies, and prediction distributions.",
        "schedule": "0 * * * *",
        "tags": ["mlops", "inference"]
    },
    {
        "pipeline_id": "account_features_pipeline",
        "name": "Account Feature Store Pipeline",
        "owner": "mlops-platform-team",
        "dataset": "account_features",
        "contract": "account_features.yaml",
        "freshness_sla_minutes": 180,
        "description": "Validates aggregate account balance and velocity features.",
        "schedule": "0 */3 * * *",
        "tags": ["featurehub", "features"]
    },
    {
        "pipeline_id": "merchant_features_pipeline",
        "name": "Merchant Risk Features Pipeline",
        "owner": "mlops-platform-team",
        "dataset": "merchant_risk_features",
        "contract": "merchant_risk_features.yaml",
        "freshness_sla_minutes": 180,
        "description": "Validates merchant chargeback ratios and settlement velocity.",
        "schedule": "0 */3 * * *",
        "tags": ["featurehub", "features"]
    },
    {
        "pipeline_id": "transaction_window_features_pipeline",
        "name": "Transaction Window Feature Pipeline",
        "owner": "mlops-platform-team",
        "dataset": "transaction_window_features",
        "contract": "transaction_window_features.yaml",
        "freshness_sla_minutes": 60,
        "description": "Validates 1h, 24h, 7d rolling aggregation features.",
        "schedule": "0 * * * *",
        "tags": ["featurehub", "features"]
    },
    {
        "pipeline_id": "daily_customer_aggregates_pipeline",
        "name": "Daily Customer Aggregates Pipeline",
        "owner": "analytics-engineering-team",
        "dataset": "daily_customer_aggregates",
        "contract": "daily_customer_aggregates.yaml",
        "freshness_sla_minutes": 1440,
        "description": "Validates end-of-day customer rollups and spend analytics.",
        "schedule": "0 2 * * *",
        "tags": ["analytics", "aggregates"]
    },
    {
        "pipeline_id": "hourly_merchant_metrics_pipeline",
        "name": "Hourly Merchant Metrics Pipeline",
        "owner": "merchant-operations-team",
        "dataset": "hourly_merchant_metrics",
        "contract": "hourly_merchant_metrics.yaml",
        "freshness_sla_minutes": 60,
        "description": "Validates hourly authorization rates and gateway response codes.",
        "schedule": "0 * * * *",
        "tags": ["merchants", "metrics"]
    },
    {
        "pipeline_id": "velocity_risk_features_pipeline",
        "name": "Velocity Risk Feature Pipeline",
        "owner": "mlops-platform-team",
        "dataset": "velocity_risk_features",
        "contract": "velocity_risk_features.yaml",
        "freshness_sla_minutes": 60,
        "description": "Validates card swipe velocity and rapid-fire transaction features.",
        "schedule": "0 * * * *",
        "tags": ["featurehub", "features", "fraud"]
    },
    {
        "pipeline_id": "temporal_behavioral_features_pipeline",
        "name": "Temporal Behavioral Feature Pipeline",
        "owner": "mlops-platform-team",
        "dataset": "temporal_behavioral_features",
        "contract": "temporal_behavioral_features.yaml",
        "freshness_sla_minutes": 360,
        "description": "Validates customer circadian activity distributions and weekday/weekend ratios.",
        "schedule": "0 */6 * * *",
        "tags": ["featurehub", "features", "mlops"]
    }
]


class PipelineRegistryService:
    """
    Manages discovery and initialization of pipeline definitions across the platform.
    """

    def __init__(self, repository: Optional[PipelineRepository] = None):
        self.repository = repository or PipelineRepository()

    def sync_all_pipelines(self) -> int:
        """
        Idempotently synchronizes all 26 defined pipelines into PostgreSQL metadata.
        Returns the number of synchronized pipelines.
        """
        count = 0
        for pipe_dict in STANDARD_PIPELINES:
            config = PipelineConfig(**pipe_dict)
            self.repository.upsert_pipeline(config)
            count += 1
        return count

    def get_standard_pipeline(self, pipeline_id: str) -> Optional[PipelineConfig]:
        """
        Retrieves configuration definition from the static catalog.
        """
        for item in STANDARD_PIPELINES:
            if item["pipeline_id"] == pipeline_id:
                return PipelineConfig(**item)
        return None

    def list_standard_pipelines(self) -> List[PipelineConfig]:
        """
        Lists all static catalog configurations.
        """
        return [PipelineConfig(**p) for p in STANDARD_PIPELINES]
