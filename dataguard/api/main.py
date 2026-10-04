"""
DataGuard REST API Application
FastAPI application delivering Contract Registry, Schema Diff Engine, Data Quality Validation, Incidents & Lineage.
"""

import os
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
import time
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Response, status, Body
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from dataguard.contracts.registry import (
    ContractRegistryService, 
    DuplicateVersionError, 
    ContractNotFoundError
)
from dataguard.contracts.validator import ContractValidationError
from dataguard.metrics import (
    CONTRACT_REGISTRY_REQUEST_COUNT,
    DATAGUARD_REQUEST_COUNT,
    DATAGUARD_LATENCY,
    INCIDENTS_COUNT
)
from dataguard.schema.diff import SchemaDiffEngine
from dataguard.schema.models import SchemaDiffRequest, SchemaDiffResult
from dataguard.quality.service import DataQualityEngine
from dataguard.quality.models import (
    QualityRunResult,
    QualitySummaryResponse,
    QualityCheckResult
)
from dataguard.incidents.service import IncidentService
from dataguard.incidents.models import (
    Incident,
    IncidentEvent,
    IncidentStatus,
    IncidentSeverity,
    IncidentSummary,
    InvalidStateTransitionError
)
from dataguard.lineage.service import LineageService
from dataguard.ci.models import (
    GatingVerdict,
    GatingChange,
    ContractGatingResult,
    PRGatingSummary
)
from dataguard.ci.gate import CICDContractGatingEngine

class CIGatingRequest(BaseModel):
    baseline_contract: Optional[Dict[str, Any]] = None
    target_contract: Dict[str, Any]
    dataset_name: Optional[str] = None
    file_path: Optional[str] = None
    validate_quality: bool = True

class PRGatingItem(BaseModel):
    baseline_contract: Optional[Dict[str, Any]] = None
    target_contract: Dict[str, Any]
    file_path: Optional[str] = None

class BatchPRGatingRequest(BaseModel):
    contracts: List[PRGatingItem]
    allow_breaking: bool = False
    validate_quality: bool = True

app = FastAPI(
    title="DataGuard API",
    description="Data Quality, Contracts, Schema Drift & Lineage Platform",
    version="1.0.0"
)

registry_service = ContractRegistryService()
quality_engine = DataQualityEngine()
incident_service = IncidentService()
lineage_service = LineageService()


@app.middleware("http")
async def add_metrics_middleware(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    endpoint = request.url.path
    if endpoint.startswith("/contracts") or endpoint == "/health":
        CONTRACT_REGISTRY_REQUEST_COUNT.labels(
            endpoint=endpoint, 
            method=request.method, 
            status=response.status_code
        ).inc()
    DATAGUARD_REQUEST_COUNT.labels(endpoint=endpoint, status=response.status_code).inc()
    DATAGUARD_LATENCY.labels(endpoint=endpoint).observe(duration)
    return response


@app.get("/health")
def health_check():
    contracts = registry_service.list_contracts()
    return {
        "status": "HEALTHY",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_contracts": len(contracts)
    }

@app.post("/contracts", status_code=status.HTTP_201_CREATED)
def register_contract(contract: Dict[str, Any]):
    try:
        result = registry_service.register_contract(contract)
        return result
    except ContractValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except DuplicateVersionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.get("/contracts")
def list_contracts(
    owner: Optional[str] = Query(None, description="Filter by owner"),
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, DEPRECATED, DRAFT)"),
    dataset: Optional[str] = Query(None, description="Filter by dataset name"),
    version: Optional[str] = Query(None, description="Filter by version string")
):
    return registry_service.list_contracts(owner=owner, status=status, dataset=dataset, version=version)

@app.get("/contracts/{name}")
def get_contract(name: str):
    contract = registry_service.get_contract(name)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contract for dataset '{name}' not found.")
    return contract

@app.get("/contracts/{name}/versions")
def get_contract_versions(name: str):
    versions = registry_service.get_contract_versions(name)
    if not versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No contract versions found for dataset '{name}'.")
    return versions

