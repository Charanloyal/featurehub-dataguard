# DataGuard Incident Management Architecture

**Stage**: STAGE 3 — PHASE E  
**Version**: 1.0.0  
**Engine**: PostgreSQL 16 + SQLAlchemy + FastAPI + Prometheus  
**Author**: Data Platform & Reliability Engineering Team  

---

## 1. Overview & System Architecture

The **DataGuard Incident Management System** provides deterministic, production-grade tracking and automated triage of data quality validation failures. In mission-critical data platforms, silent data corruption, freshness violations, or contract drifts undermine downstream ML models, financial analytics, and operational decisions.

DataGuard connects the automated **Data Quality Engine (Phase D)** directly to a persistent, deduplicated **Incident Management Engine (Phase E)**. When a real validation failure occurs in Great Expectations or custom validators (freshness, referential integrity), an incident is generated, classified by severity, routed to the dataset owner declared in the contract metadata, and tracked across an immutable audit trail.

```
+----------------------------------------------------------------------------------------------------+
|                                    DATAGUARD PHASE E PIPELINE                                      |
+----------------------------------------------------------------------------------------------------+
                                      Data Dataset Batch
                                              │
                                              ▼
                              Great Expectations Quality Runner
                                              │
                                              ▼
                                     QualityCheckResult
                                (Status: FAIL, Column, Check)
                                              │
                         ┌────────────────────┴────────────────────┐
                         ▼                                         ▼
                   Status == PASS                            Status == FAIL
                 (No Incident Created)                             │
                                                                   ▼
                                                       IncidentSeverityPolicy
                                                  (Maps check to severity & owner)
                                                                   │
                                                                   ▼
                                                       Deterministic Signature
                                                  SHA-256(dataset, check, col, exp)
                                                                   │
                                                                   ▼
                                                        Deduplication Check
                                             (Query active OPEN/ACK in PostgreSQL)
                                                                   │
                                          ┌────────────────────────┴────────────────────────┐
                                          ▼                                                 ▼
                                   Active Match Found                               No Active Match
                               (Return Existing Incident)                                   │
                                                                                            ▼
                                                                                  Create Persistent Incident
                                                                                  - status = OPEN
                                                                                  - audit event: INCIDENT_CREATED
                                                                                            │
                                                                                            ▼
                                                                                 PostgreSQL 16 Tables
                                                                                 - incidents
                                                                                 - incident_events
                                                                                            │
                                                                                            ▼
                                                                                   Prometheus Metrics
                                                                               (incidents_created_total)
                                                                                            │
                                                                                            ▼
                                                                                    FastAPI Endpoints
                                                                         (/incidents, /ack, /resolve, /summary)
```

---

## 2. Incident Data Model

All incidents and transition events are persisted in PostgreSQL 16 under atomic ACID transactions.

### 2.1 Table: `incidents`

| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `incident_id` | `VARCHAR(64)` | Primary Key (Format: `inc_<uuid_hex>`) |
| `dataset` | `VARCHAR(128)` | Target dataset name (Indexed) |
| `pipeline` | `VARCHAR(128)` | Pipeline identifier (Indexed) |
| `check_name` | `VARCHAR(256)` | Specific check or constraint name |
| `expectation_type`| `VARCHAR(256)` | Great Expectations / DataGuard expectation type |
| `severity` | `VARCHAR(32)` | `INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` (Indexed) |
| `status` | `VARCHAR(32)` | `OPEN`, `ACKNOWLEDGED`, `RESOLVED` (Indexed) |
| `owner` | `VARCHAR(128)` | Team/owner from contract metadata (Indexed) |
| `title` | `VARCHAR(256)` | Short, human-readable summary |
| `description` | `TEXT` | Detailed failure context and column information |
| `error_message` | `TEXT` | Exact failure or expectation output |
| `observed_value` | `TEXT` | Observed value from validation |
| `expected_value` | `TEXT` | Expected threshold or rule constraint |
| `failure_signature`| `VARCHAR(64)`| Deterministic deduplication hash (Indexed) |
| `created_at` | `TIMESTAMP WITH TZ` | Creation timestamp |
| `updated_at` | `TIMESTAMP WITH TZ` | Last status/metadata update timestamp |
| `acknowledged_at`| `TIMESTAMP WITH TZ` | Timestamp when first acknowledged |
| `resolved_at` | `TIMESTAMP WITH TZ` | Timestamp when resolved |

