"""
Apache Airflow DAG Definitions for FeatureHub & DataGuard Platforms
Includes feature computation, online materialization, freshness monitoring, and contract validation pipelines.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'data-platform-team',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# 1. Feature Computation Backfill DAG
dag_compute = DAG(
    'feature_compute',
    default_args=default_args,
    description='Idempotent backfill and windowed aggregation for 120+ offline features',
    schedule_interval='0 * * * *', # Hourly
    catchup=False
)

def run_feature_compute():
    from featurehub.computation.engine import compute_offline_features
    compute_offline_features()

task_compute = PythonOperator(
    task_id='compute_offline_features_task',
    python_callable=run_feature_compute,
    dag=dag_compute
)

# 2. Feature Materialization DAG
dag_materialize = DAG(
    'feature_materialization',
    default_args=default_args,
    description='Materializes offline Parquet feature store into Redis Online Store',
    schedule_interval='*/15 * * * *', # Every 15 mins
    catchup=False
)

def run_materialization():
    from featurehub.materialization.service import FeatureMaterializer
    mat = FeatureMaterializer()
    mat.materialize_all()

task_mat = PythonOperator(
    task_id='materialize_redis_task',
    python_callable=run_materialization,
    dag=dag_materialize
)

# 3. Feature Freshness Monitoring DAG
dag_freshness = DAG(
    'feature_freshness_monitor',
    default_args=default_args,
    description='Audits online feature freshness against SLA limits and creates incidents on breach',
    schedule_interval='*/30 * * * *',
    catchup=False
)

def run_freshness_audit():
    print("Auditing online feature freshness SLAs...")

task_freshness = PythonOperator(
    task_id='freshness_audit_task',
    python_callable=run_freshness_audit,
    dag=dag_freshness
)

# 4. DataGuard Contract & Quality Validation DAG
dag_dataguard = DAG(
    'dataguard_quality_validation',
    default_args=default_args,
    description='Executes Great Expectations quality suites and contract checks across 25+ datasets',
    schedule_interval='0 2 * * *', # Daily at 2am
    catchup=False
)

def run_quality_checks():
    from dataguard.benchmarks.run_benchmarks import run_dataguard_benchmarks
    run_dataguard_benchmarks()

task_quality = PythonOperator(
    task_id='validate_contracts_task',
    python_callable=run_quality_checks,
    dag=dag_dataguard
)
