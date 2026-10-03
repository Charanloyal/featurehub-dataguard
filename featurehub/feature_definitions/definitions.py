"""
FeatureHub Feature Definitions Registry Catalog
Defines 120+ distinct financial transaction & fraud detection features across 6 feature groups.
"""

from typing import Dict, Any, List
from pydantic import BaseModel

class FeatureDefinition(BaseModel):
    name: str
    feature_group: str
    entity: str
    data_type: str
    description: str
    source_table: str
    version: str = "v1"
    owner: str = "fraud-analytics-team"
    freshness_sla_minutes: int = 60
    status: str = "ACTIVE"

FEATURE_CATALOG: List[FeatureDefinition] = []

# Helper to register features cleanly
def _reg(name: str, group: str, entity: str, dtype: str, desc: str, sla: int = 60):
    source = "transactions" if "txn" in name or "cust" in name or "acc" in name else "merchants"
    FEATURE_CATALOG.append(FeatureDefinition(
        name=name,
        feature_group=group,
        entity=entity,
        data_type=dtype,
        description=desc,
        source_table=source,
        freshness_sla_minutes=sla
    ))

# ---------------------------------------------------------
# Group 1: customer_velocity (22 Features)
# ---------------------------------------------------------
_reg("cust_txn_count_1h", "customer_velocity", "customer", "INT64", "Total transactions by customer in past 1 hour", 15)
_reg("cust_txn_count_6h", "customer_velocity", "customer", "INT64", "Total transactions by customer in past 6 hours", 30)
_reg("cust_txn_count_12h", "customer_velocity", "customer", "INT64", "Total transactions by customer in past 12 hours", 60)
_reg("cust_txn_count_24h", "customer_velocity", "customer", "INT64", "Total transactions by customer in past 24 hours", 60)
_reg("cust_txn_count_3d", "customer_velocity", "customer", "INT64", "Total transactions by customer in past 3 days", 120)
_reg("cust_txn_count_7d", "customer_velocity", "customer", "INT64", "Total transactions by customer in past 7 days", 360)
_reg("cust_txn_count_14d", "customer_velocity", "customer", "INT64", "Total transactions by customer in past 14 days", 720)
_reg("cust_txn_count_30d", "customer_velocity", "customer", "INT64", "Total transactions by customer in past 30 days", 1440)

_reg("cust_txn_amount_sum_1h", "customer_velocity", "customer", "FLOAT64", "Total transaction volume (USD) in past 1 hour", 15)
_reg("cust_txn_amount_sum_6h", "customer_velocity", "customer", "FLOAT64", "Total transaction volume (USD) in past 6 hours", 30)
_reg("cust_txn_amount_sum_24h", "customer_velocity", "customer", "FLOAT64", "Total transaction volume (USD) in past 24 hours", 60)
_reg("cust_txn_amount_sum_7d", "customer_velocity", "customer", "FLOAT64", "Total transaction volume (USD) in past 7 days", 360)
_reg("cust_txn_amount_sum_30d", "customer_velocity", "customer", "FLOAT64", "Total transaction volume (USD) in past 30 days", 1440)

_reg("cust_txn_amount_avg_1h", "customer_velocity", "customer", "FLOAT64", "Average transaction amount in past 1 hour", 15)
_reg("cust_txn_amount_avg_24h", "customer_velocity", "customer", "FLOAT64", "Average transaction amount in past 24 hours", 60)
_reg("cust_txn_amount_avg_7d", "customer_velocity", "customer", "FLOAT64", "Average transaction amount in past 7 days", 360)
_reg("cust_txn_amount_avg_30d", "customer_velocity", "customer", "FLOAT64", "Average transaction amount in past 30 days", 1440)

_reg("cust_failed_txn_count_1h", "customer_velocity", "customer", "INT64", "Failed transaction attempts in past 1 hour", 15)
_reg("cust_failed_txn_count_24h", "customer_velocity", "customer", "INT64", "Failed transaction attempts in past 24 hours", 60)
_reg("cust_failed_txn_count_7d", "customer_velocity", "customer", "INT64", "Failed transaction attempts in past 7 days", 360)

