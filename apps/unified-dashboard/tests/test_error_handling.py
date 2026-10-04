"""
Tests for Dashboard Error Handling & Graceful Degradation
Ensures dashboard never crashes when an external endpoint or container is unreachable.
"""

import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.unified_dashboard.services.featurehub_client import FeatureHubClient
from apps.unified_dashboard.services.dataguard_client import DataGuardClient
from apps.unified_dashboard.services.platform_client import PlatformClient


def test_featurehub_client_unreachable_api():
    client = FeatureHubClient(api_url="http://127.0.0.1:59999", timeout=0.1)
    health = client.health()
    # Should seamlessly fall back to direct service or return DOWN without raising unhandled exception
    assert health["status"] in ["HEALTHY", "DEGRADED", "DOWN"]
    features = client.list_features()
    assert isinstance(features, list)
    assert len(features) >= 120


def test_dataguard_client_unreachable_api():
    client = DataGuardClient(api_url="http://127.0.0.1:59999", timeout=0.1)
    health = client.health()
    assert health["status"] in ["HEALTHY", "DEGRADED", "DOWN"]
    contracts = client.list_contracts()
    assert isinstance(contracts, list)
    assert len(contracts) >= 25


def test_online_features_nonexistent_entity():
    client = FeatureHubClient()
    res = client.get_online_features(entity_id="cust_nonexistent_999999")
    assert res is None or res == {}


def test_nonexistent_feature_lookup():
    client = FeatureHubClient()
    feat = client.get_feature("non_existent_feature_12345")
    assert feat is None
