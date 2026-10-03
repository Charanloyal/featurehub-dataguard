-- Database Initialization Script for FeatureHub & DataGuard

-- Feature Registry Table
CREATE TABLE IF NOT EXISTS feature_registry (
    feature_name VARCHAR(128) PRIMARY KEY,
    feature_group VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    data_type VARCHAR(32) NOT NULL,
    description TEXT,
    source_table VARCHAR(128),
    version VARCHAR(16) DEFAULT 'v1',
    owner VARCHAR(64) DEFAULT 'data-platform-team',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    freshness_sla_minutes INTEGER DEFAULT 60,
    status VARCHAR(32) DEFAULT 'ACTIVE'
);

-- Feature Groups Table
CREATE TABLE IF NOT EXISTS feature_groups (
    group_name VARCHAR(64) PRIMARY KEY,
    entity_type VARCHAR(64) NOT NULL,
    description TEXT,
    owner VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Data Quality Incidents Table
CREATE TABLE IF NOT EXISTS quality_incidents (
    incident_id VARCHAR(64) PRIMARY KEY,
    dataset_name VARCHAR(128) NOT NULL,
    check_name VARCHAR(128) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    error_message TEXT,
    pipeline_name VARCHAR(128),
    owner VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Materialization Job Runs Log
CREATE TABLE IF NOT EXISTS materialization_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    feature_group VARCHAR(64) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    records_written INTEGER DEFAULT 0,
    status VARCHAR(32) NOT NULL,
    error_message TEXT
);

-- Data Quality Validation History
CREATE TABLE IF NOT EXISTS quality_validation_history (
    validation_id VARCHAR(64) PRIMARY KEY,
    dataset_name VARCHAR(128) NOT NULL,
    contract_version VARCHAR(16) NOT NULL,
    total_checks INTEGER NOT NULL,
    passed_checks INTEGER NOT NULL,
    failed_checks INTEGER NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    details JSONB
);

-- Core Entities Tables for Seed Data
CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(64) PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    kyc_status VARCHAR(32) NOT NULL,
    risk_tier VARCHAR(16) NOT NULL,
    country VARCHAR(8) NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(64) REFERENCES customers(customer_id),
    account_type VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    current_balance NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id VARCHAR(64) PRIMARY KEY,
    merchant_category VARCHAR(64) NOT NULL,
    risk_score NUMERIC(5, 4) NOT NULL,
    country VARCHAR(8) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(64) REFERENCES customers(customer_id),
    account_id VARCHAR(64) REFERENCES accounts(account_id),
    merchant_id VARCHAR(64) REFERENCES merchants(merchant_id),
    amount NUMERIC(12, 2) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(32) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    is_fraud INTEGER DEFAULT 0
);