_reg("cust_unique_merchants_24h", "customer_velocity", "customer", "INT64", "Distinct merchant count transacted with in past 24 hours", 60)
_reg("cust_unique_merchants_7d", "customer_velocity", "customer", "INT64", "Distinct merchant count transacted with in past 7 days", 360)

# ---------------------------------------------------------
# Group 2: account_balance_stats (20 Features)
# ---------------------------------------------------------
_reg("acc_balance_ratio_24h", "account_balance_stats", "account", "FLOAT64", "Ratio of 24h spend to current balance", 60)
_reg("acc_balance_ratio_7d", "account_balance_stats", "account", "FLOAT64", "Ratio of 7d spend to current balance", 360)
_reg("acc_age_days", "account_balance_stats", "account", "INT64", "Age of account in days", 1440)
_reg("acc_current_balance", "account_balance_stats", "account", "FLOAT64", "Current posted account balance in USD", 15)
_reg("acc_avg_daily_spend_7d", "account_balance_stats", "account", "FLOAT64", "Average daily spending over past 7 days", 360)
_reg("acc_avg_daily_spend_14d", "account_balance_stats", "account", "FLOAT64", "Average daily spending over past 14 days", 720)
_reg("acc_avg_daily_spend_30d", "account_balance_stats", "account", "FLOAT64", "Average daily spending over past 30 days", 1440)

_reg("acc_max_txn_amount_7d", "account_balance_stats", "account", "FLOAT64", "Maximum single transaction amount in past 7 days", 360)
_reg("acc_max_txn_amount_30d", "account_balance_stats", "account", "FLOAT64", "Maximum single transaction amount in past 30 days", 1440)
_reg("acc_min_txn_amount_30d", "account_balance_stats", "account", "FLOAT64", "Minimum single transaction amount in past 30 days", 1440)
_reg("acc_stddev_txn_amount_30d", "account_balance_stats", "account", "FLOAT64", "Standard deviation of transaction amounts over 30 days", 1440)

_reg("acc_balance_drain_rate_24h", "account_balance_stats", "account", "FLOAT64", "Percentage balance decrease over past 24 hours", 60)
_reg("acc_balance_drain_rate_7d", "account_balance_stats", "account", "FLOAT64", "Percentage balance decrease over past 7 days", 360)
_reg("acc_high_val_txn_count_24h", "account_balance_stats", "account", "INT64", "Count of transactions > $1,000 in past 24 hours", 60)
_reg("acc_high_val_txn_count_7d", "account_balance_stats", "account", "INT64", "Count of transactions > $1,000 in past 7 days", 360)
_reg("acc_high_val_txn_count_30d", "account_balance_stats", "account", "INT64", "Count of transactions > $1,000 in past 30 days", 1440)

_reg("acc_is_overdrawn_flag", "account_balance_stats", "account", "INT64", "Binary flag indicating negative account balance", 15)
_reg("acc_overdraft_count_30d", "account_balance_stats", "account", "INT64", "Total overdraft occurrences in past 30 days", 1440)
_reg("acc_credit_utilization_ratio", "account_balance_stats", "account", "FLOAT64", "Ratio of used credit to limit (for credit accounts)", 360)
_reg("acc_days_since_first_txn", "account_balance_stats", "account", "INT64", "Days elapsed since first recorded transaction", 1440)

# ---------------------------------------------------------
# Group 3: merchant_risk_profile (20 Features)
# ---------------------------------------------------------
_reg("merch_risk_score", "merchant_risk_profile", "merchant", "FLOAT64", "Static/dynamic merchant fraud risk rating [0,1]", 1440)
_reg("merch_txn_count_1h", "merchant_risk_profile", "merchant", "INT64", "Total transaction volume processed in past 1 hour", 15)
_reg("merch_txn_count_24h", "merchant_risk_profile", "merchant", "INT64", "Total transaction volume processed in past 24 hours", 60)
_reg("merch_txn_count_7d", "merchant_risk_profile", "merchant", "INT64", "Total transaction volume processed in past 7 days", 360)
_reg("merch_txn_count_30d", "merchant_risk_profile", "merchant", "INT64", "Total transaction volume processed in past 30 days", 1440)