@app.get("/contracts/{name}/versions/{version}")
def get_contract_version(name: str, version: str):
    contract = registry_service.get_contract(name, version=version)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Contract for dataset '{name}' version '{version}' not found."
        )
    return contract

@app.post("/contracts/{name}/validate")
def validate_contract(name: str, contract: Dict[str, Any]):
    if contract.get("dataset") and contract.get("dataset") != name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
            detail=f"Dataset name mismatch: pathParam '{name}' vs payload dataset '{contract.get('dataset')}'"
        )
    is_valid, errors = registry_service.validate_contract_structure(contract)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
            detail=f"Contract validation failed: {'; '.join(errors)}"
        )
    return {
        "dataset": name,
        "valid": True,
        "errors": []
    }

@app.post("/schema/diff", response_model=SchemaDiffResult)
def compute_schema_diff(req: SchemaDiffRequest):
    # Mode 1: Compare registered versions in PostgreSQL (dataset, from_version, to_version)
    if req.dataset or (req.from_version and req.to_version):
        if not req.dataset:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Field 'dataset' is required for version comparison."
            )
        if not req.from_version or not req.to_version:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Both 'from_version' and 'to_version' are required for version comparison."
            )
        if req.from_version == req.to_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot compare identical version '{req.from_version}' to itself. 'from_version' and 'to_version' must be distinct."
            )
        try:
            diff_result = SchemaDiffEngine.compare_versions(
                registry_service=registry_service,
                dataset=req.dataset,
                from_version=req.from_version,
                to_version=req.to_version
            )
            return diff_result
        except ContractNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # Mode 2: Direct contract payload comparison
    if req.baseline_contract is not None and req.target_contract is not None:
        if not isinstance(req.baseline_contract, dict) or not isinstance(req.target_contract, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="baseline_contract and target_contract must be dictionary objects."
            )
        base_ds = req.baseline_contract.get("dataset")
        tgt_ds = req.target_contract.get("dataset")
        if base_ds and tgt_ds and base_ds != tgt_ds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dataset mismatch: baseline '{base_ds}' does not match target '{tgt_ds}'."
            )
        try:
            return SchemaDiffEngine.compare_contracts(req.baseline_contract, req.target_contract)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid contract payload: {str(e)}"
            )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Must provide either (dataset, from_version, to_version) or (baseline_contract, target_contract)."
    )

@app.get("/contracts/{name}/diff")
def compare_contract_versions(name: str, v1: str = Query(..., description="Baseline version tag"), v2: Optional[str] = Query(None, description="Target version tag (defaults to latest)")):
    c1 = registry_service.get_contract(name, version=v1)
    if not c1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contract for dataset '{name}' version '{v1}' not found.")
    
    c2 = registry_service.get_contract(name, version=v2)
    if not c2:
        target_label = v2 if v2 else "latest"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contract for dataset '{name}' version '{target_label}' not found.")
        
    return SchemaDiffEngine.compare_contracts(c1, c2)

@app.post("/contracts/{name}/diff/table")
def compare_contract_with_table(name: str, table_name: Optional[str] = None, version: Optional[str] = None):
    contract = registry_service.get_contract(name, version=version)
    if not contract:
        ver_label = version if version else "latest"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contract for dataset '{name}' ({ver_label}) not found.")
    
    target_table = table_name or name
    try:
        diff_res = SchemaDiffEngine.compare_contract_to_table(contract, target_table)
        return diff_res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/lineage")
def get_lineage():
    return lineage_service.get_lineage_graph()

# ==========================================
# Incident Management Endpoints (Phase E)
# ==========================================