### 2.2 Table: `incident_events`

Maintains an append-only, immutable audit trail for governance, compliance, and post-mortem investigations.

| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `event_id` | `VARCHAR(64)` | Primary Key (Format: `evt_<uuid_hex>`) |
| `incident_id` | `VARCHAR(64)` | Foreign Key referencing `incidents.incident_id` (Indexed) |
| `event_type` | `VARCHAR(64)` | `INCIDENT_CREATED`, `INCIDENT_ACKNOWLEDGED`, `INCIDENT_RESOLVED`, etc. |
| `old_status` | `VARCHAR(32)` | Status before transition (`None` on creation) |
| `new_status` | `VARCHAR(32)` | Status after transition |
| `actor` | `VARCHAR(128)` | User, service account, or automation worker |
| `timestamp` | `TIMESTAMP WITH TZ` | Event timestamp |
| `notes` | `TEXT` | Optional context, triage notes, or resolution cause |

---

## 3. Failure Signature & Deduplication Engine

To prevent alert fatigue and database flooding, DataGuard computes a deterministic SHA-256 failure signature for every check failure.

### 3.1 Signature Formula

$$\text{Signature} = \text{"sig\_"} + \text{SHA256}(\text{dataset} \mathbin{\Vert} \text{check\_name} \mathbin{\Vert} \text{expectation\_type} \mathbin{\Vert} \text{column} \mathbin{\Vert} \text{pipeline})[:16]$$

- All input tokens are normalized to lowercase and stripped of leading/trailing whitespace.
- Optional fields (like `column`) are normalized to empty strings if absent.

### 3.2 Deduplication Lifecycle Rule

1. When a failure occurs, compute $\text{Signature}$.
2. Query PostgreSQL for an active incident matching:
   $$\text{failure\_signature} = \text{Signature} \quad \text{AND} \quad \text{status} \in \{\text{'OPEN'}, \text{'ACKNOWLEDGED'}\}$$
3. **If an active incident exists**:
   - Suppress creation of a new incident.
   - Return the active incident ID.
   - Increment Prometheus metric `incident_deduplicated_total`.
4. **If no active incident exists** (or previous instances are `RESOLVED`):
   - Create a fresh `OPEN` incident.
   - Record an initial `INCIDENT_CREATED` audit event.

---

## 4. Severity Policy

DataGuard centralizes severity classification in `IncidentSeverityPolicy`. Rather than relying on arbitrary developer input, failure severities are mapped strictly by failure category:

| Severity | Failure Categories & Triggers | Default SLA |
| :--- | :--- | :--- |
| **`CRITICAL`** | - Primary key / uniqueness corruption on primary identifier<br>- Foreign key referential integrity breaches (orphan records)<br>- Severe freshness breaches ($\text{Delay} \ge 2\times \text{SLA}$)<br>- Core contract schema violations | 1 Hour |
| **`HIGH`** | - Null values in non-nullable critical columns<br>- Distribution or range anomalies on financial/transaction amounts<br>- Uniqueness failure on secondary keys | 4 Hours |
| **`MEDIUM`** | - Moderate freshness delay ($\text{SLA} < \text{Delay} < 2\times \text{SLA}$)<br>- Set/enum membership constraint violations<br>- Secondary column type mismatches | 24 Hours |
| **`LOW`** | - Non-critical metadata deviations<br>- Row count deviations within warning tolerances | 48 Hours |
| **`INFO`** | - Advisory notices or non-blocking checks | Informational |

---

## 5. Owner Routing

Incident ownership is decoupled from manual triage. The `IncidentManager` inspects the data contract metadata associated with the failing dataset:

- If `owner` is defined in the data contract (e.g. `e-commerce-data-team`, `payments-team`, `ml-platform-team`), it is assigned directly as the incident owner.
- Domain fallback routing:
  - `transactions`, `payments` $\to$ `payments-team`
  - `orders`, `cart`, `checkout` $\to$ `e-commerce-data-team`
  - `customers`, `users` $\to$ `identity-team`
  - `customer_features`, `embeddings` $\to$ `ml-platform-team`
  - Unmapped datasets $\to$ `data-platform-team`

---

## 6. Incident State Machine & Transitions

