# Architectural Decision Records (ADRs)

## ADR 001: Selection of Redis for Online Feature Store
- **Status**: Accepted
- **Context**: Real-time ML inference requires sub-millisecond feature lookup latencies during API requests.
- **Decision**: Use Redis 7.2 key-value store to serve materialized feature vectors.
- **Consequences**: Enables low p99 latencies, decouples online prediction from offline analytical storage.

## ADR 002: Strict Point-In-Time As-Of Joins for Feature Generation
- **Status**: Accepted
- **Context**: Training models on current feature snapshots introduces future data leakage and severe training-serving skew.
- **Decision**: Enforce timestamp-aware `merge_asof` joins requiring $t_{\text{feature}} \le t_{\text{observation}}$. Raise `DataLeakageError` on violation.
- **Consequences**: Guaranteed zero target leakage across model retraining cycles.

## ADR 003: Declarative YAML Data Contracts & CI Diff Gatekeeping
- **Status**: Accepted
- **Context**: Unannounced upstream database schema modifications break downstream data pipelines and ML inference models.
- **Decision**: Define YAML contracts across 25 datasets and implement CI Schema Diff Engine classifying changes into `SAFE`, `WARNING`, and `BREAKING`.
- **Consequences**: Automatically blocks breaking schema edits in GitHub Pull Requests pre-merge.
