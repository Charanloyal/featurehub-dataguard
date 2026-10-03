"""
DataGuard Quality Incidents Service.
Service facade managing lifecycle tracking, deduplication, audit trail, and resolution of quality incidents.
Backed by IncidentManager and PostgreSQL / SQLite repositories.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path

from dataguard.incidents.models import (
    Incident,
    IncidentEvent,
    IncidentStatus,
    IncidentSeverity,
    IncidentSummary,
    InvalidStateTransitionError
)
from dataguard.incidents.repository import IncidentRepository
from dataguard.incidents.manager import IncidentManager
from dataguard.quality.models import QualityCheckResult, QualityStatus


def _to_dict(model: Any) -> Dict[str, Any]:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)


class IncidentService:
    """
    DataGuard Incidents API Service facade.
    Provides backward-compatible method signatures while delegating to IncidentManager.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        db_url: Optional[str] = None,
        manager: Optional[IncidentManager] = None
    ):
        if manager is not None:
            self.manager = manager
        else:
            repo = IncidentRepository(db_path=db_path, db_url=db_url)
            self.manager = IncidentManager(repository=repo)

    def create_incident(
        self,
        dataset_name: str,
        check_name: str,
        severity: str = "HIGH",
        error_message: str = "",
        pipeline_name: str = "default_pipeline",
        owner: Optional[str] = None,
        expectation_type: str = "custom_check",
        column: Optional[str] = None,
        observed_value: Optional[str] = None,
        expected_value: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates or returns an active deduplicated incident."""
        adhoc_check = QualityCheckResult(
            run_id="manual",
            dataset=dataset_name,
            check_name=check_name,
            column=column,
            expectation_type=expectation_type,
            status=QualityStatus.FAIL,
            severity=IncidentSeverity(severity.upper()) if severity.upper() in IncidentSeverity.__members__ else IncidentSeverity.HIGH,
            observed_value=observed_value or error_message or "Failed",
            expected_value=expected_value or "Pass",
            success=False,
            pipeline=pipeline_name
        )
        contract_override = {"owner": owner} if owner else None
        inc = self.manager.handle_check_failure(
            check=adhoc_check,
            dataset=dataset_name,
            pipeline=pipeline_name,
            contract=contract_override
        )
        return _to_dict(inc)

    def list_incidents(
        self,
        status: Optional[str] = None,
        dataset: Optional[str] = None,
        pipeline: Optional[str] = None,
        severity: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Lists incidents with optional filters."""
        incidents = self.manager.list_incidents(
            status=status,
            dataset=dataset,
            pipeline=pipeline,
            severity=severity,
            owner=owner,
            limit=limit
        )
        return [_to_dict(inc) for inc in incidents]

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single incident by ID along with its event history."""
        inc = self.manager.get_incident(incident_id)
        return _to_dict(inc) if inc else None

    def update_status(self, incident_id: str, status: str, actor: str = "engineer", notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Transitions incident status to ACKNOWLEDGED or RESOLVED."""
        status_upper = status.upper()
        if status_upper == "ACKNOWLEDGED":
            res = self.manager.acknowledge_incident(incident_id, actor=actor, notes=notes)
            return _to_dict(res)
        elif status_upper == "RESOLVED":
            res = self.manager.resolve_incident(incident_id, actor=actor, notes=notes)
            return _to_dict(res)
        elif status_upper == "OPEN":
            # Reopening or no-op
            inc = self.manager.get_incident(incident_id)
            if not inc:
                return None
            if inc.status == IncidentStatus.OPEN:
                return _to_dict(inc)
            raise InvalidStateTransitionError(f"Cannot transition backwards to OPEN from {inc.status.value}.")
        else:
            raise ValueError(f"Unknown status '{status}'. Must be OPEN, ACKNOWLEDGED, or RESOLVED.")

    def acknowledge_incident(self, incident_id: str, actor: str = "engineer", notes: Optional[str] = None) -> Dict[str, Any]:
        inc = self.manager.acknowledge_incident(incident_id, actor=actor, notes=notes)
        return _to_dict(inc)

    def resolve_incident(self, incident_id: str, actor: str = "engineer", notes: Optional[str] = None) -> Dict[str, Any]:
        inc = self.manager.resolve_incident(incident_id, actor=actor, notes=notes)
        return _to_dict(inc)

    def get_events(self, incident_id: str) -> List[Dict[str, Any]]:
        events = self.manager.get_events(incident_id)
        return [_to_dict(ev) for ev in events]

    def get_summary(self) -> Dict[str, Any]:
        summary = self.manager.get_summary()
        return _to_dict(summary)
