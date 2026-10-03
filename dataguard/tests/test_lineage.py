"""
DataGuard OpenLineage Unit & API Test Suite (Phase F).
Validates dataset lineage, job registration, run lifecycle, graph traversal,
column-level lineage, OpenLineage standard events, and incident correlation.
"""

import uuid
import pytest
from datetime import datetime, timezone
from pathlib import Path
from starlette.testclient import TestClient

from dataguard.lineage.models import (
    LineageStatus,
    LineageDataset,
    LineageJob,
    LineageRun,
    LineageGraphResponse
)
from dataguard.lineage.events import (
    RunEvent,
    Run,
    Job,
    InputDataset,
    OutputDataset,
    ColumnLineageDatasetFacet,
    ColumnLineageField,
    ColumnLineageInputField
)
from dataguard.lineage.repository import LineageRepository
from dataguard.lineage.collector import LineageCollector
from dataguard.lineage.service import LineageService
from dataguard.incidents.models import Incident, IncidentStatus, IncidentSeverity
from dataguard.incidents.repository import IncidentRepository
from dataguard.incidents.manager import IncidentManager
from dataguard.quality.models import QualityCheckResult, QualityStatus
from dataguard.api.main import app


@pytest.fixture
def temp_repo(tmp_path: Path):
    db_file = tmp_path / "test_lineage.db"
    return LineageRepository(db_path=db_file)


@pytest.fixture
def collector(temp_repo: LineageRepository):
    return LineageCollector(repository=temp_repo)


@pytest.fixture
def client(temp_repo: LineageRepository):
    # Override lineage_service repository in app for isolated testing
    from dataguard.api import main
    main.lineage_service = LineageService(repository=temp_repo)
    return TestClient(app)


# 1. Dataset Registration
def test_dataset_registration(temp_repo: LineageRepository):
    ds = temp_repo.register_dataset(
        name="raw_events",
        namespace="kafka",
        description="Streaming click events"
    )
    assert ds.dataset_id == "kafka.raw_events"
    assert ds.name == "raw_events"
    assert ds.namespace == "kafka"

    # Re-registration updates metadata without duplicate key error
    ds_upd = temp_repo.register_dataset(
        name="raw_events",
        namespace="kafka",
        description="Updated description"
    )
    assert ds_upd.description == "Updated description"


# 2. Job Registration
def test_job_registration(temp_repo: LineageRepository):
    job = temp_repo.register_job(
        name="enrich_events_job",
        namespace="spark",
        pipeline_id="event_enrichment_pipeline",
        description="Enriches events with geo IP"
    )
    assert job.job_id == "spark.enrich_events_job"
    assert job.pipeline_id == "event_enrichment_pipeline"


# 3. Run Creation & Status Transitions
def test_run_creation(collector: LineageCollector, temp_repo: LineageRepository):
    run = collector.start_run(
        pipeline_id="etl_transactions",
        inputs=["postgres.transactions"],
        job_name="etl_transactions_job",
        namespace="airflow"
    )
    assert run.pipeline_id == "etl_transactions"
    assert run.status == LineageStatus.START
    assert "postgres.transactions" in run.inputs

    # Fetch from repository
    fetched = temp_repo.get_run(run.run_id)
    assert fetched is not None
    assert fetched.status == LineageStatus.START


# 4. Successful Run
def test_successful_run(collector: LineageCollector, temp_repo: LineageRepository):
    run = collector.start_run(
        pipeline_id="feature_pipeline",
        inputs=["raw_data"]
    )
    completed = collector.complete_run(
        run_id=run.run_id,
        outputs=["clean_features"],
        pipeline_id="feature_pipeline"
    )
    assert completed.status == LineageStatus.COMPLETE
    assert completed.end_time is not None
    assert "clean_features" in completed.outputs


