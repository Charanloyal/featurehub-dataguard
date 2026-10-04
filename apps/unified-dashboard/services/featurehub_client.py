"""
FeatureHub Client Layer
Encapsulates HTTP API communication with graceful, transparent fallback
to direct Python services (FeatureRegistryService, RedisOnlineStore, RealTimePredictor).
"""

import time
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from apps.unified_dashboard.config import (
    FEATUREHUB_API_URL,
    API_TIMEOUT_SECONDS,
    HEALTH_CHECK_TIMEOUT_SECONDS,
    DEFAULT_ENTITY_ID,
)


class FeatureHubClient:
    def __init__(self, api_url: Optional[str] = None, timeout: float = API_TIMEOUT_SECONDS):
        self.api_url = (api_url or FEATUREHUB_API_URL).rstrip("/")
        self.timeout = timeout
        self._direct_registry = None
        self._direct_store = None
        self._direct_predictor = None

    def _get_registry(self):
        if self._direct_registry is None:
            from featurehub.registry.service import FeatureRegistryService
            self._direct_registry = FeatureRegistryService()
        return self._direct_registry

    def _get_store(self):
        if self._direct_store is None:
            from featurehub.online_store.redis_store import RedisOnlineStore
            self._direct_store = RedisOnlineStore()
        return self._direct_store

    def _get_predictor(self):
        if self._direct_predictor is None:
            from featurehub.inference.predictor import RealTimePredictor
            self._direct_predictor = RealTimePredictor(online_store=self._get_store())
        return self._direct_predictor

    def health(self) -> Dict[str, Any]:
        """Check FeatureHub API and datastore health with fallback."""
        start = time.time()
        try:
            r = requests.get(f"{self.api_url}/health", timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
            lat = round((time.time() - start) * 1000, 2)
            if r.status_code == 200:
                data = r.json()
                return {
                    "status": "HEALTHY",
                    "latency_ms": lat,
                    "redis_connected": data.get("redis_connected", True),
                    "mode": "HTTP API",
                    "last_checked": datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                }
            return {
                "status": "DEGRADED",
                "latency_ms": lat,
                "redis_connected": False,
                "mode": "HTTP API",
                "last_checked": datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            }
        except Exception:
            # Fallback to direct Redis & Registry check
            try:
                store = self._get_store()
                connected = store.is_connected()
                reg = self._get_registry()
                feats = reg.list_features()
                lat = round((time.time() - start) * 1000, 2)
                return {
                    "status": "HEALTHY" if connected and feats else "DEGRADED",
                    "latency_ms": lat,
                    "redis_connected": connected,
                    "mode": "DIRECT SERVICE",
                    "last_checked": datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                }
            except Exception as e:
                lat = round((time.time() - start) * 1000, 2)
                return {
                    "status": "DOWN",
                    "latency_ms": lat,
                    "redis_connected": False,
                    "mode": "UNAVAILABLE",
                    "error": str(e),
                    "last_checked": datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                }

    def list_features(self, entity: Optional[str] = None, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """List features with optional filtering by entity and group."""
        try:
            params = {}
            if entity and entity != "All":
                params["entity"] = entity
            if group and group != "All":
                params["group"] = group
            r = requests.get(f"{self.api_url}/features", params=params, timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        # Direct fallback
        ent = None if (not entity or entity == "All") else entity
        grp = None if (not group or group == "All") else group
        return self._get_registry().list_features(entity=ent, group=grp)

    def get_feature(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata for a specific feature."""
        try:
            r = requests.get(f"{self.api_url}/features/{feature_name}", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return self._get_registry().get_feature(feature_name)

    def list_groups(self) -> List[Dict[str, Any]]:
        """List registered feature groups."""
        try:
            r = requests.get(f"{self.api_url}/feature-groups", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return self._get_registry().list_groups()

    def get_online_features(self, entity_id: str, entity_name: str = "customer") -> Optional[Dict[str, Any]]:
        """Fetch online feature vector from Redis online store."""
        try:
            r = requests.get(f"{self.api_url}/online/features/{entity_id}?entity_name={entity_name}", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return self._get_store().get_online_features(entity_name=entity_name, entity_id=entity_id)

    def test_online_latency(self, entity_id: str = DEFAULT_ENTITY_ID, samples: int = 5) -> Dict[str, Any]:
        """Perform live benchmark of Redis point-lookup latency."""
        latencies = []
        store = self._get_store()
        for _ in range(samples):
            t0 = time.perf_counter()
            features = store.get_online_features(entity_name="customer", entity_id=entity_id)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)

        latencies.sort()
        p50 = round(latencies[len(latencies) // 2], 3)
        mean = round(sum(latencies) / len(latencies), 3)
        return {
            "p50_ms": p50,
            "mean_ms": mean,
            "min_ms": round(latencies[0], 3),
            "max_ms": round(latencies[-1], 3),
            "samples": samples,
            "entity_found": features is not None,
            "feature_count": len(features) if features else 0
        }

    def predict(
        self,
        customer_id: str,
        transaction_amount: float,
        merchant_id: str,
        channel: str = "WEB",
        timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """Perform real-time ML fraud prediction using online feature store."""
        payload = {
            "customer_id": customer_id,
            "transaction_amount": transaction_amount,
            "merchant_id": merchant_id,
            "channel": channel,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat()
        }
        try:
            r = requests.post(f"{self.api_url}/predict", json=payload, timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        # Fallback to direct predictor
        return self._get_predictor().predict_fraud_risk(
            customer_id=customer_id,
            transaction_amount=transaction_amount,
            merchant_id=merchant_id,
            channel=channel,
            timestamp=payload["timestamp"]
        )

    def run_pit_demo(self, customer_id: str = DEFAULT_ENTITY_ID, event_timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Execute Point-In-Time evaluation demonstrating leakage prevention."""
        from featurehub.point_in_time.pit_engine import PointInTimeJoinEngine
        engine = PointInTimeJoinEngine()
        return engine.evaluate_pit_demo(customer_id=customer_id, event_timestamp=event_timestamp)

    def run_integrated_pipeline(
        self,
        dataset: str = "customer_features",
        customer_id: str = DEFAULT_ENTITY_ID,
        anomaly: Optional[str] = None,
        allow_breaking: bool = False
    ) -> Dict[str, Any]:
        """Execute full 11-stage integrated FeatureHub + DataGuard pipeline."""
        payload = {
            "dataset": dataset,
            "customer_id": customer_id,
            "anomaly": anomaly,
            "allow_breaking": allow_breaking
        }
        try:
            r = requests.post(f"{self.api_url}/pipeline/integrated-run", json=payload, timeout=30.0)
            if r.status_code in [200, 422]:
                return r.json()
        except Exception:
            pass
        # Fallback to direct integrator
        from featurehub.integration.service import FeatureHubDataGuardIntegrator
        integrator = FeatureHubDataGuardIntegrator()
        result = integrator.run_integrated_pipeline(
            dataset_name=dataset,
            customer_id=customer_id,
            inject_anomaly=anomaly,
            allow_breaking=allow_breaking
        )
        return result.model_dump()

    def get_latest_pipeline_run(self) -> Optional[Dict[str, Any]]:
        """Retrieve status and metrics of the latest integrated pipeline run."""
        try:
            r = requests.get(f"{self.api_url}/pipeline/integrated-run/latest", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
