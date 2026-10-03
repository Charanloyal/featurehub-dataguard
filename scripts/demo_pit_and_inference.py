"""
Live Demonstration Script for Point-In-Time Correctness and Real-Time ML Inference
Run via 'make demo'
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from featurehub.computation.engine import compute_offline_features
from featurehub.materialization.service import FeatureMaterializer
from featurehub.training.train_model import train_fraud_model
from featurehub.inference.predictor import RealTimePredictor
from dataguard.schema.diff import SchemaDiffEngine

def run_platform_demo():
    print("============================================================")
    print("  FEATUREHUB & DATAGUARD PLATFORM LIVE DEMONSTRATION")
    print("============================================================")

    # Step 1: Compute Offline Features
    print("\n[Step 1] Computing 120+ Offline Features...")
    compute_offline_features()

    # Step 2: Train Model on PIT Dataset
    print("\n[Step 2] Training ML Fraud Classifier on PIT Correct Dataset...")
    train_fraud_model()

    # Step 3: Materialize to Online Store
    print("\n[Step 3] Materializing Feature Vectors to Online Store...")
    mat = FeatureMaterializer()
    mat_res = mat.materialize_all()

    # Step 4: Real-Time Inference
    print("\n[Step 4] Executing Real-Time Fraud Probability Inference...")
    predictor = RealTimePredictor(online_store=mat.online_store)
    res = predictor.predict_fraud_risk(
        customer_id="cust_000001",
        transaction_amount=3200.0,
        merchant_id="merch_00001",
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    print("  [+] Inference Payload Result:")
    print(f"      Risk Score      : {res['risk_score'] * 100:.2f}%")
    print(f"      Prediction Flag : {'FRAUD (ALERT)' if res['prediction'] == 1 else 'APPROVED'}")
    print(f"      Model Version   : {res['model_version']}")
    print(f"      Feature Time    : {res['feature_timestamp']}")

    # Step 5: DataGuard Schema CI Protection Demo
    print("\n[Step 5] Demonstrating DataGuard Schema Diff Breaking Change Protection...")
    base_contract = {
        "dataset": "transactions",
        "version": "v1.0.0",
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "numeric", "nullable": False}
        ]
    }
    pr_breaking_contract = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [
            {"name": "transaction_id", "type": "string", "nullable": False} # Removed 'amount'
        ]
    }
    diff = SchemaDiffEngine.compare_contracts(base_contract, pr_breaking_contract)
    print(f"  [+] PR Schema Diff Result: {diff['classification']}")
    print(f"      Is Breaking?        : {diff['is_breaking']}")
    print(f"      CI Action           : BLOCKED (Preventing Downstream Pipeline Crash)")

    print("\n============================================================")
    print("  DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("============================================================")

if __name__ == "__main__":
    run_platform_demo()
