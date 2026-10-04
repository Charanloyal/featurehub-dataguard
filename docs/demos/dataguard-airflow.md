# DataGuard Demo Guide — Apache Airflow Pipeline Orchestration (Phase G)

This guide walks through triggering, testing, and observing DataGuard data pipeline orchestration workflows using the Airflow CLI, Docker, Python SDK, and FastAPI endpoints.

---

## 1. Inspecting Registered Airflow DAGs

Connect to the containerized Airflow service to view all 16 registered production DAGs:

```powershell
docker exec featurehub_dataguard_airflow airflow dags list
```

**Output**:
```text
dag_id                            | fileloc                                            | owners               | is_paused
==================================+====================================================+======================+==========
customer_quality_pipeline         | /opt/airflow/dags/customer_quality_pipeline.py     | customer-risk-team   | True     
transaction_quality_pipeline      | /opt/airflow/dags/transaction_quality_pipeline.py  | payments-data-team   | True     
feature_quality_pipeline          | /opt/airflow/dags/feature_quality_pipeline.py      | mlops-platform-team  | True     
schema_validation_pipeline        | /opt/airflow/dags/schema_validation_pipeline.py    | data-platform-team   | True     
freshness_monitoring_pipeline     | /opt/airflow/dags/freshness_monitoring_pipeline.py | data-operations-team | True     
demo_clean_pipeline               | /opt/airflow/dags/demo_test_pipelines.py           | platform-qa-team     | True     
demo_null_failure_pipeline        | /opt/airflow/dags/demo_test_pipelines.py           | platform-qa-team     | True     
demo_duplicate_failure_pipeline   | /opt/airflow/dags/demo_test_pipelines.py           | platform-qa-team     | True     
demo_invalid_enum_pipeline        | /opt/airflow/dags/demo_test_pipelines.py           | platform-qa-team     | True     
demo_referential_failure_pipeline | /opt/airflow/dags/demo_test_pipelines.py           | platform-qa-team     | True     
demo_stale_dataset_pipeline       | /opt/airflow/dags/demo_test_pipelines.py           | platform-qa-team     | True     
demo_breaking_schema_pipeline     | /opt/airflow/dags/demo_test_pipelines.py           | platform-qa-team     | True     
```

---

## 2. Executing an End-to-End Clean Pipeline

Trigger the customer quality pipeline via Python:

```python
from dataguard.pipelines.runner import DataGuardPipelineOrchestrator

orchestrator = DataGuardPipelineOrchestrator()
result = orchestrator.execute_pipeline("customer_quality_pipeline")

print("Pipeline Status :", result["status"])
print("Quality Score   :", result["quality_score"])
print("Total Checks    :", result["total_checks"])
print("Checks Passed   :", result["checks_passed"])
print("Execution Time  :", round(result["duration_ms"], 2), "ms")
```

**Expected Output**:
```text
Pipeline Status : SUCCESS
Quality Score   : 100.0
Total Checks    : 14
Checks Passed   : 14
Execution Time  : 274.19 ms
```

---

## 3. Testing Deterministic Failure Scenarios

### Scenario A: Injected Null Value into Non-Nullable Column
```python
res = orchestrator.execute_pipeline(
    "customer_quality_pipeline",
    test_scenario="null_violation",
    raise_on_failure=False
)
print("Status   :", res["status"])
print("Stage    :", res["stage"])
print("Incident :", res["incident_id"])
print("Error    :", res["error"])
```

### Scenario B: Breaking Schema Drift (Column Dropped)
```python
res = orchestrator.execute_pipeline(
    "customer_quality_pipeline",
    test_scenario="breaking_schema",
    raise_on_failure=False
)
print("Status   :", res["status"])
print("Stage    :", res["stage"])
print("Error    :", res["error"])
```

---

## 4. Querying Pipeline Telemetry via FastAPI Endpoints

Launch or query the live FastAPI backend:

```powershell
# 1. Platform Summary
curl http://localhost:8000/pipelines/summary

# 2. List All Active Pipelines
curl http://localhost:8000/pipelines

# 3. Pipeline Health Assessment
curl http://localhost:8000/pipelines/customer_quality_pipeline/health

# 4. Pipeline Execution Run History
curl http://localhost:8000/pipelines/customer_quality_pipeline/runs?limit=5
```

### Example Summary Response:
```json
{
  "total_pipelines": 26,
  "active_pipelines": 26,
  "successful_pipelines": 24,
  "failed_pipelines": 2,
  "running_pipelines": 0,
  "stale_pipelines": 1,
  "total_runs": 85,
  "failed_runs": 12,
  "success_rate": 85.88
}
```

---

## 5. Prometheus Observability Metrics

Query live metrics exposed on `GET /metrics`:

```text
# HELP pipeline_runs_total Total pipeline executions initiated
# TYPE pipeline_runs_total counter
pipeline_runs_total{pipeline_id="customer_quality_pipeline",status="SUCCESS"} 28.0
pipeline_runs_total{pipeline_id="customer_quality_pipeline",status="FAILED"} 3.0

# HELP pipeline_duration_seconds Pipeline run duration in seconds
# TYPE pipeline_duration_seconds histogram
pipeline_duration_seconds_sum{pipeline_id="customer_quality_pipeline"} 8.29
pipeline_duration_seconds_count{pipeline_id="customer_quality_pipeline"} 31.0
```