@app.get("/incidents")
def list_incidents(
    dataset: Optional[str] = Query(None, description="Filter by dataset name"),
    pipeline: Optional[str] = Query(None, description="Filter by pipeline name"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)"),
    status: Optional[str] = Query(None, description="Filter by status (OPEN, ACKNOWLEDGED, RESOLVED)"),
    owner: Optional[str] = Query(None, description="Filter by owner"),
    limit: int = Query(100, description="Max incidents to return")
):
    try:
        return incident_service.list_incidents(
            status=status,
            dataset=dataset,
            pipeline=pipeline,
            severity=severity,
            owner=owner,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/incidents/summary")
def get_incidents_summary():
    try:
        return incident_service.get_summary()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    inc = incident_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")
    return inc


@app.post("/incidents/{incident_id}/ack")
def acknowledge_incident_endpoint(
    incident_id: str,
    payload: Optional[Dict[str, Any]] = Body(None)
):
    actor = payload.get("actor", "engineer") if payload else "engineer"
    notes = payload.get("notes") if payload else None
    try:
        return incident_service.acknowledge_incident(incident_id, actor=actor, notes=notes)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/incidents/{incident_id}/acknowledge")
def acknowledge_incident_legacy(
    incident_id: str,
    payload: Optional[Dict[str, Any]] = Body(None)
):
    return acknowledge_incident_endpoint(incident_id, payload)


@app.post("/incidents/{incident_id}/resolve")
def resolve_incident_endpoint(
    incident_id: str,
    payload: Optional[Dict[str, Any]] = Body(None)
):
    actor = payload.get("actor", "engineer") if payload else "engineer"
    notes = payload.get("notes") if payload else None
    try:
        return incident_service.resolve_incident(incident_id, actor=actor, notes=notes)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/incidents/{incident_id}/events")
def get_incident_events_endpoint(incident_id: str):
    inc = incident_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")
    return incident_service.get_events(incident_id)

# ==========================================
# Data Quality Engine Endpoints (Phase D)
# ==========================================

@app.post("/quality/validate/{dataset}", response_model=QualityRunResult)
def validate_dataset_endpoint(
    dataset: str,
    version: Optional[str] = Query(None, description="Contract version (defaults to latest)"),
    pipeline: str = Query("dataguard-api", description="Pipeline identifier"),
    payload: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = Body(None, description="Optional custom dataset payload to validate")
):
    df = None
    if payload is not None:
        try:
            if isinstance(payload, list):
                df = pd.DataFrame(payload)
            elif isinstance(payload, dict):
                if "records" in payload and isinstance(payload["records"], list):
                    df = pd.DataFrame(payload["records"])
                else:
                    df = pd.DataFrame(payload)
            else:
                raise ValueError("Payload must be a list of records or a dictionary.")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid dataset payload: {str(e)}"
            )

    try:
        result = quality_engine.validate_dataset(
            dataset_name=dataset,
            df=df,
            version=version,
            pipeline=pipeline
        )
        return result
    except ContractNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database or validation execution failure: {str(e)}")


@app.get("/quality/results")
def list_quality_results(
    dataset: Optional[str] = Query(None, description="Filter by dataset name"),
    status: Optional[str] = Query(None, description="Filter by check status (PASS, FAIL, WARNING)"),
    pipeline: Optional[str] = Query(None, description="Filter by pipeline name"),
    limit: int = Query(100, description="Max check results to return")
):
    try:
        return quality_engine.list_results(
            dataset=dataset,
            status=status,
            pipeline=pipeline,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/quality/summary", response_model=QualitySummaryResponse)
def get_quality_summary():
    try:
        return quality_engine.get_summary()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/quality/{dataset}", response_model=QualityRunResult)
def get_dataset_quality_latest(dataset: str):
    # Verify dataset exists in registry or in run store
    contract = registry_service.get_contract(dataset)
    latest = quality_engine.get_latest_run(dataset)
    if not latest:
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown dataset '{dataset}'."
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No quality validation records found for dataset '{dataset}'."
        )
    return latest


@app.get("/quality/{dataset}/latest", response_model=QualityRunResult)
def get_dataset_quality_latest_explicit(dataset: str):
    contract = registry_service.get_contract(dataset)
    latest = quality_engine.get_latest_run(dataset)
    if not latest:
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown dataset '{dataset}'."
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No quality validation records found for dataset '{dataset}'."
        )
    return latest


