# Final Benchmark Index & Performance Ledger

**Audit Phase**: STAGE 3 — PHASE K: SYSTEM TRUTH AUDIT  
**Date**: 2026-10-04  
**Primary Repository**: `Charanloyal/featurehub-dataguard`  

This index aggregates all empirical benchmarks, hardware environments, measurement scripts, and output artifacts produced during the platform audit.

---

## 1. Benchmark Artifacts & Reports

| # | Benchmark Domain | Output Artifact / Report | Key Empirical Finding | Script to Reproduce |
|---|---|---|---|---|
| **1** | **FeatureHub Online & Inference** | [`featurehub/benchmarks/final_results.json`](../featurehub/benchmarks/final_results.json) | **122 features**, Redis P99: **1.62ms**, Prediction P99: **6.62ms**, Throughput: **228.5 req/s** | `python featurehub/benchmarks/run_final_benchmarks.py` |
| **2** | **DataGuard Schema Diff** | [`dataguard/benchmarks/final_schema_results.json`](../dataguard/benchmarks/final_schema_results.json) | 10 cols: **0.085ms**, 50 cols: **0.202ms**, 100 cols: **0.368ms**, 250 cols: **0.893ms** (P50) | `python scripts/benchmark_schema_diff.py` |
| **3** | **Data Quality (Great Expectations)** | [`dataguard/benchmarks/final_quality_results.json`](../dataguard/benchmarks/final_quality_results.json) | 1K rows: **37.6ms**, 10K rows: **164.8ms**, 100K rows: **290.4ms** (**344,340 rows/sec**) | `python scripts/benchmark_quality.py` |
| **4** | **OpenLineage Lineage Traversal** | [`dataguard/benchmarks/final_lineage_results.json`](../dataguard/benchmarks/final_lineage_results.json) | Column Lineage: **6.29ms**, Graph Query: **19.04ms**, Upstream Traversal: **20.22ms** | `python scripts/benchmark_lineage.py` |
| **5** | **Incident Management Operations** | [`dataguard/benchmarks/final_incident_results.json`](../dataguard/benchmarks/final_incident_results.json) | Creation: **22.09ms**, Deduplication: **13.48ms**, Ack: **20.74ms**, Resolution: **20.93ms** (P50) | `python scripts/benchmark_incidents.py` |
| **6** | **GitHub Actions CI/CD Pre-Merge Gate** | [`dataguard/benchmarks/ci_gate_results.json`](../dataguard/benchmarks/ci_gate_results.json) | Full 25-contract PR evaluated in **1.37ms** (P50); 100% breaking changes blocked | `python scripts/benchmark_ci_gate.py` |
| **7** | **Schema Breaking Change Experiment** | [`scripts/schema_breaking_experiment.py`](../scripts/schema_breaking_experiment.py) | **100.0%** of breaking evolutions blocked pre-merge; 100% of safe changes allowed | `python scripts/schema_breaking_experiment.py` |
| **8** | **Incident Triage Reduction Experiment** | [`docs/benchmarks/incident_triage_experiment.md`](../docs/benchmarks/incident_triage_experiment.md) | Single-point PostgreSQL lookup completes in **5.44ms**; 55% MTTR reduction audited as **UNVERIFIED / DESIGN GOAL** | `python scripts/incident_triage_experiment.py` |
| **9** | **Full End-to-End Platform Flow** | [`docs/FEATUREHUB_DATAGUARD_INTEGRATION_VALIDATION.md`](../docs/FEATUREHUB_DATAGUARD_INTEGRATION_VALIDATION.md) | 11-stage flow verified: Success (10.8s), Fast-Fail Circuit Breaker (1.09s), Recovery (5.74s) | `python scripts/run_integrated_pipeline.py` |

---

## 2. Platform Pipeline Inventory Link

- Comprehensive registry of all 26 standard pipelines, 10 dedicated Airflow DAGs, and 7 deterministic demo DAGs:  
  [`docs/PIPELINE_INVENTORY.md`](../docs/PIPELINE_INVENTORY.md)

---

## 3. Test Suite Sign-Off

- Complete results across 21 test suites (276 / 276 tests passing):  
  [`docs/FINAL_TEST_RESULTS.md`](../docs/FINAL_TEST_RESULTS.md)