# 5. Failed Run
def test_failed_run(collector: LineageCollector, temp_repo: LineageRepository):
    run = collector.start_run(
        pipeline_id="failing_pipeline",
        inputs=["input_stream"]
    )
    failed = collector.fail_run(
        run_id=run.run_id,
        pipeline_id="failing_pipeline",
        error_message="Deadlock detected during batch update."
    )
    assert failed.status == LineageStatus.FAIL
    assert "errorMessage" in failed.facets
    assert "Deadlock detected" in failed.facets["errorMessage"]["message"]


# 6. Input / Output Relationship & Edges
def test_input_output_relationship(collector: LineageCollector, temp_repo: LineageRepository):
    run = collector.start_run(
        pipeline_id="transformation_pipe",
        inputs=["dataset_a", "dataset_b"]
    )
    collector.complete_run(
        run_id=run.run_id,
        outputs=["dataset_c"],
        pipeline_id="transformation_pipe"
    )

    graph = temp_repo.get_graph()
    sources = [e.source for e in graph.edges]
    targets = [e.target for e in graph.edges]

    assert "dataset_a" in sources
    assert "dataset_b" in sources
    assert "dataset_c" in targets
    assert "transformation_pipe" in sources or "transformation_pipe" in targets


# 7. Upstream Query (Multi-Hop BFS)
def test_upstream_query(collector: LineageCollector, temp_repo: LineageRepository):
    # Hop 1: A -> Pipe1 -> B
    r1 = collector.start_run(pipeline_id="pipe_1", inputs=["dataset_a"])
    collector.complete_run(run_id=r1.run_id, outputs=["dataset_b"], pipeline_id="pipe_1")

    # Hop 2: B -> Pipe2 -> C
    r2 = collector.start_run(pipeline_id="pipe_2", inputs=["dataset_b"])
    collector.complete_run(run_id=r2.run_id, outputs=["dataset_c"], pipeline_id="pipe_2")

    upstream_c = temp_repo.get_upstream("dataset_c", max_depth=5)
    assert "dataset_b" in upstream_c.upstream_datasets
    assert "dataset_a" in upstream_c.upstream_datasets
    assert "pipe_1" in upstream_c.pipelines
    assert "pipe_2" in upstream_c.pipelines


# 8. Downstream Query (Multi-Hop BFS)
def test_downstream_query(collector: LineageCollector, temp_repo: LineageRepository):
    r1 = collector.start_run(pipeline_id="pipe_1", inputs=["dataset_a"])
    collector.complete_run(run_id=r1.run_id, outputs=["dataset_b"], pipeline_id="pipe_1")

    r2 = collector.start_run(pipeline_id="pipe_2", inputs=["dataset_b"])
    collector.complete_run(run_id=r2.run_id, outputs=["dataset_c"], pipeline_id="pipe_2")

    downstream_a = temp_repo.get_downstream("dataset_a", max_depth=5)
    assert "dataset_b" in downstream_a.downstream_datasets
    assert "dataset_c" in downstream_a.downstream_datasets
    assert "pipe_1" in downstream_a.pipelines
    assert "pipe_2" in downstream_a.pipelines


# 9. Column-Level Lineage Direct Mapping
def test_column_lineage(temp_repo: LineageRepository):
    col = temp_repo.record_column_mapping(
        run_id="run_123",
        source_dataset="transactions",
        source_column="amount",
        target_dataset="transaction_features",
        target_column="total_amount_24h",
        transformation="SUM(amount) over trailing 24h window",
        pipeline_id="feature_compute"
    )
    assert col.target_column == "total_amount_24h"

    retrieved = temp_repo.get_column_lineage("transaction_features")
    assert len(retrieved) >= 1
    matched = [c for c in retrieved if c.target_column == "total_amount_24h"]
    assert len(matched) == 1
    assert matched[0].transformation == "SUM(amount) over trailing 24h window"
    assert matched[0].source_columns[0]["column"] == "amount"


