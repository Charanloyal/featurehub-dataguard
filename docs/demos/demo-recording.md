# Screen Recording & Demo Video Guide
**Storyline:** The Self-Defending Data Platform in Action  
**Target Duration:** 2–3 Minutes  
**Target Audience:** Recruiters, Staff/Principal Data Engineers, Engineering Managers

---

## The Coherent Narrative Arc

The most impactful demonstration tells a single end-to-end story: **How the platform actively halts corrupted data, attributes blast radius, and safely resumes ML inference.**

```
Corrupted Raw Data Ingestion
             ↓
DataGuard Detects Failure (< 1s)
             ↓
Incident Filed in PostgreSQL & Owner Notified
             ↓
OpenLineage Graph Traces Affected Models
             ↓
Materialization Aborted (Circuit Breaker Tripped)
             ↓
Data Cleaned & Pipeline Rerun
             ↓
FeatureHub Online Store Updated (Redis)
             ↓
Live ML Fraud Model Scores Accurately
```

---

## Screen Recording Step-by-Step Script

### Phase 1: The Initial State (0:00 – 0:30)
1. Open the **Unified Dashboard** at the live URL or `http://localhost:8505`.
2. Start on **1. Platform Overview** showing healthy KPIs: 122 features, 27 contracts, 96.1% quality pass rate.
3. Show **9. ML Prediction** with customer `cust_000001` scoring normally (**LEGITIMATE**, score: 0.04).

### Phase 2: The Malformed Data Event (0:30 – 1:00)
1. Switch to terminal or **6. Schema & Contracts** / **5. Data Quality**.
2. Run bad data simulation:
   ```bash
   python scripts/generate_bad_data.py
   ```
3. Trigger the ingestion pipeline:
   ```bash
   python scripts/run_integrated_pipeline.py --simulate-failure
   ```
4. Point out the terminal / UI feedback:
   - Great Expectations check **FAILS** (unexpected NULLs and extreme range drift).
   - Pipeline **ABORTED** at Stage 4 (pre-materialization circuit breaker trips in `< 911 ms`).
   - Downstream Redis online feature cache is **PROTECTED** from poisoned values.

### Phase 3: Blast Radius & Incident Attribution (1:00 – 1:45)
1. Navigate to **8. Incident Management**:
   - Show newly generated incident `INC-2026-002` (Severity: `HIGH`).
   - Root cause attribution: `Null spike on transaction_amount exceeding 0.0% SLA`.
2. Navigate to **7. Lineage**:
   - Show OpenLineage provenance graph.
   - Point out affected downstream feature views and models before they serve inference traffic.

### Phase 4: Remediation & Safe Recovery (1:45 – 2:30)
1. In the Incident Center, click **Acknowledge** then **Resolve**.
2. Reset or heal dataset with clean baseline data:
   ```bash
   python scripts/reset_demo.py
   ```
3. Re-run pipeline to completion:
   - All 11 stages pass: Contract Validated $\to$ Schema Compatible $\to$ Quality Green $\to$ Features Materialized $\to$ Redis Online Updated.
4. Return to **9. ML Prediction**:
   - Re-run inference for `cust_000001`.
   - Show clean feature vector and verified classification.

---

## Recording Setup Best Practices

1. **Resolution:** 1080p (1920x1080) at 60 FPS or 30 FPS.
2. **Browser Window:** Maximize or set to 1536x864 for crisp text rendering. Set browser zoom to 100%.
3. **Tools:**
   - Windows: **OBS Studio** or **Xbox Game Bar** (`Win + Alt + R`).
   - macOS: **QuickTime** or **Screen Studio**.
4. **Mouse Pointer:** Enable subtle mouse click highlights if available.
5. **No Jargon Overload:** Focus on business impact—*"This circuit breaker prevented corrupted features from causing silent financial fraud misclassifications in production."*
