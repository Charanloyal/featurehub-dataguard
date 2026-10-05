# Live Public Demo Deployment Guide

This document details the production deployment, architecture, operations, rollback, and security design for the public live demonstration of **FeatureHub + DataGuard**.

---

## 1. Deployment Architecture

The deployment implements a clean defense-in-depth isolation boundary separating public traffic from private persistence layers.

```
                      [ Recruiter / Browser Client ]
                                    │
                                    ▼ (HTTPS / TLS 1.3)
       ┌─────────────────────────────────────────────────────────┐
       │                 PUBLIC ACCESS PERIMETER                 │
       │                                                         │
       │   Unified Streamlit Dashboard (Port 8505)              │
       │   Public API Gateway (Port 8000, FastAPI)               │
       └────────────┬─────────────────────────────┬──────────────┘
                    │                             │
        (Safe JSON Proxies)               (Controlled Endpoints)
                    │                             │
       ┌────────────▼─────────────────────────────▼──────────────┐
       │                PRIVATE INTERNAL SERVICES                │
       │                                                         │
       │   • PostgreSQL 16 (Port 5432 - Internal Only)           │
       │   • Redis 7.2 (Port 6379 - Internal Only)               │
       │   • Airflow 2.9 (Port 8080 - Internal Only)             │
       │   • Prometheus (Port 9090 - Internal Only)              │
       │   • Grafana (Port 3000 - Internal Only)                 │
       │   • FeatureHub Internal API (Port 8010)                 │
       │   • DataGuard Internal API (Port 8001)                  │
       └─────────────────────────────────────────────────────────┘
```

### Key Architectural Principles
- **No Unrestricted Database Exposure:** Ports `5432`, `6379`, `8080`, `9090`, and `3000` are bound exclusively to `127.0.0.1` and are never exposed directly to the internet.
- **Two Deployment Modes:**
  1. `LOCAL_FULL`: Full Docker stack running local PostgreSQL, Redis, and Apache Airflow with live ETL pipelines.
  2. `PUBLIC_DEMO`: Lightweight, secure public deployment exposing deterministic demo data and controlled endpoints.
- **Strict Read-Only Demonstration:** Arbitrary SQL execution and administrative data-deletion APIs are blocked at the public gateway.

---

## 2. Required Environment Variables

Configuration is loaded from environment variables (or `.env`):

| Variable | Description | Default | Mode |
|---|---|---|---|
| `PLATFORM_MODE` | Operating mode (`PUBLIC_DEMO` or `LOCAL_FULL`) | `PUBLIC_DEMO` | Public |
| `PUBLIC_API_HOST` | Host interface for public gateway | `0.0.0.0` | Public |
| `PUBLIC_API_PORT` | Port for public gateway | `8000` | Public |
| `PUBLIC_API_URL` | Public base URL for API queries | `http://localhost:8000` | Public |
| `PUBLIC_DASHBOARD_PORT` | Port for unified dashboard | `8505` | Public |
| `PUBLIC_CORS_ORIGINS` | Permitted origins for CORS | `*` (safe demo) | Public |
| `LOCAL_POSTGRES_HOST` | Internal PostgreSQL host | `localhost` | Local Full |
| `LOCAL_POSTGRES_PORT` | Internal PostgreSQL port | `5432` | Local Full |
| `LOCAL_REDIS_HOST` | Internal Redis host | `localhost` | Local Full |
| `LOCAL_REDIS_PORT` | Internal Redis port | `6379` | Local Full |

---

## 3. Build Command

To prepare dependencies and assets in a clean environment:

```bash
# 1. Clone repository
git clone https://github.com/Charanloyal/featurehub-dataguard.git
cd featurehub-dataguard

# 2. Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\Activate.ps1

# 3. Install platform dependencies
pip install -r requirements.txt
pip install -e .
```

---

## 4. Start Command

### Running in Public Demo Mode:
```bash
# Start Public API Gateway
python apps/public-api/run.py 8000 &

# Start Unified Dashboard
streamlit run apps/unified-dashboard/app.py --server.port 8505 --server.headless true
```

