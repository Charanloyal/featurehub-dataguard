"""
DataGuard Dataset Catalog & Quality Test Fixtures.
Provides realistic datasets matching production contracts,
and deterministic bad-data fixtures for failure scenario testing.
"""

import os
import uuid
import random
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
OFFLINE_DIR = DATA_DIR / "offline_store"


class DatasetCatalog:
    """
    Manages loading and generation of realistic datasets for all 25 production contracts.
    Provides deterministic clean and bad-data fixtures for quality testing.
    """

    @classmethod
    def load_dataset(cls, dataset_name: str) -> pd.DataFrame:
        """Loads dataset from raw parquet/csv or generates realistic data if not yet materialized."""
        # 1. Check data/raw/*.parquet or *.csv
        parquet_path = RAW_DIR / f"{dataset_name}.parquet"
        if parquet_path.exists():
            return pd.read_parquet(parquet_path)

        csv_path = RAW_DIR / f"{dataset_name}.csv"
        if csv_path.exists():
            return pd.read_csv(csv_path)

        # 2. Check offline store
        offline_path = OFFLINE_DIR / f"{dataset_name}.parquet"
        if offline_path.exists():
            return pd.read_parquet(offline_path)

        # 3. Generate on-the-fly realistic dataset matching contract
        return cls.generate_clean_dataset(dataset_name, num_rows=100)

    @classmethod
    def generate_clean_dataset(cls, dataset_name: str, num_rows: int = 100) -> pd.DataFrame:
        """Generates pristine, 100% compliant dataset matching contract schema."""
        now = datetime.now(timezone.utc)

        # Helper to get parent keys if available
        def _get_parent_keys(parent_name: str, key_col: str, fallback_prefix: str, count: int) -> List[str]:
            p_path = RAW_DIR / f"{parent_name}.parquet"
            if p_path.exists():
                try:
                    df_p = pd.read_parquet(p_path)
                    if key_col in df_p.columns:
                        return df_p[key_col].dropna().astype(str).tolist()
                except Exception:
                    pass
            return [f"{fallback_prefix}_{i:06d}" for i in range(1, count + 1)]

        if dataset_name == "customers":
            return pd.DataFrame({
                "customer_id": [f"cust_{i:06d}" for i in range(1, num_rows + 1)],
                "created_at": [now - timedelta(days=random.randint(1, 365)) for _ in range(num_rows)],
                "kyc_status": [random.choice(["VERIFIED", "PENDING", "REJECTED"]) for _ in range(num_rows)],
                "risk_tier": [random.choice(["LOW", "MEDIUM", "HIGH"]) for _ in range(num_rows)],
                "country": [random.choice(["US", "GB", "DE", "FR", "CA"]) for _ in range(num_rows)]
            })

        elif dataset_name == "products":
            return pd.DataFrame({
                "product_id": [f"prod_{i:04d}" for i in range(1, num_rows + 1)],
                "name": [f"Product Title {i}" for i in range(1, num_rows + 1)],
                "category": [random.choice(["Electronics", "Fashion", "Home", "Sports", "Beauty"]) for _ in range(num_rows)],
                "price": [round(random.uniform(5.0, 999.0), 2) for _ in range(num_rows)],
                "stock_quantity": [random.randint(5, 500) for _ in range(num_rows)]
            })

        elif dataset_name == "orders":
            valid_custs = _get_parent_keys("customers", "customer_id", "cust", 50)
            return pd.DataFrame({
                "order_id": [f"ord_{i:06d}" for i in range(1, num_rows + 1)],
                "customer_id": [random.choice(valid_custs) for _ in range(num_rows)],
                "order_total": [round(random.uniform(10.0, 2500.0), 2) for _ in range(num_rows)],
                "currency": [random.choice(["USD", "EUR", "GBP", "CAD"]) for _ in range(num_rows)],
                "created_at": [now - timedelta(minutes=random.randint(1, 55)) for _ in range(num_rows)]
            })

        elif dataset_name == "order_items":
            valid_orders = [f"ord_{i:06d}" for i in range(1, max(2, num_rows // 2))]
            valid_prods = [f"prod_{i:04d}" for i in range(1, max(2, num_rows // 2))]
            return pd.DataFrame({
                "item_id": [f"item_{i:06d}" for i in range(1, num_rows + 1)],
                "order_id": [random.choice(valid_orders) for _ in range(num_rows)],
                "product_id": [random.choice(valid_prods) for _ in range(num_rows)],
                "quantity": [random.randint(1, 10) for _ in range(num_rows)],
                "unit_price": [round(random.uniform(5.0, 250.0), 2) for _ in range(num_rows)]
            })

        elif dataset_name == "payments":
            valid_orders = [f"ord_{i:06d}" for i in range(1, max(2, num_rows // 2))]
            return pd.DataFrame({
                "payment_id": [f"pay_{i:06d}" for i in range(1, num_rows + 1)],
                "order_id": [random.choice(valid_orders) for _ in range(num_rows)],
                "payment_method": [random.choice(["CREDIT_CARD", "DEBIT_CARD", "PAYPAL", "WIRE"]) for _ in range(num_rows)],
                "status": [random.choice(["SETTLED", "PENDING", "REFUNDED"]) for _ in range(num_rows)],
                "settled_at": [now - timedelta(minutes=random.randint(1, 25)) for _ in range(num_rows)]
            })

        elif dataset_name == "accounts":
            valid_custs = _get_parent_keys("customers", "customer_id", "cust", 50)
            return pd.DataFrame({
                "account_id": [f"acc_{i:06d}" for i in range(1, num_rows + 1)],
                "customer_id": [random.choice(valid_custs) for _ in range(num_rows)],
                "account_type": [random.choice(["CHECKING", "SAVINGS", "INVESTMENT", "CREDIT"]) for _ in range(num_rows)],
                "created_at": [now - timedelta(days=random.randint(1, 300)) for _ in range(num_rows)],
                "current_balance": [round(random.uniform(10.0, 50000.0), 2) for _ in range(num_rows)]
            })

        elif dataset_name == "merchants":
            return pd.DataFrame({
                "merchant_id": [f"merch_{i:05d}" for i in range(1, num_rows + 1)],
                "merchant_category": [random.choice(["RETAIL", "TRAVEL", "ENTERTAINMENT", "GROCERY"]) for _ in range(num_rows)],
                "risk_score": [round(random.uniform(0.01, 0.95), 4) for _ in range(num_rows)],
                "country": [random.choice(["US", "GB", "DE", "FR", "CA"]) for _ in range(num_rows)],
                "created_at": [now - timedelta(days=random.randint(1, 300)) for _ in range(num_rows)]
            })

        elif dataset_name == "transactions":
            valid_custs = _get_parent_keys("customers", "customer_id", "cust", 50)
            valid_accs = _get_parent_keys("accounts", "account_id", "acc", 50)
            valid_merchs = _get_parent_keys("merchants", "merchant_id", "merch", 20)
            return pd.DataFrame({
                "transaction_id": [f"txn_{i:08d}" for i in range(1, num_rows + 1)],
                "customer_id": [random.choice(valid_custs) for _ in range(num_rows)],
                "account_id": [random.choice(valid_accs) for _ in range(num_rows)],
                "merchant_id": [random.choice(valid_merchs) for _ in range(num_rows)],
                "amount": [round(random.uniform(1.0, 5000.0), 2) for _ in range(num_rows)],
                "timestamp": [now - timedelta(minutes=random.randint(1, 10)) for _ in range(num_rows)],
                "status": [random.choice(["APPROVED", "DECLINED"]) for _ in range(num_rows)],
                "channel": [random.choice(["ONLINE", "POS", "MOBILE", "ATM"]) for _ in range(num_rows)],
                "is_fraud": [random.choice([0, 1]) for _ in range(num_rows)]
            })

        elif dataset_name == "fraud_events":
            valid_txns = _get_parent_keys("transactions", "transaction_id", "txn", 50)
            valid_custs = _get_parent_keys("customers", "customer_id", "cust", 50)
            return pd.DataFrame({
                "event_id": [f"fevt_{i:06d}" for i in range(1, num_rows + 1)],
                "transaction_id": [random.choice(valid_txns) for _ in range(num_rows)],
                "customer_id": [random.choice(valid_custs) for _ in range(num_rows)],
                "fraud_type": [random.choice(["ACCOUNT_TAKEOVER", "CARD_TESTING", "IDENTITY_THEFT", "CHARGEBACK_FRAUD"]) for _ in range(num_rows)],
                "confirmed_at": [now - timedelta(minutes=random.randint(1, 15)) for _ in range(num_rows)]
            })

        # Generic generator for feature tables
        cols = {
            "entity_id": [f"ent_{i:05d}" for i in range(1, num_rows + 1)],
            "created_at": [now - timedelta(minutes=random.randint(1, 30)) for _ in range(num_rows)],
            "feature_val": [round(random.uniform(0.0, 100.0), 2) for _ in range(num_rows)]
        }
        return pd.DataFrame(cols)

    # -------------------------------------------------------------
    # Failure Scenarios / Deterministic Bad-Data Fixtures (Req. 12)
    # -------------------------------------------------------------

    @classmethod
    def bad_orders_nulls(cls, num_rows: int = 50) -> pd.DataFrame:
        """Injects NULL values into mandatory non-nullable columns (order_total, currency)."""
        df = cls.generate_clean_dataset("orders", num_rows=num_rows)
        df.loc[0:4, "order_total"] = np.nan
        df.loc[5:9, "currency"] = None
        return df

    @classmethod
    def bad_orders_duplicates(cls, num_rows: int = 50) -> pd.DataFrame:
        """Injects duplicate primary keys into order_id."""
        df = cls.generate_clean_dataset("orders", num_rows=num_rows)
        # Duplicate the first order_id across first 5 rows
        df.loc[1:4, "order_id"] = df.loc[0, "order_id"]
        return df

    @classmethod
    def bad_transactions_negative_amounts(cls, num_rows: int = 50) -> pd.DataFrame:
        """Injects negative amounts into transactions (violates min: 0.0)."""
        df = cls.generate_clean_dataset("transactions", num_rows=num_rows)
        df.loc[0:4, "amount"] = -250.0
        return df

    @classmethod
    def bad_payments_invalid_status(cls, num_rows: int = 50) -> pd.DataFrame:
        """Injects disallowed enum status values (violates allowed_values)."""
        df = cls.generate_clean_dataset("payments", num_rows=num_rows)
        df.loc[0:4, "status"] = "INVALID_BITCOIN_ESCROW"
        return df

    @classmethod
    def bad_orders_missing_customer(cls, num_rows: int = 50) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Injects non-existent customer_ids into orders (violates referential integrity)."""
        orders_df = cls.generate_clean_dataset("orders", num_rows=num_rows)
        customers_df = cls.generate_clean_dataset("customers", num_rows=num_rows)
        # Point some orders to orphan customer IDs
        orders_df.loc[0:4, "customer_id"] = "cust_orphan_ghost_9999"
        return orders_df, customers_df

    @classmethod
    def stale_dataset(cls, dataset_name: str = "orders", days_old: int = 14, hours_old: Optional[int] = None) -> pd.DataFrame:
        """Creates dataset with timestamps far older than freshness SLA."""
        df = cls.generate_clean_dataset(dataset_name, num_rows=50)
        delta = timedelta(hours=hours_old) if hours_old is not None else timedelta(days=days_old)
        old_time = datetime.now(timezone.utc) - delta
        for col in df.columns:
            if "time" in col or "date" in col or "at" in col:
                df[col] = old_time
        return df
