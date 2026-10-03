"""
DataGuard Observability Metrics Definition
Exposes Prometheus counters, histograms, and gauges for DataGuard platform metrics.
"""

from prometheus_client import Counter, Histogram, Gauge

CONTRACTS_REGISTERED_TOTAL = Counter(
    "contracts_registered_total", 
    "Total number of contracts successfully registered"
)

CONTRACT_REGISTRATION_FAILURES_TOTAL = Counter(
    "contract_registration_failures_total", 
    "Total number of contract registration failures"
)

CONTRACT_VALIDATION_TOTAL = Counter(
    "contract_validation_total", 
    "Total number of contract structural validations performed",
    ["result"]
)

CONTRACT_REGISTRY_REQUEST_COUNT = Counter(
    "contract_registry_request_count", 
    "Total HTTP requests handled by Contract Registry API",
    ["endpoint", "method", "status"]
)

DATAGUARD_REQUEST_COUNT = Counter(
    "dataguard_http_requests_total", 
    "Total DataGuard HTTP Requests", 
    ["endpoint", "status"]
)

DATAGUARD_LATENCY = Histogram(
    "dataguard_http_request_duration_seconds", 
    "DataGuard HTTP Request Latency in seconds", 
    ["endpoint"]
)

INCIDENTS_COUNT = Counter(
    "dataguard_incidents_created_total", 
    "Total Quality Incidents Created"
)

SCHEMA_DIFF_EVALUATIONS_TOTAL = Counter(
    "schema_diff_evaluations_total", 
    "Total schema diff evaluations performed", 
    ["classification"]
)

SCHEMA_DRIFT_DETECTED_TOTAL = Counter(
    "schema_drift_detected_total", 
    "Total schema drift modifications detected", 
    ["severity"]
)

SCHEMA_DIFF_REQUESTS_TOTAL = Counter(
    "schema_diff_requests_total",
    "Total schema diff comparison requests"
)

SCHEMA_DIFF_BREAKING_TOTAL = Counter(
    "schema_diff_breaking_total",
    "Total breaking schema diffs detected"
)

SCHEMA_DIFF_WARNING_TOTAL = Counter(
    "schema_diff_warning_total",
    "Total warning schema diffs detected"
)

SCHEMA_DIFF_SAFE_TOTAL = Counter(
    "schema_diff_safe_total",
    "Total safe schema diffs detected"
)

SCHEMA_DIFF_DURATION_SECONDS = Histogram(
    "schema_diff_duration_seconds",
    "Duration of schema diff evaluations in seconds"
)

# Phase D: Data Quality Metrics
QUALITY_VALIDATION_TOTAL = Counter(
    "quality_validation_total",
    "Total data quality validation suites executed",
    ["dataset", "status"]
)

QUALITY_VALIDATION_FAILURES_TOTAL = Counter(
    "quality_validation_failures_total",
    "Total data quality validation suites failed",
    ["dataset"]
)

QUALITY_CHECKS_TOTAL = Counter(
    "quality_checks_total",
    "Total individual quality expectation checks evaluated",
    ["dataset", "expectation_type"]
)

QUALITY_CHECK_FAILURES_TOTAL = Counter(
    "quality_check_failures_total",
    "Total individual quality expectation check failures",
    ["dataset", "expectation_type", "severity"]
)

QUALITY_VALIDATION_DURATION_SECONDS = Histogram(
    "quality_validation_duration_seconds",
    "Execution duration of data quality validations in seconds",
    ["dataset"]
)

FRESHNESS_VIOLATIONS_TOTAL = Counter(
    "freshness_violations_total",
    "Total dataset freshness SLA violations detected",
    ["dataset"]
)

# Phase E: Incident Management Metrics
INCIDENTS_CREATED_TOTAL = Counter(
    "incidents_created_total",
    "Total data quality incidents created",
    ["dataset", "severity"]
)

INCIDENTS_OPEN_TOTAL = Gauge(
    "incidents_open_total",
    "Current number of open data quality incidents"
)

INCIDENTS_ACKNOWLEDGED_TOTAL = Counter(
    "incidents_acknowledged_total",
    "Total data quality incidents acknowledged",
    ["dataset"]
)

INCIDENTS_RESOLVED_TOTAL = Counter(
    "incidents_resolved_total",
    "Total data quality incidents resolved",
    ["dataset"]
)

INCIDENT_CREATION_FAILURES_TOTAL = Counter(
    "incident_creation_failures_total",
    "Total failures when creating data quality incidents",
    ["dataset"]
)

INCIDENT_ACKNOWLEDGEMENT_SECONDS = Histogram(
    "incident_acknowledgement_seconds",
    "Time elapsed before incident acknowledgement in seconds",
    ["dataset"]
)

INCIDENT_RESOLUTION_SECONDS = Histogram(
    "incident_resolution_seconds",
    "Time elapsed before incident resolution in seconds",
    ["dataset"]
)

# Phase F: OpenLineage Data Lineage Metrics
LINEAGE_EVENTS_TOTAL = Counter(
    "lineage_events_total",
    "Total OpenLineage events ingested",
    ["event_type", "pipeline_id"]
)

LINEAGE_EVENT_FAILURES_TOTAL = Counter(
    "lineage_event_failures_total",
    "Total failures processing OpenLineage events",
    ["pipeline_id"]
)

LINEAGE_RUNS_TOTAL = Counter(
    "lineage_runs_total",
    "Total pipeline runs tracked in lineage",
    ["pipeline_id", "status"]
)

LINEAGE_FAILED_RUNS_TOTAL = Counter(
    "lineage_failed_runs_total",
    "Total failed pipeline runs tracked in lineage",
    ["pipeline_id"]
)

LINEAGE_DATASETS_TOTAL = Gauge(
    "lineage_datasets_total",
    "Current total unique datasets tracked in lineage graph"
)

LINEAGE_EDGES_TOTAL = Gauge(
    "lineage_edges_total",
    "Current total lineage dependency edges"
)

LINEAGE_PROCESSING_DURATION_SECONDS = Histogram(
    "lineage_processing_duration_seconds",
    "Time spent ingesting and processing OpenLineage events",
    ["event_type"]
)

# Phase G: Airflow Pipeline Orchestration Metrics
PIPELINE_RUNS_TOTAL = Counter(
    "pipeline_runs_total",
    "Total Airflow pipeline runs tracked by DataGuard",
    ["pipeline_id", "status"]
)

PIPELINE_SUCCESS_TOTAL = Counter(
    "pipeline_success_total",
    "Total successful Airflow pipeline runs",
    ["pipeline_id"]
)

PIPELINE_FAILURE_TOTAL = Counter(
    "pipeline_failure_total",
    "Total failed Airflow pipeline runs",
    ["pipeline_id", "failure_type"]
)

PIPELINE_DURATION_SECONDS = Histogram(
    "pipeline_duration_seconds",
    "Airflow pipeline execution duration in seconds",
    ["pipeline_id"]
)

PIPELINE_RETRIES_TOTAL = Counter(
    "pipeline_retries_total",
    "Total pipeline retries executed",
    ["pipeline_id"]
)

PIPELINE_STALE_TOTAL = Counter(
    "pipeline_stale_total",
    "Total stale dataset breaches detected by freshness pipelines",
    ["pipeline_id", "dataset"]
)

PIPELINE_QUALITY_FAILURES_TOTAL = Counter(
    "pipeline_quality_failures_total",
    "Total quality validation failures encountered during pipeline runs",
    ["pipeline_id", "dataset"]
)
