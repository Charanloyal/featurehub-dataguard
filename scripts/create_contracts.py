"""
DataGuard Data Contract Generator
Creates 25 production-style YAML contracts with strict column constraints, data types, and SLAs.
"""

import os
import yaml
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "dataguard" / "contracts"
CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)

CONTRACT_DEFINITIONS = [
    {
        "dataset": "customers",
        "version": "v1.0.0",
        "owner": "data-platform-team",
        "description": "Core customer identity profile and risk tiers",
        "freshness_sla_minutes": 1440,
        "columns": [
            {"name": "customer_id", "type": "string", "nullable": False, "unique": True},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False},
            {"name": "kyc_status", "type": "string", "nullable": False, "unique": False, "allowed_values": ["VERIFIED", "PENDING", "ENHANCED_DUE_DILIGENCE"]},
            {"name": "risk_tier", "type": "string", "nullable": False, "unique": False, "allowed_values": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
            {"name": "country", "type": "string", "nullable": False, "unique": False}
        ]
    },
    {
        "dataset": "accounts",
        "version": "v1.0.0",
        "owner": "banking-data-team",
        "description": "Customer bank accounts and balance ledgers",
        "freshness_sla_minutes": 60,
        "columns": [
            {"name": "account_id", "type": "string", "nullable": False, "unique": True},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False},
            {"name": "account_type", "type": "string", "nullable": False, "unique": False, "allowed_values": ["CHECKING", "SAVINGS", "CREDIT"]},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False},
            {"name": "current_balance", "type": "numeric", "nullable": False, "unique": False, "min": -10000.0, "max": 10000000.0}
        ]
    },
    {
        "dataset": "merchants",
        "version": "v1.0.0",
        "owner": "merchant-analytics",
        "description": "Merchant catalog and risk scoring profiles",
        "freshness_sla_minutes": 1440,
        "columns": [
            {"name": "merchant_id", "type": "string", "nullable": False, "unique": True},
            {"name": "merchant_category", "type": "string", "nullable": False, "unique": False},
            {"name": "risk_score", "type": "float", "nullable": False, "unique": False, "min": 0.0, "max": 1.0},
            {"name": "country", "type": "string", "nullable": False, "unique": False},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False}
        ]
    },
    {
        "dataset": "transactions",
        "version": "v1.0.0",
        "owner": "payments-data-team",
        "description": "Real-time payment transaction event log",
        "freshness_sla_minutes": 15,
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False, "unique": True},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False},
            {"name": "account_id", "type": "string", "nullable": False, "unique": False},
            {"name": "merchant_id", "type": "string", "nullable": False, "unique": False},
            {"name": "amount", "type": "numeric", "nullable": False, "unique": False, "min": 0.01, "max": 500000.0},
            {"name": "timestamp", "type": "timestamp", "nullable": False, "unique": False},
            {"name": "status", "type": "string", "nullable": False, "unique": False, "allowed_values": ["APPROVED", "FAILED", "REJECTED"]},
            {"name": "channel", "type": "string", "nullable": False, "unique": False, "allowed_values": ["WEB", "MOBILE_APP", "POS", "ATM", "WIRE"]},
            {"name": "is_fraud", "type": "integer", "nullable": False, "unique": False, "allowed_values": [0, 1]}
        ]
    },
    {
        "dataset": "orders",
        "version": "v1.0.0",
        "owner": "e-commerce-team",
        "description": "Customer e-commerce purchase orders",
        "freshness_sla_minutes": 60,
        "columns": [
            {"name": "order_id", "type": "string", "nullable": False, "unique": True},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False},
            {"name": "order_total", "type": "numeric", "nullable": False, "unique": False, "min": 0.0},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False}
        ]
    },
    {
        "dataset": "order_items",
        "version": "v1.0.0",
        "owner": "e-commerce-team",
        "description": "Individual line items per order",
        "freshness_sla_minutes": 60,
        "columns": [
            {"name": "item_id", "type": "string", "nullable": False, "unique": True},
            {"name": "order_id", "type": "string", "nullable": False, "unique": False},
            {"name": "product_id", "type": "string", "nullable": False, "unique": False},
            {"name": "quantity", "type": "integer", "nullable": False, "unique": False, "min": 1}
        ]
    },
    {
        "dataset": "payments",
        "version": "v1.0.0",
        "owner": "payments-data-team",
        "description": "Payment settlement records",
        "freshness_sla_minutes": 30,
        "columns": [
            {"name": "payment_id", "type": "string", "nullable": False, "unique": True},
            {"name": "order_id", "type": "string", "nullable": False, "unique": False},
            {"name": "status", "type": "string", "nullable": False, "unique": False}
        ]
    },
    {
        "dataset": "products",
        "version": "v1.0.0",
        "owner": "catalog-team",
        "description": "Product catalog and pricing",
        "freshness_sla_minutes": 1440,
        "columns": [
            {"name": "product_id", "type": "string", "nullable": False, "unique": True},
            {"name": "category", "type": "string", "nullable": False, "unique": False},
            {"name": "price", "type": "numeric", "nullable": False, "unique": False, "min": 0.0}
        ]
    },
    {
        "dataset": "fraud_events",
        "version": "v1.0.0",
        "owner": "fraud-analytics-team",
        "description": "Confirmed fraud case investigation registry",
        "freshness_sla_minutes": 120,
        "columns": [
            {"name": "event_id", "type": "string", "nullable": False, "unique": True},
            {"name": "transaction_id", "type": "string", "nullable": False, "unique": False},
            {"name": "confirmed_at", "type": "timestamp", "nullable": False, "unique": False}
        ]
    }
]

