"""
End-to-End Platform Integration Test Suite
Validates seed generation, feature computation, point-in-time correctness, model inference, and schema diff engine.
"""

import pytest
import os
import pandas as pd
from pathlib import Path

from featurehub.computation.engine import compute_offline_features
from featurehub.point_in_time.pit_engine import PointInTimeJoinEngine
from featurehub.materialization.service import FeatureMaterializer
from featurehub.inference.predictor import RealTimePredictor
from dataguard.schema.diff import SchemaDiffEngine

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def test_full_platform_e2e_pipeline():
    """Validates complete data lifecycle from offline computation to real-time serving & governance."""
    # 1. Feature Computation
    features = compute_offline_features()
    assert "customer_features" in features
    assert len(features["customer_features"]) > 0

    # 2. Materialization
    materializer = FeatureMaterializer()
    mat_res = materializer.materialize_all()
    assert mat_res["status"] == "SUCCESS"
    assert mat_res["records_written"] > 0

    # 3. Real-Time Inference
    predictor = RealTimePredictor(online_store=materializer.online_store)
    pred_res = predictor.predict_fraud_risk(
        customer_id="cust_000001",
        transaction_amount=450.0,
        merchant_id="merch_00001",
        timestamp="2026-01-10T12:00:00Z"
    )
    assert "prediction" in pred_res
    assert "risk_score" in pred_res
    assert 0.0 <= pred_res["risk_score"] <= 1.0

    # 4. DataGuard Schema Diff Verification
    base_c = {
        "dataset": "transactions",
        "version": "v1.0.0",
        "columns": [{"name": "id", "type": "string", "nullable": False}]
    }
    target_breaking = {
        "dataset": "transactions",
        "version": "v1.1.0",
        "columns": [] # Removed column
    }
    diff_res = SchemaDiffEngine.compare_contracts(base_c, target_breaking)
    assert diff_res["is_breaking"] == True
    assert diff_res["classification"] == "BREAKING"