_reg("merch_avg_txn_amount_24h", "merchant_risk_profile", "merchant", "FLOAT64", "Average transaction amount at merchant in past 24h", 60)
_reg("merch_avg_txn_amount_7d", "merchant_risk_profile", "merchant", "FLOAT64", "Average transaction amount at merchant in past 7d", 360)
_reg("merch_avg_txn_amount_30d", "merchant_risk_profile", "merchant", "FLOAT64", "Average transaction amount at merchant in past 30d", 1440)

_reg("merch_fraud_rate_7d", "merchant_risk_profile", "merchant", "FLOAT64", "Historical fraud rate percentage over past 7 days", 360)
_reg("merch_fraud_rate_30d", "merchant_risk_profile", "merchant", "FLOAT64", "Historical fraud rate percentage over past 30 days", 1440)
_reg("merch_declined_txn_rate_24h", "merchant_risk_profile", "merchant", "FLOAT64", "Percentage of authorization declines in past 24h", 60)
_reg("merch_declined_txn_rate_7d", "merchant_risk_profile", "merchant", "FLOAT64", "Percentage of authorization declines in past 7d", 360)

_reg("merch_unique_customers_24h", "merchant_risk_profile", "merchant", "INT64", "Count of distinct customers transacting in past 24h", 60)
_reg("merch_unique_customers_7d", "merchant_risk_profile", "merchant", "INT64", "Count of distinct customers transacting in past 7d", 360)
_reg("merch_unique_customers_30d", "merchant_risk_profile", "merchant", "INT64", "Count of distinct customers transacting in past 30d", 1440)

_reg("merch_high_risk_cat_flag", "merchant_risk_profile", "merchant", "INT64", "Flag for high risk category (crypto, gambling)", 1440)
_reg("merch_cross_border_ratio_7d", "merchant_risk_profile", "merchant", "FLOAT64", "Ratio of international customer transactions (7d)", 360)
_reg("merch_max_txn_amount_30d", "merchant_risk_profile", "merchant", "FLOAT64", "Largest transaction processed at merchant in 30d", 1440)
_reg("merch_velocity_spike_index", "merchant_risk_profile", "merchant", "FLOAT64", "Ratio of 1h volume vs 24h hourly average", 15)
_reg("merch_refund_ratio_30d", "merchant_risk_profile", "merchant", "FLOAT64", "Refund to transaction amount ratio over 30 days", 1440)

# ---------------------------------------------------------
# Group 4: transaction_window_stats (20 Features)
# ---------------------------------------------------------
_reg("txn_amount_to_cust_avg_ratio_7d", "transaction_window_stats", "transaction", "FLOAT64", "Current amount relative to customer 7d average", 15)
_reg("txn_amount_to_cust_avg_ratio_30d", "transaction_window_stats", "transaction", "FLOAT64", "Current amount relative to customer 30d average", 15)
_reg("txn_amount_to_merch_avg_ratio_7d", "transaction_window_stats", "transaction", "FLOAT64", "Current amount relative to merchant 7d average", 15)
_reg("txn_amount_to_merch_avg_ratio_30d", "transaction_window_stats", "transaction", "FLOAT64", "Current amount relative to merchant 30d average", 15)

_reg("txn_time_since_last_txn_sec", "transaction_window_stats", "transaction", "FLOAT64", "Elapsed seconds since customer's previous transaction", 15)
_reg("txn_is_night_time_flag", "transaction_window_stats", "transaction", "INT64", "Binary flag indicating transaction between 00:00-05:00 local time", 15)
_reg("txn_is_weekend_flag", "transaction_window_stats", "transaction", "INT64", "Binary flag indicating Saturday or Sunday transaction", 15)
_reg("txn_hour_of_day", "transaction_window_stats", "transaction", "INT64", "Hour of day (0-23) when transaction occurred", 15)
_reg("txn_day_of_week", "transaction_window_stats", "transaction", "INT64", "Day of week (0-6, Monday=0) when transaction occurred", 15)

_reg("txn_channel_is_mobile", "transaction_window_stats", "transaction", "INT64", "Flag if transaction channel is MOBILE_APP", 15)
_reg("txn_channel_is_web", "transaction_window_stats", "transaction", "INT64", "Flag if transaction channel is WEB", 15)
_reg("txn_channel_is_pos", "transaction_window_stats", "transaction", "INT64", "Flag if transaction channel is POS", 15)
_reg("txn_channel_is_atm", "transaction_window_stats", "transaction", "INT64", "Flag if transaction channel is ATM", 15)
_reg("txn_channel_is_wire", "transaction_window_stats", "transaction", "INT64", "Flag if transaction channel is WIRE", 15)