# Generate remaining up to 25 contracts programmatically
EXTRA_DATASETS = [
    ("customer_features", "Customer windowed aggregates for FeatureHub"),
    ("account_balance_features", "Account drain and balance features"),
    ("merchant_risk_features", "Merchant historical fraud rates"),
    ("transaction_window_features", "Windowed transaction velocity stats"),
    ("temporal_behavioral_features", "Customer lifestyle and channel ratios"),
    ("velocity_risk_features", "Composite risk and velocity indicators"),
    ("kyc_verification_logs", "KYC identity check attempt logs"),
    ("device_fingerprints", "Device MAC and browser user agent logs"),
    ("ip_geolocation", "IP address location lookup tables"),
    ("card_tokens", "PCI-compliant card token mapping"),
    ("chargeback_disputes", "Customer credit card dispute filings"),
    ("daily_customer_aggregates", "Daily aggregated spending summaries"),
    ("hourly_merchant_metrics", "Hourly merchant transaction volume rollup"),
    ("model_predictions_log", "Real-time ML inference prediction logs"),
    ("audit_trail_events", "Data platform access & security audit log"),
    ("user_sessions", "Customer app session logs")
]

for name, desc in EXTRA_DATASETS:
    CONTRACT_DEFINITIONS.append({
        "dataset": name,
        "version": "v1.0.0",
        "owner": "data-platform-team",
        "description": desc,
        "freshness_sla_minutes": 60,
        "columns": [
            {"name": f"{name}_id", "type": "string", "nullable": False, "unique": True},
            {"name": "entity_id", "type": "string", "nullable": False, "unique": False},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False},
            {"name": "metric_val", "type": "float", "nullable": True, "unique": False}
        ]
    })

def generate_contracts():
    print(f"Generating 25 YAML Data Contracts in {CONTRACTS_DIR}...")
    for contract in CONTRACT_DEFINITIONS:
        file_path = CONTRACTS_DIR / f"{contract['dataset']}.yaml"
        with open(file_path, "w") as f:
            yaml.dump(contract, f, sort_keys=False, default_flow_style=False)
        print(f"  [+] Created contract: {contract['dataset']}.yaml")
    print("All 25 data contracts successfully created.")

if __name__ == "__main__":
    generate_contracts()
