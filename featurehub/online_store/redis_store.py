"""
Redis Online Feature Store Handler
Handles low-latency key-value writes and reads for real-time feature retrieval during ML inference.
"""

import os
import json
import time
from typing import Dict, Any, Optional, List
import redis
from datetime import datetime, timezone

# In-memory fallback dictionary for testing environments without an active Redis server
_LOCAL_REDIS_FALLBACK: Dict[str, str] = {}

class RedisOnlineStore:
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", 6379))
        self.client = None
        self._connected = False
        self._connect()

    def _connect(self):
        for h in [self.host, "127.0.0.1", "localhost"]:
            if not h: continue
            try:
                self.client = redis.Redis(
                    host=h,
                    port=self.port,
                    db=0,
                    decode_responses=True,
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0,
                    protocol=2
                )
                self.client.ping()
                self._connected = True
                self.host = h
                return
            except Exception:
                self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def put_online_features(
        self,
        entity_name: str,
        entity_id: str,
        feature_vector: Dict[str, Any],
        feature_timestamp: str,
        feature_version: str = "v1"
    ):
        key = f"featurehub:{entity_name}:{entity_id}"
        payload = {
            "entity_id": entity_id,
            "entity_name": entity_name,
            "features": feature_vector,
            "feature_timestamp": feature_timestamp,
            "feature_version": feature_version,
            "source": "FeatureHub-Materializer",
            "materialized_at": datetime.now(timezone.utc).isoformat()
        }
        json_str = json.dumps(payload)

        if self._connected and self.client:
            try:
                self.client.set(key, json_str)
                return
            except Exception:
                self._connected = False

        # Fallback to local memory dictionary
        _LOCAL_REDIS_FALLBACK[key] = json_str

    def get_online_features(self, entity_name: str, entity_id: str) -> Optional[Dict[str, Any]]:
        key = f"featurehub:{entity_name}:{entity_id}"
        json_str = None

        if self._connected and self.client:
            try:
                json_str = self.client.get(key)
            except Exception:
                self._connected = False

        if not json_str:
            json_str = _LOCAL_REDIS_FALLBACK.get(key)

        if not json_str:
            return None

        data = json.loads(json_str)
        
        # Calculate freshness in minutes
        feat_time = pd.to_datetime(data["feature_timestamp"], utc=True) if "pd" in globals() else datetime.fromisoformat(data["feature_timestamp"].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        freshness_minutes = round((now - feat_time).total_seconds() / 60.0, 2)
        data["freshness_minutes"] = max(0.0, freshness_minutes)
        return data

    def batch_get_online_features(self, entity_name: str, entity_ids: List[str]) -> List[Optional[Dict[str, Any]]]:
        return [self.get_online_features(entity_name, eid) for eid in entity_ids]