### Running in Local Full Mode (Docker):
```bash
docker compose up -d postgres redis airflow-webserver airflow-scheduler
python apps/public-api/run.py 8000 &
streamlit run apps/unified-dashboard/app.py --server.port 8505
```

---

## 5. Health Check

The platform exposes two public monitoring endpoints:

- **Liveness & Mode Check:** `GET /health`
  ```json
  {
    "status": "DEMO MODE",
    "timestamp": "2026-10-05T02:22:02Z",
    "mode": "PUBLIC_DEMO",
    "api_version": "1.0.0",
    "demo_data_loaded": true
  }
  ```
- **Observability Status:** `GET /platform/status`
  ```json
  {
    "platform_name": "FeatureHub + DataGuard",
    "mode": "PUBLIC_DEMO",
    "status": "OPERATIONAL",
    "metrics": {
      "registered_features": 122,
      "feature_groups": 6,
      "active_contracts": 27,
      "production_pipelines": 26,
      "quality_pass_rate": 96.1,
      "open_incidents": 1
    }
  }
  ```

---

## 6. Logs & Observability

All API calls are intercepted by structured logging middleware:
- Logs include: Timestamp, HTTP Method, Path, Status Code, and Processing Latency (ms).
- Secrets, tokens, and passwords are never logged.

Sample log output:
```text
2026-10-05 02:22:02,578 [INFO] public-api: HTTP GET /health -> 200 (4.58ms)
2026-10-05 02:23:23,443 [INFO] public-api: HTTP GET /online/features/cust_000001 -> 200 (2.34ms)
2026-10-05 02:23:28,663 [INFO] public-api: HTTP POST /schema/diff -> 200 (2.29ms)
```

---

## 7. Redeployment

To perform a zero-downtime or rolling redeployment:
1. Pull new release commit: `git pull origin main`
2. Run database migration / contract sync if any: `python scripts/register_contracts.py`
3. Restart public API gateway:
   ```bash
   pkill -f "apps/public-api/run.py"
   python apps/public-api/run.py 8000 &
   ```
4. Verify `/health` returns status `200`.

---

## 8. Rollback

In the event of a regression or unexpected failure:
1. Check git commit history: `git log -n 5 --oneline`
2. Check out previous verified commit: `git checkout <previous_verified_commit>`
3. Run the deterministic reset script:
   ```bash
   python scripts/reset_demo.py
   ```
4. Restart the public services.

---

## 9. Demo Mode Safeguards

When `PLATFORM_MODE=PUBLIC_DEMO`:
- Real ML inference executes against Scikit-Learn pipelines without needing cloud GPU/heavy clusters.
- Schema diffing executes against genuine Pydantic/DataGuard compatibility rules.
- Great Expectations reports display genuine verification runs.
- Entities are deterministically reset via `python scripts/reset_demo.py`.
- No internal databases can be wiped or modified by public visitors.

---

## 10. Security Considerations

- **No Root Privileges:** Services run under unprivileged service users.
- **Security Headers:** The public API automatically injects:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- **Zero Committed Secrets:** The repository contains no committed passwords, API keys, or production secrets.

---

## 11. Cost Considerations

- The public demo is designed to run efficiently on low-footprint cloud compute (e.g. 1 vCPU / 2GB RAM container or VM).
- Zero cloud database egress costs: internal read queries are cached and deterministic fallbacks prevent runaway database queries.
- Total hosting cost can remain within the free tier of major cloud or container providers.

---

## 12. Troubleshooting

| Issue | Symptom | Remediation |
|---|---|---|
| Port Conflict | `Address already in use: 8000` | Kill previous process: `lsof -i :8000` or use another port with `python apps/public-api/run.py <port>` |
| Corrupted Demo State | Unexpected entity or diff values | Run `python scripts/reset_demo.py` to restore baseline state |
| Public Tunnel Drop | Remote URL unreachable | Re-run SSH tunnel: `ssh -R 80:localhost:8505 nokey@localhost.run` |
| Redis Disconnected | Fallback to in-memory cache | Normal in `PUBLIC_DEMO` mode; for `LOCAL_FULL`, start Redis with `docker compose up -d redis` |
