# Architecture Design Decisions & Trade-Offs

This document records the core architectural decisions made in designing and implementing **FeatureHub + DataGuard**, detailing the rationale, evaluated alternatives, and deliberate engineering trade-offs.

---

## 1. Online Feature Store: Redis 7.2

- **Decision:** Use **Redis** as the online key-value storage layer for real-time feature vectors.
- **Reason:** Real-time ML inference for fraud classification requires sub-10ms end-to-end API SLAs. Redis stores data entirely in-memory with single-threaded event-loop execution, avoiding disk seek latency. In our benchmark harness, Redis achieved **1.62 ms P99 retrieval latency**.
- **Alternative Evaluated:** Cassandra / ScyllaDB or PostgreSQL JSONB.
- **Trade-Off:** Redis requires sufficient RAM to hold the entire working dataset. It trades complex relational querying and historical time-series analytics for raw single-key point-lookup throughput.

---

## 2. Metadata, Contracts & Incident Datastore: PostgreSQL 16

- **Decision:** Use **PostgreSQL 16** as the relational metadata repository for data contracts, contract version history, pipeline run telemetry, and incident lifecycles.
- **Reason:** Data contracts require ACID compliance, schema version constraints, unique index deduplication, foreign key cascades, and complex SQL joins for audit logging. PostgreSQL provides rock-solid consistency, robust JSONB support for contract schemas, and native timestamp indexing.
- **Alternative Evaluated:** MongoDB / DocumentDB or DynamoDB.
- **Trade-Off:** Relational schemas require migrations and connection pooling management, whereas a NoSQL store would offer schemaless ingestion at the cost of referential integrity and transaction guarantees.

---

## 3. Pipeline Orchestration: Apache Airflow 2.9

- **Decision:** Use **Apache Airflow 2.9** for scheduling, monitoring, and dependency management across the 26 production pipelines.
- **Reason:** Airflow represents the industry standard for Python-native DAG orchestration. It provides mature retry policies, task-level SLA tracking, dynamic task generation, and native integration hooks for PostgreSQL, Docker, and OpenLineage.
- **Alternative Evaluated:** Dagster or Prefect.
- **Trade-Off:** Airflow has heavier container resource requirements (scheduler, webserver, database) compared to lightweight libraries. We mitigated this by providing a lightweight Public Gateway Demo Mode that operates without spinning up the heavy Airflow cluster.

---

## 4. Lineage & Provenance: OpenLineage Standard

- **Decision:** Adopt the **OpenLineage standard** (emitting JSON RunEvents for `START`, `COMPLETE`, and `FAIL` states) rather than proprietary metadata logging.
- **Reason:** OpenLineage provides an open, vendor-neutral specification for capturing dataset facets, job facets, and column-level transformations. It enables cross-system graph rendering and guarantees compatibility with tools like Marquez.
- **Alternative Evaluated:** Custom internal metadata tables or static graph JSONs.
- **Trade-Off:** Adhering to the OpenLineage schema requires strictly formatted event schemas and facet serialization overhead during pipeline runs.

---

## 5. Data Quality Engine: Great Expectations 1.x

- **Decision:** Use **Great Expectations** for declarative, contract-aligned data quality suites before feature materialization.
- **Reason:** Great Expectations decouples test assertions from data storage engines, enabling portable, human-readable expectations (e.g. nullability, value ranges, type conformance). Running in-memory over Pandas/Arrow tables achieved **344,340 rows/sec validation throughput**.
- **Alternative Evaluated:** Soda Core or custom assert scripts.
- **Trade-Off:** Great Expectations carries package weight and complex configuration objects, but provides comprehensive test documentation and structured diagnostic results.

---

## 6. Unified Presentation & Recruiter Console: Streamlit

- **Decision:** Build the Unified Platform Dashboard (`apps/unified-dashboard/`) using **Streamlit** with a custom CSS design system.
- **Reason:** Streamlit enables rapid Python-native dashboard development with real-time reactive state, direct Plotly visualization integration, and zero front-end build step overhead. This allowed us to build 12 rich pages (contracts, schema diffs, DAGs, lineage graphs, live inference, and benchmarks) in days while connecting directly to live Python services.
- **Alternative Evaluated:** React / Next.js with FastAPI backend.
- **Trade-Off:** Streamlit re-executes Python scripts on user interactions, which requires careful session-state caching and client connection management compared to a client-side SPA.

---

## 7. Public Deployment Strategy: Defense-in-Depth Gateway

- **Decision:** Deploy a lightweight **Public Gateway API** and Unified Dashboard over Cloudflare Anycast tunnels while keeping internal datastores (5432, 6379, 8080) completely private.
- **Reason:** Allows recruiters and evaluators to test all 12 platform capabilities over HTTPS without risking credential leaks, arbitrary database modifications, or requiring high-cost cloud compute.
- **Alternative Evaluated:** Hosting full multi-node Kubernetes cluster on AWS EKS with public load balancers.
- **Trade-Off:** The public demo runs with deterministic synthetic entities rather than executing heavy 100,000-row batch backfills live on the public server.
