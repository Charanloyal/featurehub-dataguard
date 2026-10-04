# DataGuard CI/CD Gating Performance Benchmark Report

**Phase**: STAGE 3 — PHASE H: GITHUB CI/CD GATING  
**Environment**: Windows AMD64, Python 3.13.9  
**Source Data**: `dataguard/benchmarks/ci_gate_results.json`  

---

## 1. Latency & Throughput Measurements

Benchmarks evaluate complete end-to-end gating:
`Contract Structural Validation -> Schema Diff Engine -> Rule Evaluation -> Markdown Formatting`.

| Schema Scale | Mean Latency | p50 (Median) | p95 Latency | p99 Latency | Throughput |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **10 Columns** | **0.153 ms** | 0.126 ms | 0.283 ms | 0.806 ms | **6,548 evals/sec** |
| **50 Columns** | **0.304 ms** | 0.286 ms | 0.543 ms | 0.648 ms | **3,285 evals/sec** |
| **100 Columns** | **0.565 ms** | 0.497 ms | 0.868 ms | 1.410 ms | **1,768 evals/sec** |
| **250 Columns** | **1.189 ms** | 1.134 ms | 1.524 ms | 1.849 ms | **840 evals/sec** |

---

## 2. Batch PR Benchmark (Full Repository)

Evaluation of all **25 production contracts** simultaneously in a single PR evaluation pass:

| Metric | Measured Value |
| :--- | :---: |
| **Contracts Evaluated** | 25 production contracts |
| **Batch Mean Latency** | **1.831 ms** |
| **Batch p50 Latency** | **1.769 ms** |
| **Batch p95 Latency** | **2.686 ms** |
| **Effective PR Throughput** | **546 Pull Requests / sec** |

---

## 3. Analysis & Overhead Implications

1. **Sub-Millisecond Per-Contract Evaluation**: Even contracts containing 100 enterprise columns evaluate in 0.565 milliseconds.
2. **Negligible CI Runner Overhead**: The entire DataGuard gating check executes in under 2 milliseconds of compute time, adding virtually zero latency to the GitHub Actions runner runtime.
3. **Linear Algorithmic Complexity**: Execution scales linearly $O(N)$ with column count, guaranteeing deterministic CI runtimes even on massive enterprise schemas with hundreds of attributes.
