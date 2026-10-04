"""
FeatureHub REST API Application
FastAPI application delivering Feature Registry, Online/Offline Feature Retrieval, and Real-Time ML Inference.
"""

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from featurehub.registry.service import FeatureRegistryService
from featurehub.online_store.redis_store import RedisOnlineStore
from featurehub.computation.engine import compute_offline_features
from featurehub.inference.predictor import RealTimePredictor
from featurehub.feature_definitions.definitions import FeatureDefinition
from featurehub.integration.service import FeatureHubDataGuardIntegrator
from featurehub.integration.models import IntegratedPipelineResult

app = FastAPI(
    title="FeatureHub API",
    description="Real-Time ML Feature Store & Online Inference Platform",
    version="1.0.0"
)

registry_service = FeatureRegistryService()
online_store = RedisOnlineStore()
predictor = RealTimePredictor(online_store=online_store)
integrator = FeatureHubDataGuardIntegrator()
_latest_integrated_result = None

# Prometheus Metrics Definition
REQUEST_COUNT = Counter("featurehub_http_requests_total", "Total HTTP Requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("featurehub_http_request_duration_seconds", "HTTP Request Latency", ["endpoint"])
ONLINE_LOOKUP_LATENCY = Histogram("featurehub_online_lookup_seconds", "Online Redis Lookup Latency")

@app.middleware("http")
async def add_metrics_middleware(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    endpoint = request.url.path
    REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
    return response

class PredictionRequest(BaseModel):
    customer_id: str
    transaction_amount: float
    merchant_id: str
    timestamp: Optional[str] = None
    channel: str = "WEB"

@app.get("/health")
def health_check():
    return {
        "status": "HEALTHY",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "redis_connected": online_store.is_connected()
    }

@app.get("/features")
def list_features(entity: Optional[str] = None, group: Optional[str] = None):
    return registry_service.list_features(entity=entity, group=group)

@app.get("/features/{name}")
def get_feature(name: str):
    feat = registry_service.get_feature(name)
    if not feat:
        raise HTTPException(status_code=404, detail=f"Feature '{name}' not found.")
    return feat

@app.get("/features/{name}/history")
def get_feature_history(name: str):
    feat = registry_service.get_feature(name)
    if not feat:
        raise HTTPException(status_code=404, detail=f"Feature '{name}' not found.")
    return {
        "feature_name": name,
        "history": [
            {"version": "v1", "updated_at": feat.get("created_at"), "changes": "Initial definition"}
        ]
    }

@app.get("/feature-groups")
def list_feature_groups():
    return registry_service.list_groups()

@app.post("/features")
def register_feature(feat: FeatureDefinition):
    return registry_service.register_feature(feat)

@app.get("/online/features/{entity_id}")
def get_online_features(entity_id: str, entity_name: str = "customer"):
    start = time.time()
    data = online_store.get_online_features(entity_name=entity_name, entity_id=entity_id)
    ONLINE_LOOKUP_LATENCY.observe(time.time() - start)
    if not data:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found in online store.")
    return data

@app.get("/offline/features")
def get_offline_features(as_of_timestamp: Optional[str] = None):
    features = compute_offline_features(as_of_timestamp=as_of_timestamp)
    return {
        "as_of_timestamp": as_of_timestamp,
        "customer_records": len(features["customer_features"]),
        "merchant_records": len(features["merchant_features"])
    }

@app.post("/predict")
def predict_fraud_risk(req: PredictionRequest):
    ts = req.timestamp or datetime.now(timezone.utc).isoformat()
    result = predictor.predict_fraud_risk(
        customer_id=req.customer_id,
        transaction_amount=req.transaction_amount,
        merchant_id=req.merchant_id,
        timestamp=ts,
        channel=req.channel
    )
    return result


class IntegratedRunRequest(BaseModel):
    dataset_name: str = "customer_features"
    target_customer_id: str = "cust_0001"
    as_of_timestamp: Optional[str] = None
    inject_anomaly: Optional[str] = None
    allow_breaking: bool = False


@app.post("/pipeline/integrated-run", response_model=IntegratedPipelineResult)
def trigger_integrated_platform_run(req: IntegratedRunRequest):
    """
    Triggers end-to-end FeatureHub + DataGuard integration flow:
    Ingestion -> Computation -> Contracts -> Diff -> Quality -> Lineage -> Offline -> Redis -> ML Inference.
    """
    global _latest_integrated_result
    result = integrator.run_e2e_pipeline(
        dataset_name=req.dataset_name,
        target_customer_id=req.target_customer_id,
        as_of_timestamp=req.as_of_timestamp,
        inject_anomaly=req.inject_anomaly,
        allow_breaking=req.allow_breaking
    )
    _latest_integrated_result = result
    return result


@app.get("/pipeline/integrated-run/latest", response_model=Optional[IntegratedPipelineResult])
def get_latest_integrated_run():
    """Retrieves the most recent integrated platform run."""
    if not _latest_integrated_result:
        raise HTTPException(status_code=404, detail="No integrated platform runs recorded yet.")
    return _latest_integrated_result


@app.get("/metrics")
def get_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

