"""
Setup and environment initialization script for FeatureHub & DataGuard platform.
Creates required local directory structures, database tables, and default configurations.
"""

import os
import sys
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DIRECTORIES = [
    BASE_DIR / "data" / "raw",
    BASE_DIR / "data" / "offline_store",
    BASE_DIR / "data" / "online_store",
    BASE_DIR / "data" / "models",
    BASE_DIR / "featurehub" / "benchmarks",
    BASE_DIR / "dataguard" / "benchmarks",
    BASE_DIR / "docs" / "benchmarks",
]

def init_environment():
    print("Initializing FeatureHub & DataGuard environment...")
    for dir_path in DIRECTORIES:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  [+] Directory ready: {dir_path.relative_to(BASE_DIR)}")

    # Initialize DataGuard Persistent Contract Registry in PostgreSQL
    try:
        from dataguard.contracts.registry import ContractRegistryService
        dg_registry = ContractRegistryService()
        print(f"  [+] DataGuard Contract Registry initialized in PostgreSQL ({dg_registry.get_db_engine_name().upper()})")
    except Exception as e:
        print(f"  [!] Warning: Could not initialize DataGuard in PostgreSQL: {e}")

    # Initialize local SQLite database fallback for FeatureHub dev testing without Postgres container
    sqlite_db_path = BASE_DIR / "data" / "platform_dev.db"
    init_sqlite_db(sqlite_db_path)
    print("Environment setup completed successfully.")

def init_sqlite_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feature_registry (
        feature_name TEXT PRIMARY KEY,
        feature_group TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        data_type TEXT NOT NULL,
        description TEXT,
        source_table TEXT,
        version TEXT DEFAULT 'v1',
        owner TEXT DEFAULT 'data-platform-team',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        freshness_sla_minutes INTEGER DEFAULT 60,
        status TEXT DEFAULT 'ACTIVE'
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quality_incidents (
        incident_id TEXT PRIMARY KEY,
        dataset_name TEXT NOT NULL,
        check_name TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT DEFAULT 'OPEN',
        error_message TEXT,
        pipeline_name TEXT,
        owner TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quality_validation_history (
        validation_id TEXT PRIMARY KEY,
        dataset_name TEXT NOT NULL,
        contract_version TEXT NOT NULL,
        total_checks INTEGER NOT NULL,
        passed_checks INTEGER NOT NULL,
        failed_checks INTEGER NOT NULL,
        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        details TEXT
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_environment()