-- DataGuard Persistent Contract Registry
CREATE TABLE IF NOT EXISTS contract_registry (
    dataset_name VARCHAR(128) PRIMARY KEY,
    latest_version VARCHAR(64) NOT NULL,
    owner VARCHAR(128) NOT NULL,
    description TEXT,
    freshness_sla_minutes INTEGER,
    status VARCHAR(32) DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contract_versions (
    id SERIAL PRIMARY KEY,
    dataset_name VARCHAR(128) NOT NULL REFERENCES contract_registry(dataset_name) ON DELETE CASCADE,
    version VARCHAR(64) NOT NULL,
    owner VARCHAR(128) NOT NULL,
    description TEXT,
    freshness_sla_minutes INTEGER,
    status VARCHAR(32) DEFAULT 'ACTIVE',
    schema_json TEXT NOT NULL,
    contract_payload TEXT,
    yaml_content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(128) DEFAULT 'data-platform',
    CONSTRAINT uq_dataset_version UNIQUE(dataset_name, version)
);

CREATE INDEX IF NOT EXISTS idx_contract_versions_dataset 
ON contract_versions(dataset_name);

-- E-Commerce & Core Business Entities
CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    category VARCHAR(64) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    stock_quantity INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL REFERENCES customers(customer_id),
    order_total NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(8) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    item_id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id VARCHAR(64) NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    payment_method VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    settled_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS fraud_events (
    event_id VARCHAR(64) PRIMARY KEY,
    transaction_id VARCHAR(64) NOT NULL REFERENCES transactions(transaction_id),
    customer_id VARCHAR(64) NOT NULL REFERENCES customers(customer_id),
    fraud_type VARCHAR(64) NOT NULL,
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- DataGuard Automated Quality Engine (Phase D)
CREATE TABLE IF NOT EXISTS quality_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    dataset_name VARCHAR(128) NOT NULL,
    contract_version VARCHAR(64) DEFAULT 'v1.0.0',
    pipeline_name VARCHAR(128) DEFAULT 'default_pipeline',
    overall_status VARCHAR(32) NOT NULL,
    total_checks INTEGER DEFAULT 0,
    passed_checks INTEGER DEFAULT 0,
    failed_checks INTEGER DEFAULT 0,
    warning_checks INTEGER DEFAULT 0,
    quality_score DOUBLE PRECISION DEFAULT 100.0,
    duration_ms DOUBLE PRECISION DEFAULT 0.0,
    freshness_status VARCHAR(32) DEFAULT 'FRESH',
    freshness_delay_minutes DOUBLE PRECISION,
    last_record_timestamp VARCHAR(64),
    row_count INTEGER DEFAULT 0,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_quality_runs_dataset ON quality_runs(dataset_name);
CREATE INDEX IF NOT EXISTS idx_quality_runs_executed_at ON quality_runs(executed_at);

CREATE TABLE IF NOT EXISTS quality_results (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES quality_runs(run_id) ON DELETE CASCADE,
    dataset_name VARCHAR(128) NOT NULL,
    check_name VARCHAR(256) NOT NULL,
    column_name VARCHAR(128),
    expectation_type VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    success BOOLEAN NOT NULL,
    observed_value TEXT,
    expected_value TEXT,
    duration_ms DOUBLE PRECISION DEFAULT 0.0,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    pipeline_name VARCHAR(128) DEFAULT 'default_pipeline',
    details_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_quality_results_run_id ON quality_results(run_id);
CREATE INDEX IF NOT EXISTS idx_quality_results_dataset ON quality_results(dataset_name);

-- DataGuard Incident Management Engine (Phase E)
CREATE TABLE IF NOT EXISTS incidents (
    incident_id VARCHAR(64) PRIMARY KEY,
    dataset VARCHAR(128) NOT NULL,
    pipeline VARCHAR(128) DEFAULT 'default_pipeline',
    check_name VARCHAR(256) NOT NULL,
    expectation_type VARCHAR(128) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    owner VARCHAR(128) NOT NULL,
    title VARCHAR(256) NOT NULL,
    description TEXT,
    error_message TEXT,
    observed_value TEXT,
    expected_value TEXT,
    failure_signature VARCHAR(128) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_incidents_dataset ON incidents(dataset);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);
CREATE INDEX IF NOT EXISTS idx_incidents_owner ON incidents(owner);
CREATE INDEX IF NOT EXISTS idx_incidents_sig_status ON incidents(failure_signature, status);

CREATE TABLE IF NOT EXISTS incident_events (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(64) NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    old_status VARCHAR(32),
    new_status VARCHAR(32) NOT NULL,
    actor VARCHAR(128) DEFAULT 'system',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_incident_events_incident_id ON incident_events(incident_id);

-- Incident reference enhancement for Data Lineage (Phase F)
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS run_id VARCHAR(64);
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS pipeline_id VARCHAR(128);
CREATE INDEX IF NOT EXISTS idx_incidents_run_id ON incidents(run_id);

-- OpenLineage Data Lineage Engine (Phase F)
CREATE TABLE IF NOT EXISTS lineage_datasets (
    dataset_id VARCHAR(256) PRIMARY KEY,
    namespace VARCHAR(128) NOT NULL,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    schema_facets TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_lineage_dataset_namespace_name UNIQUE(namespace, name)
);

CREATE INDEX IF NOT EXISTS idx_lineage_datasets_name ON lineage_datasets(name);
CREATE INDEX IF NOT EXISTS idx_lineage_datasets_namespace ON lineage_datasets(namespace);

CREATE TABLE IF NOT EXISTS lineage_jobs (
    job_id VARCHAR(256) PRIMARY KEY,
    namespace VARCHAR(128) NOT NULL,
    name VARCHAR(128) NOT NULL,
    pipeline_id VARCHAR(128) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_lineage_job_namespace_name UNIQUE(namespace, name)
);

CREATE INDEX IF NOT EXISTS idx_lineage_jobs_pipeline ON lineage_jobs(pipeline_id);

CREATE TABLE IF NOT EXISTS lineage_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    job_id VARCHAR(256) NOT NULL REFERENCES lineage_jobs(job_id) ON DELETE CASCADE,
    pipeline_id VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    inputs_json TEXT,
    outputs_json TEXT,
    facets_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lineage_runs_job_id ON lineage_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_lineage_runs_pipeline ON lineage_runs(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_lineage_runs_status ON lineage_runs(status);

CREATE TABLE IF NOT EXISTS lineage_edges (
    edge_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES lineage_runs(run_id) ON DELETE CASCADE,
    source_dataset VARCHAR(256) NOT NULL,
    target_dataset VARCHAR(256) NOT NULL,
    pipeline_id VARCHAR(128) NOT NULL,
    edge_type VARCHAR(32) DEFAULT 'DATA_FLOW',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lineage_edges_source ON lineage_edges(source_dataset);
CREATE INDEX IF NOT EXISTS idx_lineage_edges_target ON lineage_edges(target_dataset);
CREATE INDEX IF NOT EXISTS idx_lineage_edges_run_id ON lineage_edges(run_id);

CREATE TABLE IF NOT EXISTS lineage_columns (
    column_edge_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES lineage_runs(run_id) ON DELETE CASCADE,
    source_dataset VARCHAR(256) NOT NULL,
    source_column VARCHAR(128) NOT NULL,
    target_dataset VARCHAR(256) NOT NULL,
    target_column VARCHAR(128) NOT NULL,
    transformation TEXT NOT NULL,
    pipeline_id VARCHAR(128) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lineage_cols_source ON lineage_columns(source_dataset, source_column);
CREATE INDEX IF NOT EXISTS idx_lineage_cols_target ON lineage_columns(target_dataset, target_column);
CREATE INDEX IF NOT EXISTS idx_lineage_cols_run_id ON lineage_columns(run_id);

-- DataGuard Pipeline Orchestration Engine (Phase G)
CREATE TABLE IF NOT EXISTS pipeline_metadata (
    pipeline_id VARCHAR(128) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    owner VARCHAR(128) NOT NULL,
    dataset VARCHAR(128) NOT NULL,
    contract VARCHAR(128) NOT NULL,
    freshness_sla_minutes INTEGER DEFAULT 60,
    description TEXT,
    schedule VARCHAR(64),
    status VARCHAR(32) DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_run_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    last_failure_at TIMESTAMP WITH TIME ZONE,
    tags_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_metadata_dataset ON pipeline_metadata(dataset);
CREATE INDEX IF NOT EXISTS idx_pipeline_metadata_status ON pipeline_metadata(status);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    pipeline_id VARCHAR(128) NOT NULL REFERENCES pipeline_metadata(pipeline_id) ON DELETE CASCADE,
    dataset VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_ms DOUBLE PRECISION DEFAULT 0.0,
    quality_run_id VARCHAR(64),
    incident_id VARCHAR(64),
    lineage_run_id VARCHAR(64),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    metrics_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline ON pipeline_runs(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_dataset ON pipeline_runs(dataset);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_start_time ON pipeline_runs(start_time);

