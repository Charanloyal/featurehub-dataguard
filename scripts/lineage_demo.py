"""
DataGuard OpenLineage Interactive CLI Demonstration.
Demonstrates dataset lineage, column-level lineage, graph traversal,
and incident correlation using live PostgreSQL 16 metadata.
"""

import sys
import json
from pathlib import Path

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataguard.lineage.service import LineageService
from dataguard.incidents.service import IncidentService


def run_lineage_demo():
    print("=" * 75)
    print("  DATAGUARD OPENLINEAGE DATA LINEAGE & AUDIT DEMONSTRATION")
    print("=" * 75)

    svc = LineageService()
    inc_svc = IncidentService()

    # 1. Dataset Lineage Graph
    print("\n[SCENARIO 1] Full End-to-End Dataset Lineage Graph")
    print("-" * 75)
    graph = svc.get_lineage_graph()
    print(f"Total Graph Nodes   : {graph['total_nodes']} (Datasets & Pipelines)")
    print(f"Total Directed Edges: {graph['total_edges']} (Lineage Dependencies)")
    print("\nSample Directed Dependency Paths:")
    for edge in graph['edges'][:8]:
        print(f"  {edge['source']:<32} ---({edge['pipeline_id']})---> {edge['target']}")

    # 2. Upstream Traversal
    print("\n[SCENARIO 2] Upstream Traversal (Root Cause Tracing)")
    print("-" * 75)
    target_ds = "customer_features"
    print(f"Querying Upstream Lineage for Target: '{target_ds}'...")
    up_res = svc.get_upstream(target_ds, depth=5)
    print(f"  Direct & Indirect Upstream Datasets: {', '.join(up_res['upstream_datasets'])}")
    print(f"  Contributing Transformation Pipelines: {', '.join(up_res['pipelines'])}")

    # 3. Downstream Traversal
    print("\n[SCENARIO 3] Downstream Traversal (Blast Radius & Impact Analysis)")
    print("-" * 75)
    source_ds = "postgres.transactions"
    print(f"Querying Downstream Lineage for Source: '{source_ds}'...")
    down_res = svc.get_downstream(source_ds, depth=5)
    print(f"  Dependent Downstream Datasets: {', '.join(down_res['downstream_datasets'])}")
    print(f"  Consuming Pipelines          : {', '.join(down_res['pipelines'])}")

    # 4. Column-Level Lineage
    print("\n[SCENARIO 4] Column-Level Lineage & Feature Transformations")
    print("-" * 75)
    target_feat_ds = "transaction_features"
    print(f"Querying Column Mappings for: '{target_feat_ds}'...")
    col_mappings = svc.get_column_lineage(target_feat_ds)
    for col in col_mappings:
        src_cols_str = ", ".join([f"{sc['dataset']}.{sc['column']}" for sc in col['source_columns']])
        print(f"\n  Target Column : {col['target_column']}")
        print(f"  Source Columns: {src_cols_str}")
        print(f"  Transformation: {col['transformation']}")
        print(f"  Pipeline      : {col['pipeline']} (Run: {col['run_id']})")

    # 5. Incident & Failed Pipeline Lineage Correlation
    print("\n[SCENARIO 5] Incident & Pipeline Lineage Correlation (Failed Pipeline)")
    print("-" * 75)
    incidents = inc_svc.list_incidents(pipeline="reconciliation_pipeline")
    if incidents:
        inc = incidents[0]
        print(f"  Incident ID        : {inc['incident_id']}")
        print(f"  Affected Dataset   : {inc['dataset']}")
        print(f"  Failed Pipeline    : {inc['pipeline']}")
        print(f"  Referenced Run ID  : {inc.get('run_id')}")
        print(f"  Severity           : {inc['severity']}")
        print(f"  Status             : {inc['status']}")
        
        # Correlate upstream lineage
        up_inc = svc.get_upstream(inc['dataset'], depth=3)
        print(f"  Upstream Dependencies for Affected Dataset: {up_inc['upstream_datasets']}")
    else:
        print("  No active reconciliation incidents found. Run scripts/populate_lineage.py first.")

    print("\n" + "=" * 75)
    print("  DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    run_lineage_demo()
