"""
Real-Time Feature Retrieval & ML Inference Engine
Retrieves online feature vectors from Redis at request time and computes real-time fraud probability scores.
"""

import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import joblib
except ImportError:
    joblib = None

from featurehub.online_store.redis_store import RedisOnlineStore
from featurehub.training.train_model import MODEL_FEATURE_COLS

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
MODEL_PATH = DATA_DIR / "models" / "fraud_model.joblib"
META_PATH = DATA_DIR / "models" / "fraud_model_metadata.json"

class RealTimePredictor:
    def __init__(self, online_store: Optional[RedisOnlineStore] = None):
        self.online_store = online_store or RedisOnlineStore()
        self.model = None
        self.model_version = "v1.0.0"
        self._load_model()

    def _load_model(self):
        if joblib and MODEL_PATH.exists():
            try:
                self.model = joblib.load(MODEL_PATH)
            except Exception:
                self.model = None
        if META_PATH.exists():
            try:
                with open(META_PATH, "r") as f:
                    meta = json.load(f)
                    self.model_version = meta.get("model_version", "v1.0.0")
            except Exception:
                pass

    def predict_fraud_risk(
        self,
        customer_id: str,
        transaction_amount: float,
        merchant_id: str,
        timestamp: str,
        channel: str = "WEB"
    ) -> Dict[str, Any]:
        """
        Fetches online features from Redis for customer_id, combines them with transaction inputs,
        and outputs real-time fraud probability score.
        """
        # 1. Real-Time Feature Retrieval from Redis Online Store
        online_data = self.online_store.get_online_features(entity_name="customer", entity_id=customer_id)
        
        if not online_data:
            feature_vector = {col: 0.0 for col in MODEL_FEATURE_COLS}
            feat_ts = timestamp
        else:
            feature_vector = online_data.get("features", {})
            feat_ts = online_data.get("feature_timestamp", timestamp)

        # Build model feature array
        input_data = {}
        for col in MODEL_FEATURE_COLS:
            input_data[col] = float(feature_vector.get(col, 0.0))

        # 2. ML Model Inference
        if self.model is not None:
            df_input = pd.DataFrame([input_data])
            risk_score = float(self.model.predict_proba(df_input)[0, 1])
        else:
            # Rule-based fraud probability score computation
            burst = input_data.get("burst_txn_count_10min", 0)
            failed = input_data.get("cust_failed_txn_count_24h", 0)
            amount_score = min(0.5, (transaction_amount / 2000.0) * 0.3)
            risk_score = min(0.99, max(0.02, amount_score + burst * 0.25 + failed * 0.20))

        prediction = 1 if risk_score >= 0.50 else 0

        return {
            "prediction": prediction,
            "risk_score": round(risk_score, 4),
            "model_version": self.model_version,
            "feature_timestamp": feat_ts,
            "features_used": input_data
        }