# 10. Column Lineage Multi-Source Grouping
def test_column_lineage_grouping(temp_repo: LineageRepository):
    temp_repo.record_column_mapping(
        run_id="run_456",
        source_dataset="orders",
        source_column="price",
        target_dataset="customer_metrics",
        target_column="avg_basket_value",
        transformation="AVG(price * quantity)",
        pipeline_id="orders_agg"
    )
    temp_repo.record_column_mapping(
        run_id="run_456",
        source_dataset="orders",
        source_column="quantity",
        target_dataset="customer_metrics",
        target_column="avg_basket_value",
        transformation="AVG(price * quantity)",
        pipeline_id="orders_agg"
    )

    cols = temp_repo.get_column_lineage("customer_metrics", target_column="avg_basket_value")
    assert len(cols) == 1
    sources = [s["column"] for s in cols[0].source_columns]
    assert "price" in sources
    assert "quantity" in sources


# 11. Column Lineage Filter
def test_column_lineage_filter(temp_repo: LineageRepository):
    temp_repo.record_column_mapping(
        run_id="r1", source_dataset="d1", source_column="c1",
        target_dataset="d2", target_column="col_a", transformation="T1", pipeline_id="p1"
    )
    temp_repo.record_column_mapping(
        run_id="r1", source_dataset="d1", source_column="c2",
        target_dataset="d2", target_column="col_b", transformation="T2", pipeline_id="p1"
    )

    filtered = temp_repo.get_column_lineage("d2", target_column="col_a")
    assert len(filtered) == 1
    assert filtered[0].target_column == "col_a"


# 12. Lineage Graph Output
def test_lineage_graph(collector: LineageCollector, temp_repo: LineageRepository):
    run = collector.start_run(pipeline_id="p_graph", inputs=["ds_in"])
    collector.complete_run(run_id=run.run_id, outputs=["ds_out"], pipeline_id="p_graph")

    graph = temp_repo.get_graph()
    assert isinstance(graph, LineageGraphResponse)
    assert graph.total_nodes >= 3
    assert graph.total_edges >= 2
    node_ids = [n.id for n in graph.nodes]
    assert "ds_in" in node_ids
    assert "ds_out" in node_ids
    assert "p_graph" in node_ids


# 13. Run History
def test_run_history(collector: LineageCollector, temp_repo: LineageRepository):
    for i in range(3):
        r = collector.start_run(pipeline_id="recurring_pipe", inputs=["feed"])
        collector.complete_run(run_id=r.run_id, outputs=["sink"], pipeline_id="recurring_pipe")

    history = temp_repo.get_runs_for_pipeline("recurring_pipe", limit=10)
    assert len(history) == 3
    assert all(r.status == LineageStatus.COMPLETE for r in history)


# 14. OpenLineage Standard Event Ingestion
def test_openlineage_event_ingestion(collector: LineageCollector, temp_repo: LineageRepository):
    event = RunEvent(
        eventType="COMPLETE",
        eventTime=datetime.now(timezone.utc).isoformat(),
        run=Run(runId="ol_run_001", facets={"env": "prod"}),
        job=Job(namespace="dataguard", name="quality_runner"),
        inputs=[InputDataset(namespace="postgres", name="merchants")],
        outputs=[OutputDataset(namespace="warehouse", name="merchants_clean")]
    )
    run = collector.emit_event(event)
    assert run.run_id == "ol_run_001"
    assert run.status == LineageStatus.COMPLETE
    assert "postgres.merchants" in run.inputs
    assert "warehouse.merchants_clean" in run.outputs


# 15. OpenLineage Column Lineage Facet Parsing
def test_openlineage_column_lineage_facet(collector: LineageCollector, temp_repo: LineageRepository):
    col_facet = ColumnLineageDatasetFacet(
        fields={
            "feature_spend_30d": ColumnLineageField(
                inputFields=[ColumnLineageInputField(namespace="postgres", name="txns", field="amount")],
                transformationDescription="SUM(amount) 30d",
                transformationType="AGGREGATION"
            )
        }
    )
    event = RunEvent(
        eventType="COMPLETE",
        eventTime=datetime.now(timezone.utc).isoformat(),
        run=Run(runId="ol_run_cols", facets={}),
        job=Job(namespace="airflow", name="feature_job"),
        inputs=[InputDataset(namespace="postgres", name="txns")],
        outputs=[OutputDataset(
            namespace="featurehub",
            name="customer_feats",
            facets={"columnLineage": col_facet.model_dump()}
        )]
    )
    collector.emit_event(event)

    cols = temp_repo.get_column_lineage("customer_feats")
    assert len(cols) >= 1
    assert cols[0].target_column == "feature_spend_30d"
    assert cols[0].transformation == "SUM(amount) 30d"


