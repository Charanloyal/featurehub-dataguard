"""
Unified Data Platform Dashboard Configuration
Settings for API endpoints, datastores, timeouts, paths, and presentation.
"""

import os
from pathlib import Path

# Paths
DASHBOARD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DASHBOARD_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONTRACTS_DIR = PROJECT_ROOT / "dataguard" / "contracts"
FEATUREHUB_BENCHMARKS_DIR = PROJECT_ROOT / "featurehub" / "benchmarks"
DATAGUARD_BENCHMARKS_DIR = PROJECT_ROOT / "dataguard" / "benchmarks"
ASSETS_DIR = DASHBOARD_DIR / "assets"

# Service URLs
FEATUREHUB_API_URL = os.getenv("FEATUREHUB_API_URL", "http://127.0.0.1:8010")
DATAGUARD_API_URL = os.getenv("DATAGUARD_API_URL", "http://127.0.0.1:8001")
AIRFLOW_URL = os.getenv("AIRFLOW_URL", "http://localhost:8080")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")

# Database & Datastores
POSTGRES_USER = os.getenv("POSTGRES_USER", "platform_admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "platform_secure_pass")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "featurehub_dataguard")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Network Timeouts
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "2.5"))
HEALTH_CHECK_TIMEOUT_SECONDS = float(os.getenv("HEALTH_CHECK_TIMEOUT_SECONDS", "0.8"))

# UI & Presentation Defaults
DEFAULT_ENTITY_ID = "cust_000001"
DEFAULT_DATASET = "customer_features"
APP_TITLE = "FeatureHub + DataGuard | Unified Data Platform"
APP_SUBTITLE = "Reliable Data Infrastructure for Production ML"
VERSION = "3.1.0"
