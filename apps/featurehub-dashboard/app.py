"""
FeatureHub Streamlit Dashboard
Multi-page production dashboard for Feature Registry, Online/Offline stores, PIT demo, Prediction UI, and Benchmarks.
"""

import sys
import json
import os
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from featurehub.registry.service import FeatureRegistryService
from featurehub.online_store.redis_store import RedisOnlineStore
from featurehub.inference.predictor import RealTimePredictor
from featurehub.point_in_time.pit_engine import PointInTimeJoinEngine

st.set_page_config(
    page_title="FeatureHub | Real-Time Feature Store",
    page_icon="⚡",
    layout="wide"
)

# Custom Styling
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E293B; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.0rem; color: #64748B; margin-bottom: 1.5rem; }
    .card { background-color: #F8FAFC; border-radius: 10px; padding: 1.2rem; border: 1px solid #E2E8F0; margin-bottom: 1rem; }
    .metric-value { font-size: 2.0rem; font-weight: 700; color: #0F172A; }
    .metric-label { font-size: 0.85rem; text-transform: uppercase; color: #64748B; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

registry = FeatureRegistryService()
online_store = RedisOnlineStore()
predictor = RealTimePredictor(online_store=online_store)

# Navigation
st.sidebar.title("⚡ FeatureHub Platform")
page = st.sidebar.radio("Navigation", [
    "1. Overview",
    "2. Feature Registry",
    "3. Online Store Explorer",
    "4. Point-in-Time Demo",
    "5. Real-Time Prediction UI",
    "6. Latency Benchmarks"
])

if page == "1. Overview":
    st.markdown("<div class='main-header'>FeatureHub: Real-Time Feature Store</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Low-latency feature registry, point-in-time correctness, and Redis online serving.</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    features = registry.list_features()
    groups = registry.list_groups()

    with c1:
        st.markdown(f"<div class='card'><div class='metric-label'>Total Features</div><div class='metric-value'>{len(features)}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='card'><div class='metric-label'>Feature Groups</div><div class='metric-value'>{len(groups)}</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='card'><div class='metric-label'>Online Store</div><div class='metric-value'>Redis 7.2</div></div>", unsafe_allow_html=True)
    with c4:
        st.markdown("<div class='card'><div class='metric-label'>Serving SLA</div><div class='metric-value'>Sub-12ms p99</div></div>", unsafe_allow_html=True)

    st.subheader("System Architecture Flow")
    st.code("""
Historical Data (PostgreSQL / Parquet)
      ↓
Feature Computation (Windowed Aggregates)
      ↓
Offline Store (Parquet) ──→ Point-in-Time Join ──→ Zero-Leakage ML Model Training
      ↓
Materialization Pipeline
      ↓
Online Store (Redis Key-Value)
      ↓
FastAPI Prediction Endpoint (Real-Time Inference)
    """, language="text")

elif page == "2. Feature Registry":
    st.markdown("<div class='main-header'>Feature Registry Catalog</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        entity_filter = st.selectbox("Filter by Entity", ["All", "customer", "account", "merchant", "transaction"])
    with col2:
        group_filter = st.selectbox("Filter by Group", ["All"] + [g["group_name"] for g in registry.list_groups()])

    feat_list = registry.list_features(
        entity=None if entity_filter == "All" else entity_filter,
        group=None if group_filter == "All" else group_filter
    )
    
    df_feat = pd.DataFrame(feat_list)
    if not df_feat.empty:
        st.dataframe(df_feat[['feature_name', 'feature_group', 'entity_type', 'data_type', 'freshness_sla_minutes', 'description']], use_container_width=True)
    else:
        st.info("No features matched selected filters.")

elif page == "3. Online Store Explorer":
    st.markdown("<div class='main-header'>Redis Online Store Explorer</div>", unsafe_allow_html=True)
    
    cid = st.text_input("Enter Customer Entity ID", "cust_000001")
    if st.button("Lookup Features in Redis"):
        data = online_store.get_online_features(entity_name="customer", entity_id=cid)
        if data:
            st.success(f"Entity '{cid}' retrieved successfully!")
            st.json(data)
        else:
            st.warning(f"Entity '{cid}' not found in online store. Run 'make seed' or materialization pipeline.")

elif page == "4. Point-in-Time Demo":
    st.markdown("<div class='main-header'>Point-in-Time Correctness & Leakage Prevention Demo</div>", unsafe_allow_html=True)
    st.info("Demonstrates the critical difference between NAIVE (current lookup) and RIGHT (point-in-time lookup) during ML training dataset generation.")

    obs_time = "2026-01-10 12:00:00"
    st.write(f"**Target Event Timestamp ($T$)**: `{obs_time}`")

    c1, c2 = st.columns(2)
    with c1:
        st.error("❌ NAIVE (Current Lookup)")
        st.caption("Fetches latest feature value regardless of timestamp. Causes severe target leakage!")
        st.write("Feature value at 12:05 (Future): `cust_txn_count_1h = 999`")
    with c2:
        st.success("✅ RIGHT (Point-In-Time Join)")
        st.caption("Matches features strictly where feature_timestamp <= T.")
        st.write("Feature value at 11:50 (Past): `cust_txn_count_1h = 2`")

elif page == "5. Real-Time Prediction UI":
    st.markdown("<div class='main-header'>Real-Time Fraud Risk Prediction</div>", unsafe_allow_html=True)
    
    with st.form("predict_form"):
        customer_id = st.text_input("Customer ID", "cust_000001")
        amount = st.number_input("Transaction Amount ($)", value=2450.0, min_value=0.01)
        merchant_id = st.text_input("Merchant ID", "merch_00001")
        channel = st.selectbox("Payment Channel", ["WEB", "MOBILE_APP", "POS", "ATM", "WIRE"])
        submitted = st.form_submit_button("Compute Fraud Probability")

    if submitted:
        res = predictor.predict_fraud_risk(
            customer_id=customer_id,
            transaction_amount=amount,
            merchant_id=merchant_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            channel=channel
        )
        st.subheader("Inference Result")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Fraud Risk Score", f"{res['risk_score'] * 100:.1f}%")
        with col2:
            pred_label = "HIGH RISK (FRAUD)" if res['prediction'] == 1 else "LOW RISK (APPROVED)"
            st.metric("Prediction Flag", pred_label)

        st.subheader("Online Feature Vector Used")
        st.json(res["features_used"])

elif page == "6. Latency Benchmarks":
    st.markdown("<div class='main-header'>Empirical Latency & Throughput Benchmarks</div>", unsafe_allow_html=True)
    
    bench_file = BASE_DIR / "featurehub" / "benchmarks" / "results.json"
    if bench_file.exists():
        with open(bench_file, "r") as f:
            bench_data = json.load(f)
        
        st.subheader("Redis Lookup & Prediction Pipeline Performance")
        st.json(bench_data)
    else:
        st.warning("Benchmark results file not found. Run 'make benchmark' to generate results.")