# 16. Airflow Collector Lifecycle
def test_airflow_collector_lifecycle(collector: LineageCollector):
    # 1. Start run
    run = collector.start_run(
        pipeline_id="airflow_dag_task",
        job_name="task_aggregate_daily",
        inputs=["postgres.orders"],
        namespace="airflow"
    )
    assert run.status == LineageStatus.START

    # 2. Complete run with column mappings
    comp = collector.complete_run(
        run_id=run.run_id,
        pipeline_id="airflow_dag_task",
        job_name="task_aggregate_daily",
        outputs=["daily_sales"],
        column_mappings=[{
            "source_dataset": "postgres.orders",
            "source_column": "amount",
            "target_dataset": "daily_sales",
            "target_column": "total_sales",
            "transformation": "SUM(amount)"
        }]
    )
    assert comp.status == LineageStatus.COMPLETE


# 17. Incident & Lineage Reference Correlation
def test_incident_lineage_reference(tmp_path: Path):
    inc_db = tmp_path / "incidents_lineage.db"
    inc_repo = IncidentRepository(db_path=inc_db)
    inc_mgr = IncidentManager(repository=inc_repo)

    failing_check = QualityCheckResult(
        run_id="run_failing_batch_001",
        dataset="transactions",
        check_name="check_amount_positive",
        column="amount",
        expectation_type="expect_column_values_to_be_between",
        status=QualityStatus.FAIL,
        severity=IncidentSeverity.HIGH,
        observed_value="-50.00",
        expected_value="[0, 1000000]",
        success=False,
        pipeline="transaction_quality_pipeline"
    )

    inc = inc_mgr.handle_check_failure(
        check=failing_check,
        dataset="transactions",
        pipeline="transaction_quality_pipeline"
    )

    assert inc is not None
    assert inc.run_id == "run_failing_batch_001"
    assert inc.pipeline == "transaction_quality_pipeline"
    assert inc.pipeline_id == "transaction_quality_pipeline"


# 18. API GET /lineage/graph
def test_api_get_graph(client: TestClient, collector: LineageCollector):
    run = collector.start_run(pipeline_id="p_api", inputs=["ds1"])
    collector.complete_run(run_id=run.run_id, outputs=["ds2"], pipeline_id="p_api")

    res = client.get("/lineage/graph")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data
    assert data["total_nodes"] >= 2


# 19. API GET /lineage/{dataset}
def test_api_get_dataset_lineage(client: TestClient, collector: LineageCollector):
    run = collector.start_run(pipeline_id="p_api_ds", inputs=["source_ds"])
    collector.complete_run(run_id=run.run_id, outputs=["target_ds"], pipeline_id="p_api_ds")

    res = client.get("/lineage/target_ds")
    assert res.status_code == 200
    data = res.json()
    assert data["dataset"] in ("target_ds", "default.target_ds")
    assert "source_ds" in data["upstream_datasets"] or "default.source_ds" in data["upstream_datasets"]


# 20. API GET /lineage/{dataset}/upstream & downstream
def test_api_get_upstream_downstream(client: TestClient, collector: LineageCollector):
    r1 = collector.start_run(pipeline_id="p_pipe", inputs=["in_ds"])
    collector.complete_run(run_id=r1.run_id, outputs=["out_ds"], pipeline_id="p_pipe")

    res_up = client.get("/lineage/out_ds/upstream")
    assert res_up.status_code == 200
    assert "in_ds" in res_up.json()["upstream_datasets"] or "default.in_ds" in res_up.json()["upstream_datasets"]

    res_down = client.get("/lineage/in_ds/downstream")
    assert res_down.status_code == 200
    assert "out_ds" in res_down.json()["downstream_datasets"] or "default.out_ds" in res_down.json()["downstream_datasets"]