The incident lifecycle follows a deterministic finite state machine (FSM):

```
     ┌──────────────┐
     │     OPEN     │
     └──────┬───────┘
            │
     ┌──────┴───────┐
     │              │
     ▼              ▼
┌──────────────┐    │
│ ACKNOWLEDGED │    │
└──────┬───────┘    │
       │            │
       ▼            │
┌──────────────┐    │
│   RESOLVED   │◄───┘
└──────────────┘
```

### Transition Validation Rules

1. **`OPEN` $\to$ `ACKNOWLEDGED`**: Valid. Records `acknowledged_at` timestamp and an `INCIDENT_ACKNOWLEDGED` event.
2. **`ACKNOWLEDGED` $\to$ `RESOLVED`**: Valid. Records `resolved_at` timestamp and an `INCIDENT_RESOLVED` event.
3. **`OPEN` $\to$ `RESOLVED`**: Permitted (e.g. auto-recovery or immediate patch). Populates both timestamps and records `INCIDENT_RESOLVED`.
4. **`RESOLVED` $\to$ `ACKNOWLEDGED`**: **REJECTED**. Raises `InvalidStateTransitionError`.
5. **`RESOLVED` $\to$ `OPEN`**: **REJECTED**. Once resolved, a failure generates a new incident rather than reopening a closed case.

---

## 7. Operational Reliability Metrics (MTTA & MTTR)

DataGuard calculates standard Site Reliability Engineering (SRE) operational metrics directly from PostgreSQL timestamps:

### 7.1 Mean Time To Acknowledge (MTTA)

$$\text{MTTA} = \frac{1}{N_{\text{ack}}} \sum_{i=1}^{N_{\text{ack}}} (\text{acknowledged\_at}_i - \text{created\_at}_i)$$

- Calculated only across incidents with non-null `acknowledged_at`.
- Returns `null` if insufficient data exists.

### 7.2 Mean Time To Resolve (MTTR)

$$\text{MTTR} = \frac{1}{N_{\text{res}}} \sum_{i=1}^{N_{\text{res}}} (\text{resolved\_at}_i - \text{created\_at}_i)$$

- Calculated only across incidents with non-null `resolved_at`.
- Returns `null` if insufficient data exists.

---

## 8. REST API Specifications

DataGuard exposes production FastAPI endpoints:

| Endpoint | Method | Query / Body Params | Description |
| :--- | :--- | :--- | :--- |
| `/incidents` | `GET` | `status`, `dataset`, `pipeline`, `severity`, `owner`, `limit` | List incidents filtered by status, dataset, severity, etc. |
| `/incidents/summary` | `GET` | None | Real-time aggregate count breakdown + MTTA/MTTR |
| `/incidents/{id}` | `GET` | Path: `incident_id` | Retrieve single incident including full audit event history |
| `/incidents/{id}/ack` | `POST` | `actor`, `notes` | Acknowledge incident (`OPEN` $\to$ `ACKNOWLEDGED`) |
| `/incidents/{id}/resolve`| `POST` | `actor`, `notes` | Resolve incident (`ACKNOWLEDGED`/`OPEN` $\to$ `RESOLVED`) |
| `/incidents/{id}/events` | `GET` | Path: `incident_id` | Retrieve chronological audit log for incident |

---

## 9. Prometheus Observability Metrics

Exported at `/metrics`:

- `incidents_created_total{severity, dataset}`: Total incidents created.
- `incidents_open_total`: Gauge of currently open incidents.
- `incidents_acknowledged_total`: Gauge of currently acknowledged incidents.
- `incidents_resolved_total`: Gauge of resolved incidents.
- `incident_creation_failures_total`: Counter tracking persistence errors.
- `incident_acknowledgement_seconds`: Histogram measuring acknowledgment duration.
- `incident_resolution_seconds`: Histogram measuring resolution duration.

---

## 10. Resilience & Error Handling

- **Database Unavailability**: If PostgreSQL is temporarily unreachable, incident creation logs error diagnostics and increments `incident_creation_failures_total`.
- **Integrity Guarantee**: A quality run is never marked as clean or passed if validation failed, even if downstream notification dispatch experiences a transient fault.
- **Race Condition Prevention**: Deduplication queries use transactional read-before-write with unique indexes on `incident_id` and indexed `failure_signature`.
