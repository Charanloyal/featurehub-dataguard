# DataGuard Incident Management Demo & Verification Scenarios

**Stage**: STAGE 3 — PHASE E  
**Script**: `scripts/incident_demo.py`  
**Database**: PostgreSQL 16 (`featurehub_dataguard_postgres`)  

---

## 1. Overview

The DataGuard Incident Management demo demonstrates real end-to-end incident generation, deduplication, owner assignment, severity classification, acknowledgment, resolution, and audit trail logging against live PostgreSQL infrastructure.

To run the interactive CLI demo:

```bash
python scripts/incident_demo.py
```

---

## 2. Tested Failure Scenarios

Each scenario synthesizes realistic failure conditions, validates them via Great Expectations or custom DataGuard checks, classifies them according to policy, routes ownership from contract metadata, and tests full lifecycle progression.

### Scenario 1: Null-Value Failure on Primary Identifier

- **Dataset**: `orders`
- **Condition**: Synthesized orders dataset containing null values in `order_id`.
- **Check**: `expect_column_values_to_not_be_null`
- **Result**:
  - **Incident ID**: `inc_29db0460395c47fb`
  - **Severity**: `HIGH`
  - **Assigned Owner**: `e-commerce-data-team` (derived from `orders.yaml` contract)
  - **Lifecycle**: `OPEN` $\to$ `ACKNOWLEDGED` (by `oncall_engineer`) $\to$ `RESOLVED` (by `lead_sre` with note: *"Backfilled missing order IDs"*).
  - **Audit Trail**: 3 immutable events recorded (`INCIDENT_CREATED`, `INCIDENT_ACKNOWLEDGED`, `INCIDENT_RESOLVED`).

---

### Scenario 2: Duplicate Primary Key

- **Dataset**: `transactions`
- **Condition**: Multiple duplicate transaction entries with `transaction_id = 'TXN_DUP_001'`.
- **Check**: `expect_column_values_to_be_unique`
- **Result**:
  - **Incident ID**: `inc_a4d3f5c5319d4538`
  - **Severity**: `CRITICAL` (Primary key corruption classified as CRITICAL)
  - **Assigned Owner**: `payments-team` (derived from `transactions.yaml` contract)
  - **Lifecycle**: `OPEN` $\to$ `ACKNOWLEDGED` (by `finops_bot`) $\to$ `RESOLVED` (by `dba_team` with note: *"Deduplicated ingestion pipeline records"*).
  - **Audit Trail**: Full event log persisted.

---

### Scenario 3: Invalid Enum Value

- **Dataset**: `orders`
- **Condition**: Order records with unapproved status `"REFUND_REQUESTED"` outside the contract allowed set `['PENDING', 'PROCESSING', 'COMPLETED', 'CANCELLED', 'RETURNED']`.
- **Check**: `expect_column_values_to_be_in_set`
- **Result**:
  - **Incident ID**: `inc_71c4c81a566649f8`
  - **Severity**: `MEDIUM`
  - **Assigned Owner**: `e-commerce-data-team`
  - **Lifecycle**: `OPEN` $\to$ `ACKNOWLEDGED` (by `triage_analyst`) $\to$ `RESOLVED` (by `app_dev` with note: *"Updated checkout service enum mappings"*).
  - **Audit Trail**: Full event log persisted.

---

### Scenario 4: Referential-Integrity Failure (Foreign Key Breach)

- **Dataset**: `orders` $\to$ `customers`
- **Condition**: `orders.customer_id` references non-existent foreign keys `['CUST_9999', 'CUST_8888']`.
- **Check**: `referential_integrity`
- **Result**:
  - **Incident ID**: `inc_20970a2560ce4175`
  - **Severity**: `CRITICAL` (Orphan foreign key records classified as CRITICAL)
  - **Assigned Owner**: `e-commerce-data-team`
  - **Observed Value**: `2 orphan records (40.0% orphan rate)`
  - **Lifecycle**: `OPEN` $\to$ `ACKNOWLEDGED` (by `catalog_guardian`) $\to$ `RESOLVED` (by `data_architect` with note: *"Resynced customer replication replica"*).
  - **Audit Trail**: Full event log persisted.

---

### Scenario 5: Stale Dataset (Freshness SLA Breach)

- **Dataset**: `transactions`
- **Condition**: Last record timestamp is 180 minutes old vs contract freshness SLA of 60 minutes.
- **Check**: `freshness_sla`
- **Result**:
  - **Incident ID**: `inc_ff8eeff1b9ec42bc`
  - **Severity**: `CRITICAL` ($\text{Delay} = 180\text{m} \ge 2\times 60\text{m}$, escalating to CRITICAL)
  - **Assigned Owner**: `payments-team`
  - **Observed Value**: `180.0 minutes latency`
  - **Lifecycle**: `OPEN` $\to$ `ACKNOWLEDGED` (by `pipeline_watcher`) $\to$ `RESOLVED` (by `oncall_infra` with note: *"Restarted Kafka consumer group connector"*).
  - **Audit Trail**: Full event log persisted.

---

## 3. Deduplication Demonstration

To confirm deduplication:

1. A failing check for `transactions.amount >= 0` is executed $\to$ Incident `inc_6a3e14bb183c480b` created (`OPEN`).
2. The exact same failing check runs again $\to$ Deduplication recognizes active signature `sig_902df59550b71457` $\to$ **Zero new incidents created**, existing ID returned.
3. Incident is transitioned to `RESOLVED`.
4. The failing check runs a third time $\to$ New incident created because previous incident was resolved.

---

## 4. Live Operational Metrics from PostgreSQL

At the conclusion of the demo, PostgreSQL calculates real SRE operational metrics:

- **Total Incidents Recorded**: `32`
- **Open Incidents**: `0`
- **Acknowledged Incidents**: `0`
- **Resolved Incidents**: `32`
- **Severity Breakdown**:
  - `CRITICAL`: 15
  - `HIGH`: 11
  - `MEDIUM`: 6
  - `LOW`: 0
  - `INFO`: 0
- **MTTA (Mean Time To Acknowledge)**: Real non-null value computed from live event deltas.
- **MTTR (Mean Time To Resolve)**: Real non-null value computed from live event deltas.
