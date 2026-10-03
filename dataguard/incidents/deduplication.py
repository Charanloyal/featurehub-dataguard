"""
DataGuard Incident Deduplication & Failure Signature Engine.
Computes deterministic signatures for data quality failures to prevent duplicate incident floods.
"""

import hashlib
from typing import Optional, List
from dataguard.incidents.models import Incident, IncidentStatus


def compute_failure_signature(
    dataset: str,
    check_name: str,
    expectation_type: str,
    column: Optional[str] = None,
    pipeline: str = "default_pipeline"
) -> str:
    """
    Computes a canonical, deterministic failure signature.
    
    Rule:
    canonical_string = f"{dataset.strip().lower()}|{pipeline.strip().lower()}|{check_name.strip().lower()}|{expectation_type.strip().lower()}|{(column or '').strip().lower()}"
    signature = "sig_" + sha256(canonical_string)[:16]
    
    Guarantees:
    - Same failure on same dataset & pipeline always produces identical signature.
    - Independent across different datasets or columns.
    """
    ds_norm = (dataset or "").strip().lower()
    pipe_norm = (pipeline or "default_pipeline").strip().lower()
    check_norm = (check_name or "").strip().lower()
    exp_norm = (expectation_type or "").strip().lower()
    col_norm = (column or "").strip().lower()

    canonical_str = f"{ds_norm}|{pipe_norm}|{check_norm}|{exp_norm}|{col_norm}"
    digest = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()[:16]
    return f"sig_{digest}"


def is_active_duplicate(signature: str, existing_incidents: List[Incident]) -> Optional[Incident]:
    """
    Checks if an incident with the given signature is currently active (OPEN or ACKNOWLEDGED).
    Returns the active Incident if a duplicate exists, else None.
    """
    for inc in existing_incidents:
        if inc.failure_signature == signature and inc.status in {IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED}:
            return inc
    return None
