"""
Unified Data Platform Dashboard - Main Application Entrance
Streamlit production console unifying FeatureHub and DataGuard.
"""

import sys
from pathlib import Path

# Add project root and dashboard directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DASHBOARD_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

# Register module alias for apps.unified_dashboard
import types
if "apps.unified_dashboard" not in sys.modules:
    import apps
    ud_mod = types.ModuleType("apps.unified_dashboard")
    ud_mod.__path__ = [str(DASHBOARD_DIR)]
    sys.modules["apps.unified_dashboard"] = ud_mod
    setattr(apps, "unified_dashboard", ud_mod)

import streamlit as st
from apps.unified_dashboard.config import APP_TITLE, APP_SUBTITLE, ASSETS_DIR
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.navbar import render_sidebar
from apps.unified_dashboard.pages import (
    p01_overview,
    p02_pipelines,
    p03_featurehub,
    p04_online_store,
    p05_pit_demo,
    p06_ml_prediction,
    p07_dataguard,
    p08_schema_diff,
    p09_data_quality,
    p10_lineage,
    p11_incidents,
    p12_ci_cd,
    p13_benchmarks,
    p14_health,
    p15_demo_center,
)

# Page configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject Custom Stylesheet
css_path = ASSETS_DIR / "style.css"
if css_path.exists():
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize Platform Client in session state
if "platform_client" not in st.session_state:
    st.session_state["platform_client"] = PlatformClient()

client = st.session_state["platform_client"]

# Render Sidebar Navigation
selected_page, demo_mode = render_sidebar()

# Routing table
if selected_page == "1. Platform Overview":
    p01_overview.render_page(client, demo_mode)

elif selected_page == "2. Pipeline Operations":
    p02_pipelines.render_page(client, demo_mode)

elif selected_page == "3. FeatureHub":
    sub_tab = st.radio("FeatureHub Explorer View", ["Feature Registry Catalog", "Redis Online Store Monitor", "Point-in-Time Demo"], horizontal=True)
    if sub_tab == "Feature Registry Catalog":
        p03_featurehub.render_page(client, demo_mode)
    elif sub_tab == "Redis Online Store Monitor":
        p04_online_store.render_page(client, demo_mode)
    elif sub_tab == "Point-in-Time Demo":
        p05_pit_demo.render_page(client, demo_mode)

elif selected_page == "4. DataGuard":
    p07_dataguard.render_page(client, demo_mode)

elif selected_page == "5. Data Quality":
    p09_data_quality.render_page(client, demo_mode)

elif selected_page == "6. Schema & Contracts":
    sub_tab = st.radio("Schema Governance View", ["Schema Diff & Compatibility Engine", "GitHub CI/CD Gating Simulator"], horizontal=True)
    if sub_tab == "Schema Diff & Compatibility Engine":
        p08_schema_diff.render_page(client, demo_mode)
    else:
        p12_ci_cd.render_page(client, demo_mode)

elif selected_page == "7. Lineage":
    p10_lineage.render_page(client, demo_mode)

elif selected_page == "8. Incidents":
    p11_incidents.render_page(client, demo_mode)

elif selected_page == "9. ML Prediction":
    p06_ml_prediction.render_page(client, demo_mode)

elif selected_page == "10. Benchmarks":
    p13_benchmarks.render_page(client, demo_mode)

elif selected_page == "11. System Health":
    p14_health.render_page(client, demo_mode)

elif selected_page == "12. Demo Center":
    p15_demo_center.render_page(client, demo_mode)

else:
    p01_overview.render_page(client, demo_mode)
