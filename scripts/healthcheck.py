"""
FeatureHub & DataGuard Infrastructure & Service Health Check Utility
Reports status, health, and operational diagnostics across platform components.
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import httpx
except ImportError:
    import requests as httpx

def check_health():
    print("============================================================")
    print("  FEATUREHUB & DATAGUARD HEALTH & INFRASTRUCTURE REPORT")
    print("============================================================")
    
    report = []

    # 1. FeatureHub API Health Endpoint
    try:
        r = httpx.get("http://127.0.0.1:8010/health", timeout=0.2)
        if r.status_code == 200:
            report.append({"service": "FeatureHub API", "status": "UP", "health": "HEALTHY", "reason": "Endpoint http://127.0.0.1:8010/health returned HTTP 200 OK"})
        else:
            report.append({"service": "FeatureHub API", "status": "DEGRADED", "health": "UNHEALTHY", "reason": f"Returned status code {r.status_code}"})
    except Exception as e:
        report.append({"service": "FeatureHub API", "status": "OFFLINE", "health": "STANDBY", "reason": "FastAPI server not currently running on port 8010"})

    # 2. DataGuard API Health Endpoint
    try:
        r = httpx.get("http://127.0.0.1:8001/health", timeout=0.2)
        if r.status_code == 200:
            report.append({"service": "DataGuard API", "status": "UP", "health": "HEALTHY", "reason": "Endpoint http://127.0.0.1:8001/health returned HTTP 200 OK"})
        else:
            report.append({"service": "DataGuard API", "status": "DEGRADED", "health": "UNHEALTHY", "reason": f"Returned status code {r.status_code}"})
    except Exception as e:
        report.append({"service": "DataGuard API", "status": "OFFLINE", "health": "STANDBY", "reason": "FastAPI server not currently running on port 8001"})

    # 3. PostgreSQL DataGuard Contract Registry
    try:
        from dataguard.contracts.registry import ContractRegistryService
        from sqlalchemy import text
        dg_registry = ContractRegistryService()
        with dg_registry.engine.connect() as conn:
            cnt_c = conn.execute(text("SELECT COUNT(*) FROM contract_registry")).scalar()
            cnt_v = conn.execute(text("SELECT COUNT(*) FROM contract_versions")).scalar()
        report.append({
            "service": "PostgreSQL Contract DB",
            "status": "UP",
            "health": "HEALTHY",
            "reason": f"PostgreSQL responsive ({cnt_c} contracts, {cnt_v} versions in {dg_registry.get_db_engine_name().upper()})"
        })
    except Exception as e:
        report.append({
            "service": "PostgreSQL Contract DB",
            "status": "OFFLINE",
            "health": "UNHEALTHY",
            "reason": f"PostgreSQL connection failed: {e}"
        })

    # 4. Redis Online Store Connection
    from featurehub.online_store.redis_store import RedisOnlineStore
    online_store = RedisOnlineStore()
    if online_store.is_connected():
        report.append({"service": "Redis Online Store", "status": "UP", "health": "HEALTHY", "reason": "Connected to active Redis socket on port 6379"})
    else:
        report.append({"service": "Redis Online Store", "status": "FALLBACK", "health": "DEGRADED", "reason": "Redis server container offline; operating on in-memory key-value fallback"})

    # 5. Feature Registry Database
    db_path = BASE_DIR / "data" / "platform_dev.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feature_registry")
            cnt = cursor.fetchone()[0]
            conn.close()
            report.append({"service": "Feature Registry DB", "status": "UP", "health": "HEALTHY", "reason": f"SQLite/Postgres platform database responsive ({cnt} features registered)"})
        except Exception as e:
            report.append({"service": "Feature Registry DB", "status": "ERROR", "health": "UNHEALTHY", "reason": str(e)})
    else:
        report.append({"service": "Feature Registry DB", "status": "UNINITIALIZED", "health": "UNHEALTHY", "reason": "Database file platform_dev.db does not exist. Run scripts/setup.py"})

    # Print Summary Table
    print(f"\n{'Service':<22} | {'Status':<10} | {'Health':<10} | {'Diagnostic Reason'}")
    print("-" * 90)
    for row in report:
        print(f"{row['service']:<22} | {row['status']:<10} | {row['health']:<10} | {row['reason']}")

    print("============================================================\n")

if __name__ == "__main__":
    check_health()
