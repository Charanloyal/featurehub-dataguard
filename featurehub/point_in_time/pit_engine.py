"""
Point-In-Time (PIT) Correct Feature Join Engine
Guarantees zero target leakage during training dataset generation by performing timestamp-aware joins.
"""

from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np
from pathlib import Path

class DataLeakageError(Exception):
    """Raised when future feature timestamps (timestamp > observation_time) leak into training data."""
    pass

class PointInTimeJoinEngine:
    """
    Assembles point-in-time correct training datasets.
    Matches observation events (entity_id, event_timestamp) to historical feature values
    that occurred strictly BEFORE or AT event_timestamp.
    """

    @staticmethod
    def get_historical_features(
        entity_df: pd.DataFrame,
        feature_df: pd.DataFrame,
        entity_id_col: str,
        timestamp_col: str = "timestamp",
        feature_timestamp_col: str = "feature_timestamp",
        ttl_seconds: int = 86400 * 30
    ) -> pd.DataFrame:
        """
        Executes a point-in-time correct merge (asof join) between entity observations and historical features.
        
        entity_df: Observation events with entity_id_col, timestamp_col, and target labels.
        feature_df: Offline feature store table with entity_id_col, feature_timestamp_col, and feature columns.
        ttl_seconds: Maximum allowed staleness of historical features.
        """
        if entity_df.empty or feature_df.empty:
            return pd.DataFrame()

        # Copy and coerce timestamps to pandas datetime (UTC)
        e_df = entity_df.copy()
        f_df = feature_df.copy()

        e_df['obs_dt'] = pd.to_datetime(e_df[timestamp_col], utc=True)
        f_df['feat_dt'] = pd.to_datetime(f_df[feature_timestamp_col], utc=True)

        # Sort both datasets chronologically required by merge_asof
        e_df = e_df.sort_values(by='obs_dt')
        f_df = f_df.sort_values(by='feat_dt')

        # Execute Point-in-Time merge_asof (backward direction ensures feature_timestamp <= observation_timestamp)
        joined_df = pd.merge_asof(
            e_df,
            f_df,
            by=entity_id_col,
            left_on='obs_dt',
            right_on='feat_dt',
            direction='backward'
        )

        # Strict Verification: Check for future data leakage
        leakage_mask = joined_df['feat_dt'] > joined_df['obs_dt']
        if leakage_mask.any():
            leaked_count = leakage_mask.sum()
            raise DataLeakageError(
                f"CRITICAL: Detected {leaked_count} records where feature_timestamp > observation_timestamp!"
            )

        # Check TTL constraint
        if ttl_seconds > 0:
            staleness = (joined_df['obs_dt'] - joined_df['feat_dt']).dt.total_seconds()
            too_old_mask = staleness > ttl_seconds
            # Null out features exceeding TTL
            feature_cols = [c for c in f_df.columns if c not in [entity_id_col, feature_timestamp_col, 'feat_dt']]
            joined_df.loc[too_old_mask, feature_cols] = np.nan

        # Clean up helper datetime columns
        joined_df.drop(columns=['obs_dt', 'feat_dt'], inplace=True, errors='ignore')
        return joined_df

    @staticmethod
    def get_naive_latest_features(
        entity_df: pd.DataFrame,
        feature_df: pd.DataFrame,
        entity_id_col: str
    ) -> pd.DataFrame:
        """
        INCORRECT / NAIVE lookup: Always joins the LATEST available feature vector regardless of observation timestamp.
        Used strictly for demonstration of training-serving skew and data leakage in the dashboard.
        """
        # Get absolute latest record for each entity in feature store
        latest_features = feature_df.sort_values(by='feature_timestamp').groupby(entity_id_col).last().reset_index()
        
        # Simple inner/left join without timestamp constraint
        return pd.merge(entity_df, latest_features, on=entity_id_col, how='left')