@app.get("/quality/{dataset}/history", response_model=List[QualityRunResult])
def get_dataset_quality_history(dataset: str, limit: int = Query(20, description="Max historical runs")):
    contract = registry_service.get_contract(dataset)
    history = quality_engine.get_history(dataset, limit=limit)
    if not history and not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown dataset '{dataset}'."
        )
    return history


# ==========================================
# OpenLineage Data Lineage Endpoints (Phase F)
# ==========================================

@app.get("/lineage/graph")
def get_lineage_graph_endpoint():
    """
    Returns full machine-readable graph topology (nodes & edges) dynamically built from PostgreSQL.
    """
    try:
        return lineage_service.get_lineage_graph()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/lineage/runs/{run_id}")
def get_lineage_run_endpoint(run_id: str):
    """
    Retrieves execution metadata, inputs, and outputs for a specific pipeline run.
    """
    run = lineage_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lineage run '{run_id}' not found.")
    return run


@app.get("/lineage/pipelines/{pipeline_id}")
def get_pipeline_runs_endpoint(pipeline_id: str, limit: int = Query(50, description="Max historical runs")):
    """
    Lists historical runs for a specific pipeline.
    """
    return lineage_service.get_pipeline_runs(pipeline_id, limit=limit)


@app.post("/lineage/events", status_code=status.HTTP_201_CREATED)
def ingest_lineage_event_endpoint(event: Dict[str, Any] = Body(...)):
    """
    Ingests an OpenLineage standard RunEvent payload into PostgreSQL.
    """
    try:
        return lineage_service.ingest_event(event)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to ingest OpenLineage event: {str(e)}")


@app.get("/lineage/{dataset}")
def get_dataset_lineage_endpoint(dataset: str):
    """
    Returns complete lineage summary (upstream, downstream, pipelines) for a dataset.
    """
    summary = lineage_service.get_dataset_lineage(dataset)
    if not summary:
        # Check if dataset exists in contracts
        contract = registry_service.get_contract(dataset)
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown dataset '{dataset}'.")
        return {
            "dataset": dataset,
            "namespace": "default",
            "producing_pipelines": [],
            "consuming_pipelines": [],
            "upstream_datasets": [],
            "downstream_datasets": [],
            "latest_run_id": None,
            "last_updated": None
        }
    return summary


@app.get("/lineage/{dataset}/upstream")
def get_dataset_upstream_lineage(dataset: str, depth: int = Query(5, description="Max traversal depth")):
    """
    Traverses upstream dependencies feeding into the dataset.
    """
    return lineage_service.get_upstream(dataset, depth=depth)


@app.get("/lineage/{dataset}/downstream")
def get_dataset_downstream_lineage(dataset: str, depth: int = Query(5, description="Max traversal depth")):
    """
    Traverses downstream dependencies consuming the dataset.
    """
    return lineage_service.get_downstream(dataset, depth=depth)


@app.get("/lineage/{dataset}/columns")
def get_dataset_column_lineage(dataset: str, column: Optional[str] = Query(None, description="Filter by column name")):
    """
    Returns column-level lineage transformations contributing to a dataset.
    """
    return lineage_service.get_column_lineage(dataset, column=column)


@app.get("/incidents/{incident_id}/lineage")
def get_incident_lineage_context(incident_id: str):
    """
    Correlates an incident to its upstream pipeline lineage context.
    """
    inc = incident_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found.")
    
    upstream = lineage_service.get_upstream(inc.get("dataset"), depth=5)
    return {
        "incident_id": incident_id,
        "dataset": inc.get("dataset"),
        "pipeline": inc.get("pipeline"),
        "run_id": inc.get("run_id"),
        "upstream_datasets": upstream.get("upstream_datasets", []),
        "upstream_pipelines": upstream.get("pipelines", [])
    }


# Pipeline Orchestration Endpoints (Phase G)
from dataguard.pipelines.repository import PipelineRepository
from dataguard.pipelines.registry import PipelineRegistryService
from dataguard.pipelines.models import PipelineConfig, PipelineRun, PipelineSummary, PipelineHealth

