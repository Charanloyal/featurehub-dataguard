"""
Seed Data Generator for Financial Transaction Domain
Generates realistic entities (customers, accounts, merchants) and transactions over a 30-day window.
"""

import os
import random
import uuid
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")
os.makedirs(DATA_DIR, exist_ok=True)

NUM_CUSTOMERS = 5000
NUM_ACCOUNTS = 6500
NUM_MERCHANTS = 1000
NUM_TRANSACTIONS = 100000

KYC_STATUSES = ["VERIFIED", "PENDING", "ENHANCED_DUE_DILIGENCE"]
RISK_TIERS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
COUNTRIES = ["US", "GB", "CA", "DE", "FR", "JP", "SG", "AU"]
MERCHANT_CATS = ["RETAIL", "TRAVEL", "GAMBLING", "CRYPTO", "ELECTRONICS", "DINING", "SERVICES"]
CHANNELS = ["WEB", "MOBILE_APP", "POS", "ATM", "WIRE"]

def generate_seed_data():
    print(f"Generating synthetic financial dataset in {DATA_DIR}...")
    random.seed(42)
    np.random.seed(42)

    start_date = datetime.now(timezone.utc) - timedelta(days=30)

    # 1. Customers
    customer_ids = [f"cust_{i:06d}" for i in range(1, NUM_CUSTOMERS + 1)]
    customers = []
    for cid in customer_ids:
        c_created = start_date - timedelta(days=random.randint(30, 365))
        customers.append({
            "customer_id": cid,
            "created_at": c_created.isoformat(),
            "kyc_status": random.choice(KYC_STATUSES),
            "risk_tier": random.choices(RISK_TIERS, weights=[0.7, 0.2, 0.08, 0.02])[0],
            "country": random.choice(COUNTRIES)
        })
    df_customers = pd.DataFrame(customers)
    df_customers.to_csv(os.path.join(DATA_DIR, "customers.csv"), index=False)
    df_customers.to_parquet(os.path.join(DATA_DIR, "customers.parquet"), index=False)

    # 2. Accounts
    account_ids = [f"acc_{i:06d}" for i in range(1, NUM_ACCOUNTS + 1)]
    accounts = []
    for aid in account_ids:
        cid = random.choice(customer_ids)
        a_created = start_date - timedelta(days=random.randint(10, 300))
        accounts.append({
            "account_id": aid,
            "customer_id": cid,
            "account_type": random.choice(["CHECKING", "SAVINGS", "CREDIT"]),
            "created_at": a_created.isoformat(),
            "current_balance": round(random.uniform(100.0, 50000.0), 2)
        })
    df_accounts = pd.DataFrame(accounts)
    df_accounts.to_csv(os.path.join(DATA_DIR, "accounts.csv"), index=False)
    df_accounts.to_parquet(os.path.join(DATA_DIR, "accounts.parquet"), index=False)

    # 3. Merchants
    merchant_ids = [f"merch_{i:05d}" for i in range(1, NUM_MERCHANTS + 1)]
    merchants = []
    for mid in merchant_ids:
        m_created = start_date - timedelta(days=random.randint(60, 500))
        cat = random.choice(MERCHANT_CATS)
        base_risk = 0.8 if cat in ["GAMBLING", "CRYPTO"] else 0.1
        merchants.append({
            "merchant_id": mid,
            "merchant_category": cat,
            "risk_score": round(min(1.0, max(0.01, random.gauss(base_risk, 0.15))), 4),
            "country": random.choice(COUNTRIES),
            "created_at": m_created.isoformat()
        })
    df_merchants = pd.DataFrame(merchants)
    df_merchants.to_csv(os.path.join(DATA_DIR, "merchants.csv"), index=False)
    df_merchants.to_parquet(os.path.join(DATA_DIR, "merchants.parquet"), index=False)

    # 4. Transactions
    transactions = []
    # Create map of account -> customer for fast lookup
    acc_to_cust = dict(zip(df_accounts["account_id"], df_accounts["customer_id"]))

    for i in range(NUM_TRANSACTIONS):
        aid = random.choice(account_ids)
        cid = acc_to_cust[aid]
        mid = random.choice(merchant_ids)
        
        offset_seconds = random.randint(0, 30 * 24 * 3600)
        txn_time = start_date + timedelta(seconds=offset_seconds)
        
        amount = round(float(np.random.exponential(scale=120.0) + 1.0), 2)
        is_fraud = 0
        
        # Inject realistic fraud rules
        if amount > 2500.0 and random.random() < 0.35:
            is_fraud = 1
        elif random.random() < 0.015:
            is_fraud = 1

        transactions.append({
            "transaction_id": f"txn_{i:08d}",
            "customer_id": cid,
            "account_id": aid,
            "merchant_id": mid,
            "amount": amount,
            "timestamp": txn_time.isoformat(),
            "status": "APPROVED" if is_fraud == 0 or random.random() > 0.4 else "FAILED",
            "channel": random.choice(CHANNELS),
            "is_fraud": is_fraud
        })

    df_txns = pd.DataFrame(transactions)
    # Sort chronologically by timestamp
    df_txns.sort_values(by="timestamp", inplace=True)
    df_txns.to_csv(os.path.join(DATA_DIR, "transactions.csv"), index=False)
    df_txns.to_parquet(os.path.join(DATA_DIR, "transactions.parquet"), index=False)

    # 5. Fraud Events
    fraud_txns = df_txns[df_txns['is_fraud'] == 1].copy()
    fraud_events = []
    for idx, row in fraud_txns.iterrows():
        fraud_events.append({
            "event_id": f"fevt_{len(fraud_events):06d}",
            "transaction_id": row["transaction_id"],
            "customer_id": row["customer_id"],
            "confirmed_at": row["timestamp"],
            "fraud_type": random.choice(["ACCOUNT_TAKEOVER", "CARD_TESTING", "IDENTITY_THEFT", "CHARGEBACK_FRAUD"])
        })
    df_fraud_events = pd.DataFrame(fraud_events)
    df_fraud_events.to_csv(os.path.join(DATA_DIR, "fraud_events.csv"), index=False)
    df_fraud_events.to_parquet(os.path.join(DATA_DIR, "fraud_events.parquet"), index=False)

    print(f"Successfully generated:")
    print(f"  - Customers: {len(df_customers)}")
    print(f"  - Accounts: {len(df_accounts)}")
    print(f"  - Merchants: {len(df_merchants)}")
    print(f"  - Transactions: {len(df_txns)}")
    print(f"  - Fraud Events: {len(df_fraud_events)}")

if __name__ == "__main__":
    generate_seed_data()
