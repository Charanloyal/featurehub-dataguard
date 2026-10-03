# FeatureHub Benchmark Methodology & Results

## Measured Performance Overview

- **Storage Target**: `Redis Container Socket (TCP)`
- **HTTP API Target**: `http://127.0.0.1:8010/predict`
- **Requests Evaluated**: 1000 iterations (100 warmup requests)
- **High-Resolution Monotonic Timer**: `time.perf_counter()`

## Measured Metrics Table

| Subsystem / Layer | p50 Latency | p95 Latency | p99 Latency | Throughput (req/sec) |
| :--- | :--- | :--- | :--- | :--- |
| **Online Store Key Lookup** | `0.1087 ms` | `0.1941 ms` | `0.2788 ms` | - |
| **Real End-to-End HTTP Prediction API** | `1.6604 ms` | `2.0930 ms` | `2.8408 ms` | **575.7 req/s** |

## Investigation of Prior Latency Reporting
Prior reporting of `0.000ms` occurred due to formatting in-memory dictionary fallback access formatted to 3 decimal places. The current benchmark measures actual network socket latency over TCP client calls with microsecond float precision (`0.000000s`).