pipeline_repo = PipelineRepository()
pipeline_registry = PipelineRegistryService(repository=pipeline_repo)

# Automatically sync standard pipelines on startup
try:
    pipeline_registry.sync_all_pipelines()
except Exception:
    pass


@app.get("/pipelines", response_model=List[PipelineConfig])
def list_pipelines(
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, PAUSED, DEPRECATED)"),
    owner: Optional[str] = Query(None, description="Filter by owner team")
):
    """
    Lists all registered data pipelines with optional filtering.
    """
    try:
        return pipeline_repo.list_pipelines(status=status, owner=owner)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/pipelines/summary", response_model=PipelineSummary)
def get_pipeline_summary():
    """
    Computes dynamic platform summary aggregated from real metadata and run history.
    """
    try:
        return pipeline_repo.get_pipeline_summary()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/pipelines/{pipeline_id}", response_model=PipelineConfig)
def get_pipeline_details(pipeline_id: str):
    """
    Retrieves configuration and metadata for a specific pipeline.
    """
    try:
        pipe = pipeline_repo.get_pipeline(pipeline_id)
        if not pipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline '{pipeline_id}' not found."
            )
        return pipe
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/pipelines/{pipeline_id}/runs", response_model=List[PipelineRun])
def list_pipeline_runs(pipeline_id: str, limit: int = Query(50, description="Max runs to return")):
    """
    Lists execution run history for a given pipeline.
    """
    try:
        pipe = pipeline_repo.get_pipeline(pipeline_id)
        if not pipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline '{pipeline_id}' not found."
            )
        return pipeline_repo.list_runs(pipeline_id=pipeline_id, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/pipelines/{pipeline_id}/latest", response_model=PipelineRun)
def get_latest_pipeline_run(pipeline_id: str):
    """
    Retrieves the most recent execution run for a pipeline.
    """
    try:
        pipe = pipeline_repo.get_pipeline(pipeline_id)
        if not pipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline '{pipeline_id}' not found."
            )
        latest = pipeline_repo.get_latest_run(pipeline_id)
        if not latest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No execution runs found for pipeline '{pipeline_id}'."
            )
        return latest
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/pipelines/{pipeline_id}/health", response_model=PipelineHealth)
def get_pipeline_health_status(pipeline_id: str):
    """
    Evaluates health score, active incidents, and freshness state of a pipeline.
    """
    try:
        health = pipeline_repo.get_pipeline_health(pipeline_id)
        if not health:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline '{pipeline_id}' not found."
            )
        return health
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/metrics")
def get_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --------------------------------------------------------------------------
# Phase H: CI/CD Pull Request Contract Compatibility & Quality Gating
# --------------------------------------------------------------------------

@app.post("/ci/gate", response_model=ContractGatingResult)
def evaluate_ci_contract_gate(payload: CIGatingRequest):
    """
    Evaluates a single contract modification for CI/CD Pull Request gating:
    Contract Validation -> Schema Diff -> Quality Regression -> Merge Verdict (SAFE/WARNING/BREAKING).
    """
    try:
        return CICDContractGatingEngine.evaluate_contract_change(
            baseline_contract=payload.baseline_contract,
            target_contract=payload.target_contract,
            dataset_name=payload.dataset_name,
            file_path=payload.file_path,
            validate_quality=payload.validate_quality
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/ci/gate/pr", response_model=PRGatingSummary)
def evaluate_ci_batch_pr(payload: BatchPRGatingRequest):
    """
    Evaluates multiple contracts in a PR batch, generating a GitHub-ready markdown summary and exit code.
    """
    try:
        items = [
            (c.baseline_contract, c.target_contract, c.file_path or "inline.yaml")
            for c in payload.contracts
        ]
        return CICDContractGatingEngine.evaluate_pr(
            contracts_to_evaluate=items,
            allow_breaking=payload.allow_breaking,
            validate_quality=payload.validate_quality
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


