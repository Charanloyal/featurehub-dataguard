# Platform Limitations & Engineering Truth Disclosures

To uphold rigorous engineering integrity, this document explicitly details the boundaries, simplifications, and known constraints of **FeatureHub + DataGuard**. Transparent disclosure of limitations demonstrates maturity and makes verified achievements credible.

---

## 1. Benchmark Execution Environment vs. Public Cloud Production
- **Disclosed Boundary:** The verified low latencies—specifically **Redis Online Lookup P99 = 1.62 ms** and **ML Prediction API P99 = 6.62 ms**—were measured on a dedicated local test harness (Windows 11 x86_64, Redis 7.2 over loopback socket, Python 3.13).
- **Production Reality:** In a distributed multi-region cloud deployment (e.g., AWS EKS across availability zones with TLS termination and API gateway hops), network transit alone typically adds 5–15 ms. Local socket latencies are **never represented as public-cloud WAN production metrics**.

---

## 2. Synthetic Data vs. Real Financial Logs
- **Disclosed Boundary:** The dataset of 5,000 customers, 6,500 accounts, 1,000 merchants, and 100,000 transactions is synthetically generated via statistical probability distributions (`scripts/seed_data.py`).
- **Production Reality:** While realistic correlation structures and fraud anomalies were injected (e.g. rapid-fire velocities, null spikes, and category deviations), synthetic data cannot model the full noise, missingness, and subtle behavioral drift present in real banking customer logs.

---

## 3. Public Demo Architecture vs. Local Full Platform
- **Disclosed Boundary:** The public live demo (`https://sympathy-mesh-microphone-oakland.trycloudflare.com`) runs on a lightweight Public Gateway architecture exposing deterministic demo entities.
- **Production Reality:** The full heavy multi-container Docker platform (PostgreSQL 16, Redis 7.2, Apache Airflow scheduler/webserver, Prometheus, Grafana) is designed for local development. We do not claim the public cloud instance hosts the full heavy distributed infrastructure.

---

## 4. Single-Machine Topology vs. Distributed Compute
- **Disclosed Boundary:** Feature computations, Great Expectations suites, and materialization jobs execute locally in Python using Pandas and PyArrow.
- **Production Reality:** At enterprise scale (> 100 million transactions/day), feature engineering and contract validations would be offloaded to distributed compute engines such as Apache Spark (Dataproc/EMR), Snowflake, or BigQuery.

---

## 5. Security & Authentication Scope
- **Disclosed Boundary:** The public demo mode operates with read-only controls, CORS policies, and rate-limiting, but omits enterprise SSO (OAuth2 / OIDC, SAML, or LDAP) and role-based access control (RBAC).
- **Production Reality:** A production internal data platform requires fine-grained column-level access control (CLAC), role-based ACLs for contract approval, and secret management via AWS Secrets Manager or HashiCorp Vault.

---

## 6. Incident Triage Metric: UNVERIFIED / DESIGN GOAL
- **Disclosed Boundary:** While automated root-cause indexing and incident filing complete in **5.44 ms**, the platform's design goal of **55% incident triage MTTR reduction** remains **UNVERIFIED**.
- **Production Reality:** Measuring human Mean Time to Resolution (MTTR) requires a longitudinal study with multiple engineering on-call rotations over several months. Single-engineer automated test environments cannot claim a verified human workflow metric.

---

## 7. Schema Breaking Change Evaluation Scope
- **Disclosed Boundary:** The **100.0% schema blocking result** reflects **100% of tested scenarios in the reproducible validation benchmark** (5 breaking evolutions, 3 safe backward-compatible evolutions).
- **Production Reality:** While the 8 scenarios cover primary SQL/YAML schema evolutions (column drops, narrowing types, enum deletions, nullability shifts), enterprise production databases may exhibit esoteric edge cases that require ongoing policy tuning.
