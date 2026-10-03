"""
DataGuard Phase A Data Contract Generator
Creates 25 production-style YAML data contracts with rich column definitions, constraints, descriptions, and SLAs.
"""

import os
import yaml
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "dataguard" / "contracts"
CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)

CONTRACTS = [
    {
        "dataset": "customers",
        "version": "v1.0.0",
        "owner": "customer-data-team",
        "description": "Core customer identity profile, KYC verification state, and credit risk tiering",
        "freshness_sla_minutes": 1440,
        "constraints": {
            "min_rows": 100,
            "primary_key": "customer_id"
        },
        "columns": [
            {"name": "customer_id", "type": "string", "nullable": False, "unique": True, "description": "Unique global customer identifier format cust_XXXXXX"},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Timestamp when customer account was opened"},
            {"name": "kyc_status", "type": "string", "nullable": False, "unique": False, "description": "KYC identity status", "allowed_values": ["VERIFIED", "PENDING", "ENHANCED_DUE_DILIGENCE"]},
            {"name": "risk_tier", "type": "string", "nullable": False, "unique": False, "description": "Internal fraud risk classification", "allowed_values": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
            {"name": "country", "type": "string", "nullable": False, "unique": False, "description": "ISO 2-letter country code of customer residence"}
        ]
    },
    {
        "dataset": "accounts",
        "version": "v1.0.0",
        "owner": "banking-data-team",
        "description": "Customer bank accounts and balance ledgers",
        "freshness_sla_minutes": 60,
        "constraints": {
            "min_rows": 100,
            "primary_key": "account_id",
            "foreign_keys": [{"column": "customer_id", "references": "customers.customer_id"}]
        },
        "columns": [
            {"name": "account_id", "type": "string", "nullable": False, "unique": True, "description": "Unique account identifier acc_XXXXXX"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Owner customer identifier"},
            {"name": "account_type", "type": "string", "nullable": False, "unique": False, "description": "Product account type", "allowed_values": ["CHECKING", "SAVINGS", "CREDIT"]},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Account opening timestamp"},
            {"name": "current_balance", "type": "numeric", "nullable": False, "unique": False, "description": "Current ledger balance in USD", "min": -10000.0, "max": 10000000.0}
        ]
    },
    {
        "dataset": "merchants",
        "version": "v1.0.0",
        "owner": "merchant-analytics-team",
        "description": "Merchant catalog and risk scoring profiles",
        "freshness_sla_minutes": 1440,
        "constraints": {
            "min_rows": 50,
            "primary_key": "merchant_id"
        },
        "columns": [
            {"name": "merchant_id", "type": "string", "nullable": False, "unique": True, "description": "Unique merchant identifier merch_XXXXX"},
            {"name": "merchant_category", "type": "string", "nullable": False, "unique": False, "description": "MCC Category name", "allowed_values": ["RETAIL", "TRAVEL", "GAMBLING", "CRYPTO", "ELECTRONICS", "DINING", "SERVICES"]},
            {"name": "risk_score", "type": "float", "nullable": False, "unique": False, "description": "Risk score between 0.0 and 1.0", "min": 0.0, "max": 1.0},
            {"name": "country", "type": "string", "nullable": False, "unique": False, "description": "Merchant registration country"},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Registration date"}
        ]
    },
    {
        "dataset": "transactions",
        "version": "v1.0.0",
        "owner": "payments-data-team",
        "description": "Real-time payment transaction event log",
        "freshness_sla_minutes": 15,
        "constraints": {
            "min_rows": 500,
            "primary_key": "transaction_id"
        },
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False, "unique": True, "description": "Unique transaction event ID txn_XXXXXXXX"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Customer ID executing payment"},
            {"name": "account_id", "type": "string", "nullable": False, "unique": False, "description": "Debited account ID"},
            {"name": "merchant_id", "type": "string", "nullable": False, "unique": False, "description": "Receiving merchant ID"},
            {"name": "amount", "type": "numeric", "nullable": False, "unique": False, "description": "Transaction amount in USD", "min": 0.01, "max": 500000.0},
            {"name": "timestamp", "type": "timestamp", "nullable": False, "unique": False, "description": "Event timestamp in UTC"},
            {"name": "status", "type": "string", "nullable": False, "unique": False, "description": "Authorization status", "allowed_values": ["APPROVED", "FAILED", "REJECTED"]},
            {"name": "channel", "type": "string", "nullable": False, "unique": False, "description": "Initiating payment channel", "allowed_values": ["WEB", "MOBILE_APP", "POS", "ATM", "WIRE"]},
            {"name": "is_fraud", "type": "integer", "nullable": False, "unique": False, "description": "Ground truth fraud label (0=Normal, 1=Fraud)", "allowed_values": [0, 1]}
        ]
    },
    {
        "dataset": "orders",
        "version": "v1.0.0",
        "owner": "e-commerce-data-team",
        "description": "Customer e-commerce purchase orders",
        "freshness_sla_minutes": 60,
        "constraints": {"min_rows": 10, "primary_key": "order_id"},
        "columns": [
            {"name": "order_id", "type": "string", "nullable": False, "unique": True, "description": "Unique purchase order ID"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Purchasing customer ID"},
            {"name": "order_total", "type": "numeric", "nullable": False, "unique": False, "description": "Total order amount", "min": 0.0, "max": 100000.0},
            {"name": "currency", "type": "string", "nullable": False, "unique": False, "description": "Currency code", "allowed_values": ["USD", "EUR", "GBP", "CAD"]},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Order placement time"}
        ]
    },
    {
        "dataset": "order_items",
        "version": "v1.0.0",
        "owner": "e-commerce-data-team",
        "description": "Individual line items per order",
        "freshness_sla_minutes": 60,
        "constraints": {"min_rows": 10, "primary_key": "item_id"},
        "columns": [
            {"name": "item_id", "type": "string", "nullable": False, "unique": True, "description": "Line item identifier"},
            {"name": "order_id", "type": "string", "nullable": False, "unique": False, "description": "Parent order ID"},
            {"name": "product_id", "type": "string", "nullable": False, "unique": False, "description": "Product catalog ID"},
            {"name": "quantity", "type": "integer", "nullable": False, "unique": False, "description": "Unit item quantity", "min": 1, "max": 100},
            {"name": "unit_price", "type": "numeric", "nullable": False, "unique": False, "description": "Price per item", "min": 0.01}
        ]
    },
    {
        "dataset": "payments",
        "version": "v1.0.0",
        "owner": "payments-data-team",
        "description": "Payment gateway settlement records",
        "freshness_sla_minutes": 30,
        "constraints": {"min_rows": 10, "primary_key": "payment_id"},
        "columns": [
            {"name": "payment_id", "type": "string", "nullable": False, "unique": True, "description": "Payment settlement ID"},
            {"name": "order_id", "type": "string", "nullable": False, "unique": False, "description": "Order reference ID"},
            {"name": "payment_method", "type": "string", "nullable": False, "unique": False, "description": "Method", "allowed_values": ["CREDIT_CARD", "DEBIT_CARD", "PAYPAL", "WIRE"]},
            {"name": "status", "type": "string", "nullable": False, "unique": False, "description": "Settlement state", "allowed_values": ["SETTLED", "PENDING", "FAILED", "REFUNDED"]},
            {"name": "settled_at", "type": "timestamp", "nullable": True, "unique": False, "description": "Settlement timestamp"}
        ]
    },
    {
        "dataset": "products",
        "version": "v1.0.0",
        "owner": "catalog-data-team",
        "description": "Product catalog and pricing",
        "freshness_sla_minutes": 1440,
        "constraints": {"min_rows": 20, "primary_key": "product_id"},
        "columns": [
            {"name": "product_id", "type": "string", "nullable": False, "unique": True, "description": "Product ID"},
            {"name": "name", "type": "string", "nullable": False, "unique": False, "description": "Product title"},
            {"name": "category", "type": "string", "nullable": False, "unique": False, "description": "Category name"},
            {"name": "price", "type": "numeric", "nullable": False, "unique": False, "description": "Current retail price", "min": 0.01},
            {"name": "stock_quantity", "type": "integer", "nullable": False, "unique": False, "description": "Inventory stock", "min": 0}
        ]
    },
    {
        "dataset": "fraud_events",
        "version": "v1.0.0",
        "owner": "fraud-analytics-team",
        "description": "Confirmed fraud case investigation registry",
        "freshness_sla_minutes": 120,
        "constraints": {"min_rows": 5, "primary_key": "event_id"},
        "columns": [
            {"name": "event_id", "type": "string", "nullable": False, "unique": True, "description": "Fraud case event ID fevt_XXXXXX"},
            {"name": "transaction_id", "type": "string", "nullable": False, "unique": False, "description": "Target transaction ID"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Fraudulent customer ID"},
            {"name": "fraud_type", "type": "string", "nullable": False, "unique": False, "description": "Typology", "allowed_values": ["ACCOUNT_TAKEOVER", "CARD_TESTING", "IDENTITY_THEFT", "CHARGEBACK_FRAUD"]},
            {"name": "confirmed_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Confirmation timestamp"}
        ]
    },
    {
        "dataset": "customer_features",
        "version": "v1.0.0",
        "owner": "featurestore-team",
        "description": "FeatureHub customer windowed aggregates and velocity features",
        "freshness_sla_minutes": 60,
        "constraints": {"min_rows": 100, "primary_key": "customer_id"},
        "columns": [
            {"name": "customer_id", "type": "string", "nullable": False, "unique": True, "description": "Entity ID"},
            {"name": "feature_timestamp", "type": "timestamp", "nullable": False, "unique": False, "description": "Observation time"},
            {"name": "cust_txn_count_1h", "type": "integer", "nullable": False, "unique": False, "description": "1-hour transaction count", "min": 0},
            {"name": "cust_txn_count_24h", "type": "integer", "nullable": False, "unique": False, "description": "24-hour transaction count", "min": 0},
            {"name": "cust_txn_amount_sum_24h", "type": "float", "nullable": False, "unique": False, "description": "24-hour spend volume", "min": 0.0}
        ]
    },
    {
        "dataset": "account_features",
        "version": "v1.0.0",
        "owner": "featurestore-team",
        "description": "FeatureHub account drain and balance velocity indicators",
        "freshness_sla_minutes": 60,
        "constraints": {"min_rows": 100, "primary_key": "account_id"},
        "columns": [
            {"name": "account_id", "type": "string", "nullable": False, "unique": True, "description": "Entity ID"},
            {"name": "feature_timestamp", "type": "timestamp", "nullable": False, "unique": False, "description": "Observation time"},
            {"name": "acc_balance_ratio_24h", "type": "float", "nullable": False, "unique": False, "description": "Spend to balance ratio", "min": 0.0, "max": 10.0},
            {"name": "acc_is_overdrawn_flag", "type": "integer", "nullable": False, "unique": False, "description": "Overdraft flag", "allowed_values": [0, 1]}
        ]
    },
    {
        "dataset": "merchant_risk_features",
        "version": "v1.0.0",
        "owner": "featurestore-team",
        "description": "FeatureHub merchant historical fraud rates and velocity spikes",
        "freshness_sla_minutes": 1440,
        "constraints": {"min_rows": 50, "primary_key": "merchant_id"},
        "columns": [
            {"name": "merchant_id", "type": "string", "nullable": False, "unique": True, "description": "Entity ID"},
            {"name": "feature_timestamp", "type": "timestamp", "nullable": False, "unique": False, "description": "Observation time"},
            {"name": "merch_risk_score", "type": "float", "nullable": False, "unique": False, "description": "Merchant score", "min": 0.0, "max": 1.0},
            {"name": "merch_fraud_rate_30d", "type": "float", "nullable": False, "unique": False, "description": "30-day fraud rate", "min": 0.0, "max": 1.0}
        ]
    },
    {
        "dataset": "transaction_window_features",
        "version": "v1.0.0",
        "owner": "featurestore-team",
        "description": "Windowed transaction velocity statistics and ratio comparisons",
        "freshness_sla_minutes": 15,
        "constraints": {"min_rows": 100, "primary_key": "transaction_id"},
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False, "unique": True, "description": "Target transaction ID"},
            {"name": "feature_timestamp", "type": "timestamp", "nullable": False, "unique": False, "description": "Event timestamp"},
            {"name": "txn_amount_to_cust_avg_ratio_7d", "type": "float", "nullable": False, "unique": False, "description": "Amount vs customer 7d avg ratio", "min": 0.0},
            {"name": "txn_is_night_time_flag", "type": "integer", "nullable": False, "unique": False, "description": "Night time transaction flag", "allowed_values": [0, 1]}
        ]
    },
    {
        "dataset": "temporal_behavioral_features",
        "version": "v1.0.0",
        "owner": "featurestore-team",
        "description": "Customer lifestyle, weekend spending, and channel ratios",
        "freshness_sla_minutes": 1440,
        "constraints": {"min_rows": 100, "primary_key": "customer_id"},
        "columns": [
            {"name": "customer_id", "type": "string", "nullable": False, "unique": True, "description": "Customer entity ID"},
            {"name": "feature_timestamp", "type": "timestamp", "nullable": False, "unique": False, "description": "Observation time"},
            {"name": "cust_activity_score", "type": "float", "nullable": False, "unique": False, "description": "Engagement score", "min": 0.0, "max": 1.0},
            {"name": "cust_night_owl_ratio_30d", "type": "float", "nullable": False, "unique": False, "description": "Night owl transaction ratio", "min": 0.0, "max": 1.0}
        ]
    },
    {
        "dataset": "velocity_risk_features",
        "version": "v1.0.0",
        "owner": "featurestore-team",
        "description": "Composite non-linear risk and velocity indicators",
        "freshness_sla_minutes": 15,
        "constraints": {"min_rows": 100, "primary_key": "customer_id"},
        "columns": [
            {"name": "customer_id", "type": "string", "nullable": False, "unique": True, "description": "Customer entity ID"},
            {"name": "feature_timestamp", "type": "timestamp", "nullable": False, "unique": False, "description": "Observation time"},
            {"name": "cust_risk_velocity_composite", "type": "float", "nullable": False, "unique": False, "description": "Risk composite score", "min": 0.0, "max": 1.0},
            {"name": "burst_txn_count_10min", "type": "integer", "nullable": False, "unique": False, "description": "10-minute burst count", "min": 0}
        ]
    },
    {
        "dataset": "kyc_verification_logs",
        "version": "v1.0.0",
        "owner": "security-identity-team",
        "description": "KYC identity check attempt logs and document status",
        "freshness_sla_minutes": 60,
        "constraints": {"min_rows": 10, "primary_key": "verification_id"},
        "columns": [
            {"name": "verification_id", "type": "string", "nullable": False, "unique": True, "description": "KYC attempt ID"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Target customer ID"},
            {"name": "document_type", "type": "string", "nullable": False, "unique": False, "description": "Doc type", "allowed_values": ["PASSPORT", "DRIVERS_LICENSE", "NATIONAL_ID"]},
            {"name": "verification_result", "type": "string", "nullable": False, "unique": False, "description": "Result", "allowed_values": ["PASSED", "FAILED", "MANUAL_REVIEW"]},
            {"name": "attempted_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Attempt timestamp"}
        ]
    },
    {
        "dataset": "device_fingerprints",
        "version": "v1.0.0",
        "owner": "security-team",
        "description": "Mobile & Web device user agent and hardware fingerprint logs",
        "freshness_sla_minutes": 15,
        "constraints": {"min_rows": 100, "primary_key": "device_id"},
        "columns": [
            {"name": "device_id", "type": "string", "nullable": False, "unique": True, "description": "Device hash identifier"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Associated customer"},
            {"name": "os_family", "type": "string", "nullable": False, "unique": False, "description": "OS", "allowed_values": ["IOS", "ANDROID", "WINDOWS", "MACOS", "LINUX"]},
            {"name": "browser", "type": "string", "nullable": False, "unique": False, "description": "Browser name"},
            {"name": "first_seen_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Device registration time"}
        ]
    },
    {
        "dataset": "ip_geolocation",
        "version": "v1.0.0",
        "owner": "security-team",
        "description": "IP address lookup table with ASN, country, and risk index",
        "freshness_sla_minutes": 1440,
        "constraints": {"min_rows": 50, "primary_key": "ip_address"},
        "columns": [
            {"name": "ip_address", "type": "string", "nullable": False, "unique": True, "description": "IPv4 / IPv6 address"},
            {"name": "country_code", "type": "string", "nullable": False, "unique": False, "description": "Geographic country"},
            {"name": "isp_asn", "type": "string", "nullable": False, "unique": False, "description": "Autonomous System Number"},
            {"name": "is_proxy_vpn_flag", "type": "integer", "nullable": False, "unique": False, "description": "VPN/Proxy flag", "allowed_values": [0, 1]},
            {"name": "ip_risk_score", "type": "float", "nullable": False, "unique": False, "description": "IP risk score", "min": 0.0, "max": 1.0}
        ]
    },
    {
        "dataset": "card_tokens",
        "version": "v1.0.0",
        "owner": "payments-data-team",
        "description": "PCI-compliant card tokenization mapping and expiration dates",
        "freshness_sla_minutes": 1440,
        "constraints": {"min_rows": 50, "primary_key": "token_id"},
        "columns": [
            {"name": "token_id", "type": "string", "nullable": False, "unique": True, "description": "Card token identifier"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Cardholder customer ID"},
            {"name": "card_brand", "type": "string", "nullable": False, "unique": False, "description": "Brand", "allowed_values": ["VISA", "MASTERCARD", "AMEX", "DISCOVER"]},
            {"name": "last_four", "type": "string", "nullable": False, "unique": False, "description": "Card last 4 digits"},
            {"name": "expiry_month_year", "type": "string", "nullable": False, "unique": False, "description": "Expiry format MM/YY"}
        ]
    },
    {
        "dataset": "chargeback_disputes",
        "version": "v1.0.0",
        "owner": "fraud-analytics-team",
        "description": "Credit card chargeback filings and dispute statuses",
        "freshness_sla_minutes": 720,
        "constraints": {"min_rows": 5, "primary_key": "dispute_id"},
        "columns": [
            {"name": "dispute_id", "type": "string", "nullable": False, "unique": True, "description": "Dispute filing ID"},
            {"name": "transaction_id", "type": "string", "nullable": False, "unique": False, "description": "Disputed transaction ID"},
            {"name": "dispute_reason", "type": "string", "nullable": False, "unique": False, "description": "Reason", "allowed_values": ["FRAUDULENT", "UNRECOGNIZED", "PRODUCT_NOT_RECEIVED", "DUPLICATE"]},
            {"name": "status", "type": "string", "nullable": False, "unique": False, "description": "Dispute status", "allowed_values": ["OPEN", "WON", "LOST", "UNDER_REVIEW"]},
            {"name": "filed_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Filing timestamp"}
        ]
    },
    {
        "dataset": "daily_customer_aggregates",
        "version": "v1.0.0",
        "owner": "analytics-data-team",
        "description": "Daily aggregated spending summaries per customer",
        "freshness_sla_minutes": 1440,
        "constraints": {"min_rows": 50, "primary_key": "aggregate_id"},
        "columns": [
            {"name": "aggregate_id", "type": "string", "nullable": False, "unique": True, "description": "Aggregate ID"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Customer ID"},
            {"name": "date", "type": "string", "nullable": False, "unique": False, "description": "Aggregation date YYYY-MM-DD"},
            {"name": "daily_spend_usd", "type": "numeric", "nullable": False, "unique": False, "description": "Total spend USD", "min": 0.0},
            {"name": "daily_txn_count", "type": "integer", "nullable": False, "unique": False, "description": "Total transaction count", "min": 0}
        ]
    },
    {
        "dataset": "hourly_merchant_metrics",
        "version": "v1.0.0",
        "owner": "analytics-data-team",
        "description": "Hourly merchant transaction volume and decline rates rollup",
        "freshness_sla_minutes": 60,
        "constraints": {"min_rows": 50, "primary_key": "metric_id"},
        "columns": [
            {"name": "metric_id", "type": "string", "nullable": False, "unique": True, "description": "Metric rollup ID"},
            {"name": "merchant_id", "type": "string", "nullable": False, "unique": False, "description": "Merchant ID"},
            {"name": "hour_timestamp", "type": "timestamp", "nullable": False, "unique": False, "description": "Hour boundary timestamp"},
            {"name": "hourly_volume_usd", "type": "numeric", "nullable": False, "unique": False, "description": "Volume USD", "min": 0.0},
            {"name": "decline_rate", "type": "float", "nullable": False, "unique": False, "description": "Decline rate", "min": 0.0, "max": 1.0}
        ]
    },
    {
        "dataset": "model_predictions_log",
        "version": "v1.0.0",
        "owner": "ml-platform-team",
        "description": "Real-time ML inference prediction logs and fraud risk scores",
        "freshness_sla_minutes": 15,
        "constraints": {"min_rows": 100, "primary_key": "prediction_id"},
        "columns": [
            {"name": "prediction_id", "type": "string", "nullable": False, "unique": True, "description": "Prediction event ID"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Customer ID"},
            {"name": "risk_score", "type": "float", "nullable": False, "unique": False, "description": "ML fraud probability", "min": 0.0, "max": 1.0},
            {"name": "prediction", "type": "integer", "nullable": False, "unique": False, "description": "Flag (0=Approve, 1=Fraud)", "allowed_values": [0, 1]},
            {"name": "model_version", "type": "string", "nullable": False, "unique": False, "description": "Model artifact version"},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Inference timestamp"}
        ]
    },
    {
        "dataset": "audit_trail_events",
        "version": "v1.0.0",
        "owner": "security-governance-team",
        "description": "Platform security access and schema modification audit events log",
        "freshness_sla_minutes": 15,
        "constraints": {"min_rows": 10, "primary_key": "audit_id"},
        "columns": [
            {"name": "audit_id", "type": "string", "nullable": False, "unique": True, "description": "Audit event ID"},
            {"name": "user_id", "type": "string", "nullable": False, "unique": False, "description": "Actor user ID"},
            {"name": "action", "type": "string", "nullable": False, "unique": False, "description": "Performed action", "allowed_values": ["CREATE", "UPDATE", "DELETE", "ACCESS", "CONTRACT_DIFF"]},
            {"name": "target_resource", "type": "string", "nullable": False, "unique": False, "description": "Target dataset / API"},
            {"name": "timestamp", "type": "timestamp", "nullable": False, "unique": False, "description": "Event timestamp"}
        ]
    },
    {
        "dataset": "user_sessions",
        "version": "v1.0.0",
        "owner": "app-platform-team",
        "description": "App active session tokens, durations, and payment channels",
        "freshness_sla_minutes": 15,
        "constraints": {"min_rows": 50, "primary_key": "session_id"},
        "columns": [
            {"name": "session_id", "type": "string", "nullable": False, "unique": True, "description": "Session token ID"},
            {"name": "customer_id", "type": "string", "nullable": False, "unique": False, "description": "Customer ID"},
            {"name": "channel", "type": "string", "nullable": False, "unique": False, "description": "Session channel", "allowed_values": ["WEB", "MOBILE_APP", "POS", "ATM", "WIRE"]},
            {"name": "duration_seconds", "type": "integer", "nullable": False, "unique": False, "description": "Session duration", "min": 0},
            {"name": "created_at", "type": "timestamp", "nullable": False, "unique": False, "description": "Session start timestamp"}
        ]
    }
]

def build_phase_a_contracts():
    print(f"Building Phase A Data Contracts in {CONTRACTS_DIR}...")
    for contract in CONTRACTS:
        file_path = CONTRACTS_DIR / f"{contract['dataset']}.yaml"
        with open(file_path, "w") as f:
            yaml.dump(contract, f, sort_keys=False, default_flow_style=False)
        print(f"  [+] Wrote complete contract: {contract['dataset']}.yaml ({len(contract['columns'])} columns)")
    
    print(f"\nPhase A Contract Generation Complete: {len(CONTRACTS)} contracts written successfully.")

if __name__ == "__main__":
    build_phase_a_contracts()
