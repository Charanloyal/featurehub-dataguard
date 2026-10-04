"""
Page 6: Real-Time ML Fraud Prediction UI
Interactive inference console calling the live FeatureHub prediction API & trained ML model.
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime, timezone
from apps.unified_dashboard.services.platform_client import PlatformClient
from apps.unified_dashboard.components.banners import get_status_badge_html
from apps.unified_dashboard.config import DEFAULT_ENTITY_ID


def render_page(client: PlatformClient, demo_mode: bool = False):
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">🤖 Real-Time ML Inference Console</div>
        <div class="hero-subtitle">Online feature retrieval from Redis combined with trained fraud risk classification</div>
    </div>
    """, unsafe_allow_html=True)

    if demo_mode:
        st.info("🎯 **Online Serving in Action:** Enter a customer ID and transaction amount. FeatureHub pulls pre-computed velocity features from Redis in < 1ms and passes the unified feature vector to the trained Scikit-Learn fraud model.")

    fh = client.fh

    # Transaction Form Inputs
    st.subheader("Simulate Real-Time Payment Transaction")
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        customer_id = st.text_input("Customer ID", value=DEFAULT_ENTITY_ID)
        channel = st.selectbox("Transaction Channel", ["WEB", "MOBILE_APP", "POS_TERMINAL", "ATM"])
    with fcol2:
        amount = st.number_input("Transaction Amount ($ USD)", min_value=0.50, max_value=25000.0, value=285.50, step=10.0)
        merchant_id = st.text_input("Merchant ID", value="merch_000042")
    with fcol3:
        ts_now = datetime.now(timezone.utc).isoformat()
        st.text_input("Transaction Timestamp (UTC)", value=ts_now, disabled=True)
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        predict_btn = st.button("⚡ Score Transaction with ML Model", use_container_width=True)

    if predict_btn or demo_mode:
        t0 = time.perf_counter()
        with st.spinner("Retrieving online Redis feature vector and computing inference..."):
            pred_res = fh.predict(
                customer_id=customer_id,
                transaction_amount=float(amount),
                merchant_id=merchant_id,
                channel=channel,
                timestamp=ts_now
            )
        infer_latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        risk_score = pred_res.get("risk_score", 0.0)
        is_fraud = pred_res.get("prediction", 0) == 1
        model_version = pred_res.get("model_version", "v1.0.0")
        feat_ts = pred_res.get("feature_timestamp", "Recent")
        features_used = pred_res.get("features_used", {})

        st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
        st.subheader("Model Decision & Real-Time Scoring Diagnostics")

        # Result Banner
        dcol1, dcol2, dcol3, dcol4 = st.columns(4)
        with dcol1:
            verdict_text = "FRAUD / SUSPICIOUS" if is_fraud else "LEGITIMATE / APPROVED"
            verdict_badge = "FAILED" if is_fraud else "SUCCESS"
            st.metric("Model Classification", verdict_text)
            st.markdown(get_status_badge_html(verdict_badge), unsafe_allow_html=True)
        with dcol2:
            st.metric("Fraud Risk Score", f"{risk_score:.4f}", delta="High Risk" if is_fraud else "Normal")
        with dcol3:
            st.metric("Inference Latency", f"{infer_latency_ms} ms", delta="Sub-10ms SLA")
        with dcol4:
            st.metric("Model Version", model_version, delta=f"Online Redis Sync")

        # Feature Vector Breakdown
        st.markdown("#### Feature Attribution: Online Redis vs Request Time Inputs")
        
        feat_rows = []
        for k, v in features_used.items():
            feat_rows.append({
                "Feature Name": k,
                "Value": f"{v:.4f}" if isinstance(v, float) else str(v),
                "Source Engine": "⚡ Redis Online Store (Materialized)",
                "Feature Snapshot Timestamp": feat_ts
            })

        feat_rows.append({
            "Feature Name": "transaction_amount",
            "Value": f"${amount:.2f}",
            "Source Engine": "🌐 Live API Payload (Request Time)",
            "Feature Snapshot Timestamp": ts_now
        })
        feat_rows.append({
            "Feature Name": "channel",
            "Value": channel,
            "Source Engine": "🌐 Live API Payload (Request Time)",
            "Feature Snapshot Timestamp": ts_now
        })

        st.dataframe(pd.DataFrame(feat_rows), use_container_width=True)
