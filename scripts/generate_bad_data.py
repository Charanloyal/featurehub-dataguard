"""
Generates synthetic anomalous/corrupted data to test DataGuard Quality Incidents and validation failures.
"""
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

def generate_corrupted_transactions():
    print("Injecting invalid transactions (missing fields, negative amounts)...")
    bad_txns = [
        {"transaction_id": "bad_001", "customer_id": None, "amount": -50.0, "timestamp": "2026-01-01T00:00:00Z", "status": "INVALID_STATUS"},
        {"transaction_id": "bad_002", "customer_id": "cust_000001", "amount": 99999999.0, "timestamp": "2026-01-01T00:00:00Z", "status": "APPROVED"}
    ]
    df_bad = pd.DataFrame(bad_txns)
    df_bad.to_csv(DATA_DIR / "corrupted_transactions.csv", index=False)
    print("Corrupted transaction data injected.")

if __name__ == "__main__":
    generate_corrupted_transactions()