_reg("txn_amount_zscore_30d", "transaction_window_stats", "transaction", "FLOAT64", "Z-score of current transaction amount vs 30d distribution", 15)
_reg("txn_consecutive_high_val_count", "transaction_window_stats", "transaction", "INT64", "Number of consecutive high value txns in 1 hour", 15)
_reg("txn_is_first_time_merchant", "transaction_window_stats", "transaction", "INT64", "Flag if customer has never transacted at merchant before", 15)
_reg("txn_is_first_time_country", "transaction_window_stats", "transaction", "INT64", "Flag if customer has never transacted in country before", 15)
_reg("txn_velocity_spike_ratio_1h_vs_24h", "transaction_window_stats", "transaction", "FLOAT64", "1-hour transaction rate vs 24-hour average rate", 15)
_reg("txn_is_round_amount_flag", "transaction_window_stats", "transaction", "INT64", "Flag for exact round dollar amount ($100, $500, $1000)", 15)

# ---------------------------------------------------------
# Group 5: temporal_behavioral (20 Features)
# ---------------------------------------------------------
_reg("cust_activity_score", "temporal_behavioral", "customer", "FLOAT64", "Normalized customer engagement score over past 30d", 1440)
_reg("cust_night_owl_ratio_30d", "temporal_behavioral", "customer", "FLOAT64", "Ratio of transactions occurring late night (00-05h)", 1440)
_reg("cust_weekend_spend_ratio_30d", "temporal_behavioral", "customer", "FLOAT64", "Ratio of spending occurring on weekends", 1440)
_reg("cust_preferred_channel_ratio_30d", "temporal_behavioral", "customer", "FLOAT64", "Dominant channel usage percentage over 30d", 1440)

_reg("cust_new_merchants_count_7d", "temporal_behavioral", "customer", "INT64", "Count of newly visited merchants in past 7 days", 360)
_reg("cust_new_merchants_count_30d", "temporal_behavioral", "customer", "INT64", "Count of newly visited merchants in past 30 days", 1440)
_reg("cust_cross_border_count_7d", "temporal_behavioral", "customer", "INT64", "International transactions in past 7 days", 360)
_reg("cust_cross_border_count_30d", "temporal_behavioral", "customer", "INT64", "International transactions in past 30 days", 1440)

_reg("cust_avg_days_between_txns_30d", "temporal_behavioral", "customer", "FLOAT64", "Average delay in days between customer transactions", 1440)
_reg("cust_stddev_days_between_txns_30d", "temporal_behavioral", "customer", "FLOAT64", "Standard deviation of inter-transaction time", 1440)

_reg("cust_preferred_category_entropy_30d", "temporal_behavioral", "customer", "FLOAT64", "Shannon entropy of merchant categories visited", 1440)
_reg("cust_mobile_usage_ratio_30d", "temporal_behavioral", "customer", "FLOAT64", "Ratio of mobile channel transactions over 30 days", 1440)
_reg("cust_pos_usage_ratio_30d", "temporal_behavioral", "customer", "FLOAT64", "Ratio of physical POS transactions over 30 days", 1440)
_reg("cust_wire_usage_ratio_30d", "temporal_behavioral", "customer", "FLOAT64", "Ratio of wire transfer transactions over 30 days", 1440)

_reg("cust_declined_ratio_7d", "temporal_behavioral", "customer", "FLOAT64", "Ratio of declined attempts to total attempts (7d)", 360)
_reg("cust_declined_ratio_30d", "temporal_behavioral", "customer", "FLOAT64", "Ratio of declined attempts to total attempts (30d)", 1440)
_reg("cust_max_daily_txn_count_30d", "temporal_behavioral", "customer", "INT64", "Highest transaction count on any single day in 30d", 1440)
_reg("cust_max_daily_spend_30d", "temporal_behavioral", "customer", "FLOAT64", "Highest single-day expenditure total in 30d", 1440)
_reg("cust_dormancy_days_before_latest_txn", "temporal_behavioral", "customer", "INT64", "Days of inactivity prior to the current transaction", 1440)
_reg("cust_rapid_repeat_txn_count_24h", "temporal_behavioral", "customer", "INT64", "Transactions occurring within 2 minutes of prior txn", 60)

