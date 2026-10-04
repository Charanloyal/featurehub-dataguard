"""
Hero Architecture View Component
Renders a visual, interactive pipeline architecture topology connecting
Data Sources -> Airflow -> DataGuard -> Feature Compute -> FeatureHub -> Offline/Online Stores -> ML Inference.
"""

import streamlit as st


def render_hero_architecture():
    """Render interactive visual platform architecture topology."""
    st.markdown("""
    <div class="architecture-container">
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="font-size: 0.82rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #2563EB;">
                End-to-End Enterprise Architecture
            </div>
            <div style="font-size: 1.35rem; font-weight: 800; color: #0F172A; margin-top: 4px;">
                FeatureHub + DataGuard Integrated Data Platform
            </div>
            <div style="font-size: 0.88rem; color: #64748B; max-width: 650px; margin: 6px auto 0;">
                Pre-materialization circuit breaker: contract enforcement, backward compatibility schema diffing, Great Expectations suites, and OpenLineage provenance.
            </div>
        </div>

        <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            <!-- Tier 1: Data Sources -->
            <div style="background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; padding: 10px 24px; font-weight: 700; color: #1E293B; box-shadow: 0 1px 2px rgba(0,0,0,0.05); min-width: 320px; text-align: center;">
                💾 DATA SOURCES <span style="font-size: 0.8rem; font-weight: 500; color: #64748B;">(Raw Transactions Parquet / Postgres)</span>
            </div>

            <div style="color: #94A3B8; font-size: 1.2rem; line-height: 1;">↓</div>

            <!-- Tier 2: Airflow Orchestration -->
            <div style="background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; padding: 10px 24px; font-weight: 700; color: #1E293B; box-shadow: 0 1px 2px rgba(0,0,0,0.05); min-width: 320px; text-align: center;">
                🌪️ AIRFLOW ORCHESTRATION <span style="font-size: 0.8rem; font-weight: 500; color: #64748B;">(16 Scheduled DAGs & Dynamic SLAs)</span>
            </div>

            <div style="color: #94A3B8; font-size: 1.2rem; line-height: 1;">↓</div>

            <!-- Tier 3: DataGuard Reliability Core -->
            <div style="background: #F0FDF4; border: 2px solid #86EFAC; border-radius: 10px; padding: 16px 28px; width: 100%; max-width: 580px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
                <div style="font-size: 1.05rem; font-weight: 800; color: #166534; text-align: center; margin-bottom: 10px;">
                    🛡️ DATAGUARD RELIABILITY PLATFORM
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; text-align: center;">
                    <div style="background: #FFFFFF; border: 1px solid #BBF7D0; border-radius: 6px; padding: 8px 4px;">
                        <div style="font-size: 0.75rem; font-weight: 700; color: #15803D;">CONTRACTS</div>
                        <div style="font-size: 0.7rem; color: #64748B;">25+ Schemas</div>
                    </div>
                    <div style="background: #FFFFFF; border: 1px solid #BBF7D0; border-radius: 6px; padding: 8px 4px;">
                        <div style="font-size: 0.75rem; font-weight: 700; color: #15803D;">SCHEMA DIFF</div>
                        <div style="font-size: 0.7rem; color: #64748B;">CI Compatibility</div>
                    </div>
                    <div style="background: #FFFFFF; border: 1px solid #BBF7D0; border-radius: 6px; padding: 8px 4px;">
                        <div style="font-size: 0.75rem; font-weight: 700; color: #15803D;">QUALITY</div>
                        <div style="font-size: 0.7rem; color: #64748B;">Great Expectations</div>
                    </div>
                    <div style="background: #FFFFFF; border: 1px solid #BBF7D0; border-radius: 6px; padding: 8px 4px;">
                        <div style="font-size: 0.75rem; font-weight: 700; color: #15803D;">LINEAGE</div>
                        <div style="font-size: 0.7rem; color: #64748B;">OpenLineage Graph</div>
                    </div>
                </div>
            </div>

            <div style="color: #94A3B8; font-size: 1.2rem; line-height: 1;">↓</div>

            <!-- Tier 4: Feature Computation -->
            <div style="background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; padding: 10px 24px; font-weight: 700; color: #1E293B; box-shadow: 0 1px 2px rgba(0,0,0,0.05); min-width: 320px; text-align: center;">
                ⚙️ FEATURE COMPUTATION <span style="font-size: 0.8rem; font-weight: 500; color: #64748B;">(Vectorized Rolling Windows ~550ms)</span>
            </div>

            <div style="color: #94A3B8; font-size: 1.2rem; line-height: 1;">↓</div>

            <!-- Tier 5: FeatureHub Dual Store Engine -->
            <div style="background: #EFF6FF; border: 2px solid #93C5FD; border-radius: 10px; padding: 16px 28px; width: 100%; max-width: 580px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
                <div style="font-size: 1.05rem; font-weight: 800; color: #1E40AF; text-align: center; margin-bottom: 10px;">
                    ⚡ FEATUREHUB REAL-TIME FEATURE STORE (122+ Features)
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; text-align: center;">
                    <div style="background: #FFFFFF; border: 1px solid #BFDBFE; border-radius: 6px; padding: 10px 8px;">
                        <div style="font-size: 0.8rem; font-weight: 700; color: #1E40AF;">📁 OFFLINE STORE</div>
                        <div style="font-size: 0.72rem; color: #475569; margin-top: 2px;">Partitioned Parquet Lake</div>
                        <div style="font-size: 0.68rem; color: #2563EB; font-weight: 600; margin-top: 4px;">Zero-Leakage PIT Joins</div>
                    </div>
                    <div style="background: #FFFFFF; border: 1px solid #BFDBFE; border-radius: 6px; padding: 10px 8px;">
                        <div style="font-size: 0.8rem; font-weight: 700; color: #1E40AF;">⚡ REDIS ONLINE STORE</div>
                        <div style="font-size: 0.72rem; color: #475569; margin-top: 2px;">Redis 7.2 Key-Value Cache</div>
                        <div style="font-size: 0.68rem; color: #059669; font-weight: 600; margin-top: 4px;">Sub-millisecond Retrieval (&lt; 1ms)</div>
                    </div>
                </div>
            </div>

            <div style="color: #94A3B8; font-size: 1.2rem; line-height: 1;">↓</div>

            <!-- Tier 6: Real-time ML Inference -->
            <div style="background: #FAF5FF; border: 1px solid #D8B4FE; border-radius: 8px; padding: 12px 28px; font-weight: 800; color: #6B21A8; box-shadow: 0 2px 4px rgba(0,0,0,0.04); min-width: 380px; text-align: center;">
                🤖 REAL-TIME ML INFERENCE <span style="font-size: 0.8rem; font-weight: 500; color: #7E22CE;">(FastAPI &lt; 1ms Fraud Scoring)</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Interactive Navigation Buttons Below Architecture
    st.markdown("<div style='text-align: center; font-size: 0.85rem; font-weight: 600; color: #64748B; margin: 12px 0 8px;'>DRILL DOWN DIRECTLY INTO SUBSYSTEM:</div>", unsafe_allow_html=True)
    bcols = st.columns(6)
    with bcols[0]:
        if st.button("🌪️ Pipelines", use_container_width=True):
            st.session_state["nav_selection"] = "2. Pipeline Operations"
            st.rerun()
    with bcols[1]:
        if st.button("🛡️ DataGuard", use_container_width=True):
            st.session_state["nav_selection"] = "4. DataGuard"
            st.rerun()
    with bcols[2]:
        if st.button("⚡ FeatureHub", use_container_width=True):
            st.session_state["nav_selection"] = "3. FeatureHub"
            st.rerun()
    with bcols[3]:
        if st.button("📈 Quality", use_container_width=True):
            st.session_state["nav_selection"] = "5. Data Quality"
            st.rerun()
    with bcols[4]:
        if st.button("🕸️ Lineage", use_container_width=True):
            st.session_state["nav_selection"] = "7. Lineage"
            st.rerun()
    with bcols[5]:
        if st.button("🤖 Prediction", use_container_width=True):
            st.session_state["nav_selection"] = "9. ML Prediction"
            st.rerun()
