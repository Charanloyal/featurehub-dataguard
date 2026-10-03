# DataGuard Contract Registry Architecture & Specification

## Overview

The DataGuard Contract Registry serves as the authoritative, persistent source of truth for data contracts across the platform. It enables data engineering and ML teams to register, discover, version, validate, and query contract definitions for all streaming and batch datasets.

---

## 1. Registry Architecture

```
                               ┌─────────────────────────────┐
                               │   dataguard/contracts/*.yaml │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │ scripts/register_contracts.py│
                               └──────────────┬──────────────┘
                                              │
                                              ▼
┌──────────────────────────┐   ┌─────────────────────────────┐
│ ContractValidator        ├──►│ ContractRegistryService     │
│ (Structural Validation)  │   │ (Persistence Engine)        │
└──────────────────────────┘   └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │ PostgreSQL Database         │
                               │ - contract_registry         │
                               │ - contract_versions         │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │ DataGuard REST API          │
                               │ (FastAPI Services)          │
                               └─────────────────────────────┘
```

---

## 2. Database Schema Model

The persistence layer uses two relational tables: `contract_registry` for dataset summary metadata and `contract_versions` for immutable version history.

### Table: `contract_registry`
Stores current state and latest active version per dataset.

| Column | Type | Description |
|---|---|---|
| `dataset_name` | TEXT (PK) | Unique identifier for dataset |
| `latest_version` | TEXT | Latest registered version tag (`v1`, `v2`, etc.) |
| `owner` | TEXT | Data team or domain owner |
| `description` | TEXT | Human-readable dataset description |
| `freshness_sla_minutes` | INTEGER | Freshness SLA limit in minutes |
| `status` | TEXT | Lifecycle status (`ACTIVE`, `DEPRECATED`, `DRAFT`) |
| `created_at` | TIMESTAMP | Registration timestamp |
| `updated_at` | TIMESTAMP | Last metadata update timestamp |

### Table: `contract_versions`
Immutable history of contract definitions and raw YAML contents.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER (PK) | Auto-increment version ID |
| `dataset_name` | TEXT | Dataset reference name |
| `version` | TEXT | Version identifier (`v1`, `v2`, etc.) |
| `owner` | TEXT | Version creator owner tag |
| `description` | TEXT | Description snippet |
| `freshness_sla_minutes` | INTEGER | SLA limit in minutes |
| `status` | TEXT | Version status (`ACTIVE`, `DEPRECATED`, `DRAFT`) |
| `schema_json` | TEXT | Parsed JSON representation of full contract |
| `yaml_content` | TEXT | Complete, recoverable raw YAML string |
| `created_at` | TIMESTAMP | Registration timestamp |
| `created_by` | TEXT | Service or user principal |

**Constraints**: `UNIQUE(dataset_name, version)` prevents duplicate version registrations.

---

## 3. Versioning Strategy

Contracts enforce explicit versioning (e.g., `v1`, `v2`, `v3`).
- Older versions are never overwritten.
- Multi-version queries enable version comparison and historical inspection (`GET /contracts/{name}/versions`).
- Schema updates register new version tags.

---

## 4. Validation Workflow

Every contract submitted for registration passes structural validation via `ContractValidator`:
1. Root keys: `dataset`, `version`, `owner`, `description`, `freshness_sla_minutes`, `columns`, `constraints`.
2. Column schema: `name`, `type`, `nullable`, `unique`, `description`.
3. Type enforcement: `string`, `numeric`, `integer`, `timestamp`, `float`.
4. Constraint syntax & range checking (e.g. `min <= max`, `allowed_values` list).

If validation fails, the registry rejects the contract with a `ContractValidationError` (`422 Unprocessable Entity`).

---

## 5. API Endpoints

| Method | Path | Description | Response / Status |
|---|---|---|---|
| `GET` | `/health` | Healthcheck & registered contract total | `200 OK` |
| `POST` | `/contracts` | Register new contract payload | `201 Created` / `409` / `422` |
| `GET` | `/contracts` | List contract catalog (filter by owner, status, etc.) | `200 OK` |
| `GET` | `/contracts/{name}` | Retrieve latest version of dataset contract | `200 OK` / `404 Not Found` |
| `GET` | `/contracts/{name}/versions` | Retrieve version history for dataset | `200 OK` / `404 Not Found` |
| `GET` | `/contracts/{name}/versions/{version}` | Retrieve specific version of contract | `200 OK` / `404 Not Found` |
| `POST` | `/contracts/{name}/validate` | Validate contract structure against name | `200 OK` / `422` |

---

## 6. Observability Metrics

The registry emits Prometheus metrics:
- `contracts_registered_total`: Total successful registrations.
- `contract_registration_failures_total`: Total registration failures.
- `contract_validation_total`: Counter by result (`pass`/`fail`).
- `contract_registry_request_count`: HTTP request counter by endpoint, method, and status.

---

## 7. CLI Utilities

### Contract Registration Script
```bash
python scripts/register_contracts.py
```
Output:
```
Registered: 25
Skipped: 0
Failed: 0
```

### Contract Catalog Listing Script
```bash
python scripts/list_contracts.py
```
Prints tabular catalog of datasets, active version, owner, and freshness SLA.
