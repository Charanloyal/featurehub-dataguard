"""
DataGuard Incident Management Models.
Defines entity models, status lifecycles, severities, and audit trail events.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class IncidentSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentEventType(str, Enum):
    INCIDENT_CREATED = "INCIDENT_CREATED"
    INCIDENT_ACKNOWLEDGED = "INCIDENT_ACKNOWLEDGED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    INCIDENT_UPDATED = "INCIDENT_UPDATED"


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal lifecycle transition is attempted."""
    pass


class IncidentEvent(BaseModel):
    id: Optional[int] = None
    incident_id: str
    event_type: IncidentEventType
    old_status: Optional[IncidentStatus] = None
    new_status: IncidentStatus
    actor: str = "system"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: Optional[str] = None

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class Incident(BaseModel):
    incident_id: str
    dataset: str
    pipeline: str = "default_pipeline"
    pipeline_id: Optional[str] = None
    run_id: Optional[str] = None
    check_name: str
    expectation_type: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    owner: str
    title: str
    description: Optional[str] = None
    error_message: Optional[str] = None
    observed_value: Optional[str] = None
    expected_value: Optional[str] = None
    failure_signature: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    events: List[IncidentEvent] = []

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class IncidentSummary(BaseModel):
    total_incidents: int = 0
    open_incidents: int = 0
    acknowledged_incidents: int = 0
    resolved_incidents: int = 0
    critical_incidents: int = 0
    high_incidents: int = 0
    medium_incidents: int = 0
    low_incidents: int = 0
    oldest_open_incident: Optional[Dict[str, Any]] = None
    mtta_seconds: Optional[float] = None
    mttr_seconds: Optional[float] = None

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)
