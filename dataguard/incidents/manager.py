"""
DataGuard Incident Manager.
Core business logic for incident creation, deduplication, owner assignment,
lifecycle transitions, audit logging, and Prometheus metrics.
"""

import uuid
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from dataguard.contracts.registry import ContractRegistryService
from dataguard.quality.models import QualityCheckResult, QualityStatus
from dataguard.incidents.models import (
    Incident,
    IncidentEvent,
    IncidentStatus,
    IncidentSeverity,
    IncidentEventType,
    IncidentSummary,
    InvalidStateTransitionError
)
from dataguard.incidents.severity import IncidentSeverityPolicy
from dataguard.incidents.deduplication import compute_failure_signature
from dataguard.incidents.repository import IncidentRepository
from dataguard.metrics import (
    INCIDENTS_CREATED_TOTAL,
    INCIDENTS_OPEN_TOTAL,
    INCIDENTS_ACKNOWLEDGED_TOTAL,
    INCIDENTS_RESOLVED_TOTAL,
    INCIDENT_CREATION_FAILURES_TOTAL,
    INCIDENT_ACKNOWLEDGEMENT_SECONDS,
    INCIDENT_RESOLUTION_SECONDS
)


class IncidentManager:
    """
    Manages end-to-end incident operations for DataGuard.
    """

    def __init__(
        self,
        repository: Optional[IncidentRepository] = None,
        registry_service: Optional[ContractRegistryService] = None
    ):
        self.repository = repository or IncidentRepository()
        self.registry = registry_service or ContractRegistryService()

    def handle_check_failure(
        self,
        check: QualityCheckResult,
        dataset: str,
        pipeline: str = "default_pipeline",
        contract: Optional[Dict[str, Any]] = None,
        actor: str = "system"
    ) -> Optional[Incident]:
        """
        Evaluates a check result. If the check has failed, creates a persistent incident
        with owner attribution and deduplication.
        If the check passed, returns None.
        """
        # Rule: Do not create incidents for successful checks
        if check.success or check.status == QualityStatus.PASS:
            return None

        try:
            # 1. Resolve Dataset Owner from Contract Metadata
            owner = "data-platform-team"
            active_contract = contract
            if active_contract is None:
                try:
                    active_contract = self.registry.get_contract(dataset)
                except Exception:
                    pass

            if active_contract and active_contract.get("owner"):
                owner = active_contract["owner"]

            # 2. Determine Severity
            severity = IncidentSeverityPolicy.determine_severity(
                expectation_type=check.expectation_type,
                column=check.column,
                details=check.details,
                observed_value=check.observed_value
            )

            # 3. Compute Deterministic Failure Signature
            signature = compute_failure_signature(
                dataset=dataset,
                check_name=check.check_name,
                expectation_type=check.expectation_type,
                column=check.column,
                pipeline=pipeline
            )

            # 4. Deduplication: Check if active incident already exists
            active_incident = self.repository.find_active_by_signature(signature)
            if active_incident is not None:
                # Active failure already tracked; return existing incident without duplication
                return active_incident

            # 5. Build New Incident
            incident_id = f"inc_{uuid.uuid4().hex[:12]}"
            title = f"Data Quality Failure: {check.check_name} on {dataset}"
            description = (
                f"Check '{check.check_name}' ({check.expectation_type}) failed for dataset '{dataset}'.\n"
                f"Column: {check.column or 'N/A'}\n"
                f"Observed: {check.observed_value or 'N/A'}\n"
                f"Expected: {check.expected_value or 'N/A'}"
            )
            err_msg = str(check.observed_value or "Expectation assertion failed")

            now_str = datetime.now(timezone.utc).isoformat()
            incident = Incident(
                incident_id=incident_id,
                dataset=dataset,
                pipeline=pipeline,
                pipeline_id=pipeline,
                run_id=getattr(check, "run_id", None),
                check_name=check.check_name,
                expectation_type=check.expectation_type,
                severity=severity,
                status=IncidentStatus.OPEN,
                owner=owner,
                title=title,
                description=description,
                error_message=err_msg,
                observed_value=str(check.observed_value) if check.observed_value is not None else None,
                expected_value=str(check.expected_value) if check.expected_value is not None else None,
                failure_signature=signature,
                created_at=now_str,
                updated_at=now_str
            )

            initial_event = IncidentEvent(
                incident_id=incident_id,
                event_type=IncidentEventType.INCIDENT_CREATED,
                old_status=None,
                new_status=IncidentStatus.OPEN,
                actor=actor,
                timestamp=now_str,
                notes="Incident automatically created from failed data quality validation."
            )

            # 6. Persist to Database
            created_inc = self.repository.create_incident(incident, initial_event)

            # 7. Update Observability Metrics
            INCIDENTS_CREATED_TOTAL.labels(dataset=dataset, severity=severity.value).inc()
            INCIDENTS_OPEN_TOTAL.inc()

            return created_inc

        except Exception as e:
            INCIDENT_CREATION_FAILURES_TOTAL.labels(dataset=dataset).inc()
            raise e

    def acknowledge_incident(
        self,
        incident_id: str,
        actor: str = "engineer",
        notes: Optional[str] = None
    ) -> Incident:
        """Transitions incident from OPEN to ACKNOWLEDGED with audit trail and metrics."""
        inc = self.repository.get_incident(incident_id)
        if not inc:
            raise ValueError(f"Incident '{incident_id}' not found.")

        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()

        event = IncidentEvent(
            incident_id=incident_id,
            event_type=IncidentEventType.INCIDENT_ACKNOWLEDGED,
            old_status=inc.status,
            new_status=IncidentStatus.ACKNOWLEDGED,
            actor=actor,
            timestamp=now_str,
            notes=notes or "Incident acknowledged by engineer."
        )

        updated_inc = self.repository.update_status(
            incident_id=incident_id,
            new_status=IncidentStatus.ACKNOWLEDGED,
            event=event
        )

        # Update metrics
        INCIDENTS_ACKNOWLEDGED_TOTAL.labels(dataset=inc.dataset).inc()

        # Measure acknowledgement latency (MTTA sample)
        if inc.created_at:
            try:
                c_dt = datetime.fromisoformat(inc.created_at.replace("Z", "+00:00"))
                ack_secs = (now_dt - c_dt).total_seconds()
                if ack_secs >= 0:
                    INCIDENT_ACKNOWLEDGEMENT_SECONDS.labels(dataset=inc.dataset).observe(ack_secs)
            except Exception:
                pass

        return updated_inc

    def resolve_incident(
        self,
        incident_id: str,
        actor: str = "engineer",
        notes: Optional[str] = None
    ) -> Incident:
        """Transitions incident to RESOLVED with audit trail and metrics."""
        inc = self.repository.get_incident(incident_id)
        if not inc:
            raise ValueError(f"Incident '{incident_id}' not found.")

        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()

        event = IncidentEvent(
            incident_id=incident_id,
            event_type=IncidentEventType.INCIDENT_RESOLVED,
            old_status=inc.status,
            new_status=IncidentStatus.RESOLVED,
            actor=actor,
            timestamp=now_str,
            notes=notes or "Incident resolved by engineer."
        )

        updated_inc = self.repository.update_status(
            incident_id=incident_id,
            new_status=IncidentStatus.RESOLVED,
            event=event
        )

        # Update metrics
        INCIDENTS_RESOLVED_TOTAL.labels(dataset=inc.dataset).inc()
        INCIDENTS_OPEN_TOTAL.dec()

        # Measure resolution latency (MTTR sample)
        if inc.created_at:
            try:
                c_dt = datetime.fromisoformat(inc.created_at.replace("Z", "+00:00"))
                res_secs = (now_dt - c_dt).total_seconds()
                if res_secs >= 0:
                    INCIDENT_RESOLUTION_SECONDS.labels(dataset=inc.dataset).observe(res_secs)
            except Exception:
                pass

        return updated_inc

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self.repository.get_incident(incident_id)

    def list_incidents(
        self,
        dataset: Optional[str] = None,
        pipeline: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 100
    ) -> List[Incident]:
        return self.repository.list_incidents(
            dataset=dataset,
            pipeline=pipeline,
            severity=severity,
            status=status,
            owner=owner,
            limit=limit
        )

    def get_events(self, incident_id: str) -> List[IncidentEvent]:
        return self.repository.get_events(incident_id)

    def get_summary(self) -> IncidentSummary:
        return self.repository.get_summary()