# 21. API GET /lineage/{dataset}/columns
def test_api_get_columns(client: TestClient, temp_repo: LineageRepository):
    temp_repo.record_column_mapping(
        run_id="run_api_col",
        source_dataset="input_tbl",
        source_column="col_in",
        target_dataset="target_tbl",
        target_column="col_out",
        transformation="UPPER(col_in)",
        pipeline_id="cleaning_pipe"
    )

    res = client.get("/lineage/target_tbl/columns")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["target_column"] == "col_out"
    assert items[0]["transformation"] == "UPPER(col_in)"


# 22. API GET /lineage/runs/{run_id} & /lineage/pipelines/{pipeline_id}
def test_api_get_run_and_pipeline(client: TestClient, collector: LineageCollector):
    run = collector.start_run(pipeline_id="pipe_runs_test", inputs=["inp1"])
    collector.complete_run(run_id=run.run_id, outputs=["out1"], pipeline_id="pipe_runs_test")

    res_run = client.get(f"/lineage/runs/{run.run_id}")
    assert res_run.status_code == 200
    assert res_run.json()["run_id"] == run.run_id

    res_pipe = client.get("/lineage/pipelines/pipe_runs_test")
    assert res_pipe.status_code == 200
    assert len(res_pipe.json()) >= 1


# 23. API POST /lineage/events
def test_api_post_lineage_event(client: TestClient):
    payload = {
        "eventType": "START",
        "eventTime": datetime.now(timezone.utc).isoformat(),
        "run": {"runId": "api_event_run_1", "facets": {}},
        "job": {"namespace": "airflow", "name": "api_ingested_dag"},
        "inputs": [{"namespace": "postgres", "name": "customers"}],
        "outputs": []
    }
    res = client.post("/lineage/events", json=payload)
    assert res.status_code == 201
    assert res.json()["run_id"] == "api_event_run_1"
    assert res.json()["status"] == "START"


# 24. Deterministic Failure Flow & Incident Correlation
def test_failed_pipeline_incident_flow(collector: LineageCollector, tmp_path: Path):
    inc_db = tmp_path / "flow_incidents.db"
    inc_repo = IncidentRepository(db_path=inc_db)
    inc_mgr = IncidentManager(repository=inc_repo)

    # 1. Pipeline starts
    f_run = collector.start_run(
        pipeline_id="reconciliation_worker",
        inputs=["ledger_txns", "bank_statement"]
    )

    # 2. Pipeline encounters failure
    collector.fail_run(
        run_id=f_run.run_id,
        pipeline_id="reconciliation_worker",
        error_message="Debit/credit balance inequality."
    )

    # 3. Quality failure is registered
    fail_check = QualityCheckResult(
        run_id=f_run.run_id,
        dataset="ledger_txns",
        check_name="balance_equality",
        column="balance",
        expectation_type="expect_column_values_to_be_between",
        status=QualityStatus.FAIL,
        severity=IncidentSeverity.CRITICAL,
        observed_value="Difference: -$1,200.00",
        expected_value="$0.00",
        success=False,
        pipeline="reconciliation_worker"
    )

    # 4. Incident is automatically created with lineage reference
    incident = inc_mgr.handle_check_failure(
        check=fail_check,
        dataset="ledger_txns",
        pipeline="reconciliation_worker"
    )

    assert incident is not None
    assert incident.status == IncidentStatus.OPEN
    assert incident.severity in (IncidentSeverity.CRITICAL, IncidentSeverity.MEDIUM, IncidentSeverity.HIGH)
    assert incident.run_id == f_run.run_id
    assert incident.pipeline == "reconciliation_worker"
