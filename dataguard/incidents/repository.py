"""
DataGuard Incident Repository.
Handles persistent storage and retrieval for incidents and incident events in PostgreSQL and SQLite.
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    select,
    desc,
    asc,
    func,
    and_
)
from sqlalchemy.engine import Engine

from dataguard.contracts.registry import get_default_db_url, create_db_engine
from dataguard.incidents.models import (
    Incident,
    IncidentEvent,
    IncidentStatus,
    IncidentSeverity,
    IncidentEventType,
    IncidentSummary,
    InvalidStateTransitionError
)


class IncidentRepository:
    """
    Persistence layer for Incident Management.
    Connects to PostgreSQL in production and SQLite in testing.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        db_path: Optional[Path] = None,
        engine: Optional[Engine] = None
    ):
        if engine is not None:
            self.engine = engine
            self.db_url = str(engine.url)
        elif db_url is not None:
            self.db_url = db_url
            self.engine = create_db_engine(self.db_url)
        elif db_path is not None:
            self.db_url = f"sqlite:///{Path(db_path).resolve().as_posix()}"
            self.engine = create_engine(self.db_url)
        else:
            self.db_url = get_default_db_url()
            self.engine = create_db_engine(self.db_url)

        self.metadata = MetaData()
        self._define_schema()
        self._init_db()

    def _define_schema(self):
        self.incidents_table = Table(
            "incidents",
            self.metadata,
            Column("incident_id", String(64), primary_key=True),
            Column("dataset", String(128), nullable=False, index=True),
            Column("pipeline", String(128), default="default_pipeline"),
            Column("pipeline_id", String(128), nullable=True),
            Column("run_id", String(64), nullable=True, index=True),
            Column("check_name", String(256), nullable=False),
            Column("expectation_type", String(128), nullable=False),
            Column("severity", String(32), nullable=False, index=True),
            Column("status", String(32), nullable=False, default="OPEN", index=True),
            Column("owner", String(128), nullable=False, index=True),
            Column("title", String(256), nullable=False),
            Column("description", Text, nullable=True),
            Column("error_message", Text, nullable=True),
            Column("observed_value", Text, nullable=True),
            Column("expected_value", Text, nullable=True),
            Column("failure_signature", String(128), nullable=False, index=True),
            Column("created_at", DateTime(timezone=True), server_default=func.now()),
            Column("updated_at", DateTime(timezone=True), server_default=func.now()),
            Column("acknowledged_at", DateTime(timezone=True), nullable=True),
            Column("resolved_at", DateTime(timezone=True), nullable=True),
        )

        self.incident_events_table = Table(
            "incident_events",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("incident_id", String(64), ForeignKey("incidents.incident_id", ondelete="CASCADE"), nullable=False, index=True),
            Column("event_type", String(64), nullable=False),
            Column("old_status", String(32), nullable=True),
            Column("new_status", String(32), nullable=False),
            Column("actor", String(128), default="system"),
            Column("timestamp", DateTime(timezone=True), server_default=func.now()),
            Column("notes", Text, nullable=True),
        )

    def _init_db(self):
        self.metadata.create_all(self.engine)

    def create_incident(self, incident: Incident, initial_event: IncidentEvent) -> Incident:
        """Persists a new incident and records the initial INCIDENT_CREATED audit event in one transaction."""
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            conn.execute(
                self.incidents_table.insert().values(
                    incident_id=incident.incident_id,
                    dataset=incident.dataset,
                    pipeline=incident.pipeline,
                    pipeline_id=incident.pipeline_id or incident.pipeline,
                    run_id=incident.run_id,
                    check_name=incident.check_name,
                    expectation_type=incident.expectation_type,
                    severity=incident.severity.value,
                    status=incident.status.value,
                    owner=incident.owner,
                    title=incident.title,
                    description=incident.description,
                    error_message=incident.error_message,
                    observed_value=incident.observed_value,
                    expected_value=incident.expected_value,
                    failure_signature=incident.failure_signature,
                    created_at=now,
                    updated_at=now
                )
            )

            conn.execute(
                self.incident_events_table.insert().values(
                    incident_id=incident.incident_id,
                    event_type=initial_event.event_type.value,
                    old_status=initial_event.old_status.value if initial_event.old_status else None,
                    new_status=initial_event.new_status.value,
                    actor=initial_event.actor,
                    timestamp=now,
                    notes=initial_event.notes
                )
            )

        return self.get_incident(incident.incident_id)

    def find_active_by_signature(self, signature: str) -> Optional[Incident]:
        """Finds any active incident (OPEN or ACKNOWLEDGED) with the given failure signature."""
        with self.engine.connect() as conn:
            stmt = (
                select(self.incidents_table.c.incident_id)
                .where(
                    and_(
                        self.incidents_table.c.failure_signature == signature,
                        self.incidents_table.c.status.in_(["OPEN", "ACKNOWLEDGED"])
                    )
                )
                .limit(1)
            )
            row = conn.execute(stmt).fetchone()
            if not row:
                return None
            return self.get_incident(row[0])

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Retrieves an incident by incident_id along with its audit events."""
        with self.engine.connect() as conn:
            stmt = select(self.incidents_table).where(self.incidents_table.c.incident_id == incident_id)
            row = conn.execute(stmt).mappings().fetchone()
            if not row:
                return None

            stmt_events = (
                select(self.incident_events_table)
                .where(self.incident_events_table.c.incident_id == incident_id)
                .order_by(asc(self.incident_events_table.c.timestamp), asc(self.incident_events_table.c.id))
            )
            event_rows = conn.execute(stmt_events).mappings().fetchall()
            events = []
            for er in event_rows:
                ts = er["timestamp"]
                events.append(IncidentEvent(
                    id=er["id"],
                    incident_id=er["incident_id"],
                    event_type=IncidentEventType(er["event_type"]),
                    old_status=IncidentStatus(er["old_status"]) if er["old_status"] else None,
                    new_status=IncidentStatus(er["new_status"]),
                    actor=er["actor"],
                    timestamp=ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                    notes=er["notes"]
                ))

            created_at = row["created_at"]
            updated_at = row["updated_at"]
            ack_at = row["acknowledged_at"]
            res_at = row["resolved_at"]

            return Incident(
                incident_id=row["incident_id"],
                dataset=row["dataset"],
                pipeline=row["pipeline"],
                pipeline_id=row.get("pipeline_id") or row.get("pipeline"),
                run_id=row.get("run_id"),
                check_name=row["check_name"],
                expectation_type=row["expectation_type"],
                severity=IncidentSeverity(row["severity"]),
                status=IncidentStatus(row["status"]),
                owner=row["owner"],
                title=row["title"],
                description=row["description"],
                error_message=row["error_message"],
                observed_value=row["observed_value"],
                expected_value=row["expected_value"],
                failure_signature=row["failure_signature"],
                created_at=created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                updated_at=updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at),
                acknowledged_at=ack_at.isoformat() if (ack_at and hasattr(ack_at, "isoformat")) else (str(ack_at) if ack_at else None),
                resolved_at=res_at.isoformat() if (res_at and hasattr(res_at, "isoformat")) else (str(res_at) if res_at else None),
                events=events
            )

    def update_status(
        self,
        incident_id: str,
        new_status: IncidentStatus,
        event: IncidentEvent
    ) -> Incident:
        """Transitions incident status and records audit event in a single transaction."""
        inc = self.get_incident(incident_id)
        if not inc:
            raise ValueError(f"Incident '{incident_id}' not found.")

        old_status = inc.status

        # Validate Lifecycle State Machine:
        # OPEN -> ACKNOWLEDGED
        # OPEN -> RESOLVED
        # ACKNOWLEDGED -> RESOLVED
        if old_status == IncidentStatus.RESOLVED:
            raise InvalidStateTransitionError(f"Cannot transition incident '{incident_id}' from RESOLVED to {new_status.value}.")
        if old_status == new_status:
            return inc
        if old_status == IncidentStatus.ACKNOWLEDGED and new_status == IncidentStatus.OPEN:
            raise InvalidStateTransitionError(f"Cannot transition incident '{incident_id}' backwards from ACKNOWLEDGED to OPEN.")

        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            upd_vals = {
                "status": new_status.value,
                "updated_at": now
            }
            if new_status == IncidentStatus.ACKNOWLEDGED:
                upd_vals["acknowledged_at"] = now
            elif new_status == IncidentStatus.RESOLVED:
                upd_vals["resolved_at"] = now

            conn.execute(
                self.incidents_table.update()
                .where(self.incidents_table.c.incident_id == incident_id)
                .values(**upd_vals)
            )

            conn.execute(
                self.incident_events_table.insert().values(
                    incident_id=incident_id,
                    event_type=event.event_type.value,
                    old_status=old_status.value,
                    new_status=new_status.value,
                    actor=event.actor,
                    timestamp=now,
                    notes=event.notes
                )
            )

        return self.get_incident(incident_id)

    def list_incidents(
        self,
        dataset: Optional[str] = None,
        pipeline: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 100
    ) -> List[Incident]:
        """Queries incidents matching filters, ordered by created_at DESC."""
        with self.engine.connect() as conn:
            stmt = select(self.incidents_table.c.incident_id).order_by(desc(self.incidents_table.c.created_at))
            if dataset:
                stmt = stmt.where(self.incidents_table.c.dataset == dataset)
            if pipeline:
                stmt = stmt.where(self.incidents_table.c.pipeline == pipeline)
            if severity:
                stmt = stmt.where(self.incidents_table.c.severity == severity.upper())
            if status:
                stmt = stmt.where(self.incidents_table.c.status == status.upper())
            if owner:
                stmt = stmt.where(self.incidents_table.c.owner == owner)
            stmt = stmt.limit(limit)

            rows = conn.execute(stmt).fetchall()
            results = []
            for r in rows:
                item = self.get_incident(r[0])
                if item:
                    results.append(item)
            return results

    def get_events(self, incident_id: str) -> List[IncidentEvent]:
        """Retrieves audit trail events for an incident."""
        inc = self.get_incident(incident_id)
        return inc.events if inc else []

    def get_summary(self) -> IncidentSummary:
        """
        Dynamically computes system-wide incident summary, including counts by status and severity,
        oldest open incident, and MTTA / MTTR from stored timestamps.
        """
        with self.engine.connect() as conn:
            # Aggregate status counts
            all_incidents = conn.execute(
                select(
                    self.incidents_table.c.incident_id,
                    self.incidents_table.c.status,
                    self.incidents_table.c.severity,
                    self.incidents_table.c.created_at,
                    self.incidents_table.c.acknowledged_at,
                    self.incidents_table.c.resolved_at
                )
            ).mappings().fetchall()

            total = len(all_incidents)
            open_count = 0
            ack_count = 0
            res_count = 0
            crit_count = 0
            high_count = 0
            med_count = 0
            low_count = 0

            oldest_open = None
            oldest_open_time = None

            ack_durations = []
            res_durations = []

            for row in all_incidents:
                st = row["status"]
                sev = row["severity"]

                if st == IncidentStatus.OPEN.value:
                    open_count += 1
                    c_time = row["created_at"]
                    if oldest_open_time is None or (c_time and c_time < oldest_open_time):
                        oldest_open_time = c_time
                        oldest_open = {
                            "incident_id": row["incident_id"],
                            "created_at": c_time.isoformat() if hasattr(c_time, "isoformat") else str(c_time)
                        }
                elif st == IncidentStatus.ACKNOWLEDGED.value:
                    ack_count += 1
                elif st == IncidentStatus.RESOLVED.value:
                    res_count += 1

                if sev == IncidentSeverity.CRITICAL.value:
                    crit_count += 1
                elif sev == IncidentSeverity.HIGH.value:
                    high_count += 1
                elif sev == IncidentSeverity.MEDIUM.value:
                    med_count += 1
                elif sev == IncidentSeverity.LOW.value:
                    low_count += 1

                # MTTA calculation: acknowledged_at - created_at
                if row["acknowledged_at"] and row["created_at"]:
                    try:
                        diff = (row["acknowledged_at"] - row["created_at"]).total_seconds()
                        if diff >= 0:
                            ack_durations.append(diff)
                    except Exception:
                        pass

                # MTTR calculation: resolved_at - created_at
                if row["resolved_at"] and row["created_at"]:
                    try:
                        diff = (row["resolved_at"] - row["created_at"]).total_seconds()
                        if diff >= 0:
                            res_durations.append(diff)
                    except Exception:
                        pass

            mtta = round(sum(ack_durations) / len(ack_durations), 2) if ack_durations else None
            mttr = round(sum(res_durations) / len(res_durations), 2) if res_durations else None

            return IncidentSummary(
                total_incidents=total,
                open_incidents=open_count,
                acknowledged_incidents=ack_count,
                resolved_incidents=res_count,
                critical_incidents=crit_count,
                high_incidents=high_count,
                medium_incidents=med_count,
                low_incidents=low_count,
                oldest_open_incident=oldest_open,
                mtta_seconds=mtta,
                mttr_seconds=mttr
            )
