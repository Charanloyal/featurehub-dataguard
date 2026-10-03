# System Known Limitations & Trade-Offs

1. **Storage Scale**: Local development uses SQLite/PostgreSQL and local Parquet files. Production deployments would utilize AWS S3 / MinIO / BigQuery as the offline feature store.
2. **Distributed Compute**: Feature computations are executed via Pandas/Numpy window aggregations locally. Large-scale production workloads (>1B events) should run on PySpark / Spark on EMR or Dataproc.
3. **In-Memory Fallback**: When Redis container is offline, RedisOnlineStore falls back to an in-memory dictionary.
