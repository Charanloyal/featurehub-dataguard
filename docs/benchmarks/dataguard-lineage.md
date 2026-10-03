# DataGuard OpenLineage Performance Benchmark Report

**Stage**: STAGE 3 — PHASE F: OPENLINEAGE DATA LINEAGE  
**Artifact**: `dataguard/benchmarks/lineage_results.json`  
**Database**: PostgreSQL 16.15 (`featurehub_dataguard_postgres` Docker container)  

---

## 1. System & Hardware Specifications

All benchmarks were executed against the live Docker PostgreSQL 16 container using `scripts/benchmark_lineage.py`:

- **Operating System**: Windows 11 (10.0.26200)
- **CPU**: Intel64 Family 6 Model 154 Stepping 3 (16 logical cores @ 2.3 GHz)
- **RAM**: 15.69 GB Total
- **Python**: 3.13.9
- **Database Engine**: PostgreSQL 16.15 on x86_64-pc-linux-musl
- **Lineage Standard**: OpenLineage 1.0.5 compliant JSON schemas
- **Sample Size**: 25 iterations per benchmark operation

---

## 2. Graph Size & Active Metadata

At the time of benchmarking, the persistent PostgreSQL lineage repository contained:

- **Total Graph Nodes**: `26` (Datasets and Pipelines)
- **Total Dependency Edges**: `54`
- **Total Datasets**: `15`
- **Total Pipeline Jobs**: `11`
- **Total Execution Runs**: `31`
- **Total Column Lineage Mappings**: `60`

---

## 3. Benchmark Results & Latency Distribution

| Operation | p50 (ms) | p95 (ms) | p99 (ms) | Mean (ms) | Std Dev (ms) | Min (ms) | Max (ms) | Throughput (ops/sec) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Event Ingestion (Full OpenLineage Payload)** | 203.45 | 242.79 | 271.78 | **208.11** | 19.27 | 188.65 | 279.69 | **4.81** |
| **Dynamic Graph Query (Nodes & Edges)** | 7.39 | 14.71 | 16.61 | **8.54** | 2.80 | 5.62 | 17.01 | **117.16** |
| **Upstream Graph Traversal (Multi-Hop BFS)** | 6.44 | 7.93 | 8.27 | **6.59** | 0.71 | 5.71 | 8.35 | **151.67** |
| **Downstream Graph Traversal (Blast Radius)** | 6.75 | 8.19 | 8.30 | **6.77** | 0.79 | 5.56 | 8.32 | **147.67** |
| **Column-Level Lineage Query** | 3.86 | 5.16 | 5.43 | **3.94** | 0.59 | 3.17 | 5.50 | **253.67** |

---

## 4. Key Performance Observations

1. **Sub-10ms Graph Retrieval**:
   - The full graph structure across 26 nodes and 54 edges executes in an average of **8.54 ms**, capable of serving over **117 graph requests per second**.
2. **High-Speed Multi-Hop Traversals**:
   - Both upstream root-cause queries (mean **6.59 ms**) and downstream blast-radius calculations (mean **6.77 ms**) leverage indexed PostgreSQL foreign keys and BFS queues, delivering over **145 traversals per second**.
3. **Ultra-Low Latency Column Inquiries**:
   - Column lineage lookups retrieve complex aggregation definitions and input column arrays in just **3.94 ms** (over **250 operations per second**).
4. **ACID Transactional Integrity on Ingestion**:
   - OpenLineage event ingestion writes across `lineage_jobs`, `lineage_datasets`, `lineage_runs`, `lineage_edges`, and `lineage_columns` in a single atomic transaction in **208.11 ms**.