# ---------------------------------------------------------
# Group 6: velocity_and_risk_scores (20 Features)
# ---------------------------------------------------------
_reg("txn_velocity_score", "velocity_and_risk_scores", "transaction", "FLOAT64", "Composite normalized velocity risk index [0,1]", 15)
_reg("cust_risk_velocity_composite", "velocity_and_risk_scores", "customer", "FLOAT64", "Weighted combination of customer risk & velocity", 15)
_reg("acc_rapid_depletion_score", "velocity_and_risk_scores", "account", "FLOAT64", "Score quantifying rapid balance drain speed", 60)
_reg("merch_category_risk_index", "velocity_and_risk_scores", "merchant", "FLOAT64", "Category baseline risk coefficient", 1440)

_reg("geo_distance_from_home_km", "velocity_and_risk_scores", "transaction", "FLOAT64", "Estimated distance of transaction from home country", 15)
_reg("geo_velocity_kph", "velocity_and_risk_scores", "transaction", "FLOAT64", "Physical speed (km/h) required between last 2 txns", 15)
_reg("consecutive_failed_auth_count", "velocity_and_risk_scores", "customer", "INT64", "Count of consecutive authorization failures", 15)
_reg("unusual_hour_spending_index", "velocity_and_risk_scores", "customer", "FLOAT64", "Deviation from customer's typical active hours", 360)

_reg("amount_dispersion_index_30d", "velocity_and_risk_scores", "customer", "FLOAT64", "Coefficient of variation of transaction amounts", 1440)
_reg("high_risk_merchant_spend_ratio_7d", "velocity_and_risk_scores", "customer", "FLOAT64", "Fraction of spend at high risk merchants (7d)", 360)
_reg("high_risk_merchant_spend_ratio_30d", "velocity_and_risk_scores", "customer", "FLOAT64", "Fraction of spend at high risk merchants (30d)", 1440)

_reg("card_testing_pattern_flag", "velocity_and_risk_scores", "customer", "INT64", "Flag for sequential low-value micro transactions", 15)
_reg("structuring_pattern_flag", "velocity_and_risk_scores", "customer", "INT64", "Flag for multiple txns just below reporting threshold", 60)
_reg("atm_cash_drain_score_24h", "velocity_and_risk_scores", "account", "FLOAT64", "Intensity score of consecutive ATM cash withdrawals", 60)

_reg("burst_txn_count_10min", "velocity_and_risk_scores", "customer", "INT64", "Count of transactions in rapid 10-minute window", 15)
_reg("burst_txn_amount_10min", "velocity_and_risk_scores", "customer", "FLOAT64", "Total dollar amount transacted in 10-minute window", 15)
_reg("account_takeover_risk_index", "velocity_and_risk_scores", "account", "FLOAT64", "Composite anomaly score for potential account takeover", 60)
_reg("merchant_collusion_risk_score", "velocity_and_risk_scores", "merchant", "FLOAT64", "Clustering risk indicator between merchant & customer", 1440)
_reg("device_fingerprint_anomaly_score", "velocity_and_risk_scores", "customer", "FLOAT64", "Anomaly score for device/IP channel switching", 60)
_reg("network_risk_centrality_score", "velocity_and_risk_scores", "customer", "FLOAT64", "Graph network risk score based on shared merchants", 1440)

def get_all_features() -> List[FeatureDefinition]:
    return FEATURE_CATALOG

def get_features_by_group(group_name: str) -> List[FeatureDefinition]:
    return [f for f in FEATURE_CATALOG if f.feature_group == group_name]

def get_features_by_entity(entity_name: str) -> List[FeatureDefinition]:
    return [f for f in FEATURE_CATALOG if f.entity == entity_name]

if __name__ == "__main__":
    print(f"Total REAL Features Registered in Catalog: {len(FEATURE_CATALOG)}")
    groups = set(f.feature_group for f in FEATURE_CATALOG)
    print(f"Feature Groups ({len(groups)}):")
    for g in sorted(groups):
        count = len(get_features_by_group(g))
        print(f"  - {g}: {count} features")
