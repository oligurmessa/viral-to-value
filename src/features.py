"""
features.py
===========
Feature engineering for the early-signal customer model.

Question answered by the model:
    Can we identify, within 7 days of acquisition, which Instagram-acquired
    customers are likely to become durable (repeat within 90 days)?

Only information observable by day 7 after acquisition is used:
    campaign attributes (known at acquisition), first-order attributes,
    refunds processed within 7 days, sessions/product views within 7 days.
Repeat orders placed within the first 7 days are a legitimate early signal
and are included as `orders_7d`; the target is repeat purchase within 90 days.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from metrics import add_virality, customer_value

CATEGORICAL = ["content_type", "campaign_type", "creator_tier", "first_order_category",
               "age_group", "region", "acquisition_device"]
NUMERIC = ["virality_score", "is_viral", "log_reach", "share_rate", "save_rate", "save_to_share_ratio",
           "campaign_discount_pct", "first_order_discount_pct", "used_discount",
           "first_order_value", "first_order_quantity", "first_order_refunded_7d", "first_order_late",
           "sessions_7d", "product_views_7d", "add_to_cart_7d", "orders_7d", "acq_lag_days"]
TARGET = "repeat_90d"
EARLY_WINDOW = 7


def build_customer_features(campaigns: pd.DataFrame, customers: pd.DataFrame,
                            sessions: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    c = add_virality(campaigns)
    cv = customer_value(customers, orders)

    first = orders[orders.is_first_order == 1].set_index("customer_id")
    df = customers.merge(cv.drop(columns=["acquisition_campaign", "acquisition_date"]), on="customer_id")
    df = df.merge(c[["campaign_id", "campaign_date", "content_type", "campaign_type", "creator_tier",
                     "discount_pct", "reach", "share_rate", "save_rate", "save_to_share_ratio",
                     "virality_score", "is_viral"]].rename(columns={"discount_pct": "campaign_discount_pct"}),
                  left_on="acquisition_campaign", right_on="campaign_id", how="left")
    df["log_reach"] = np.log(df.reach)
    df["acq_lag_days"] = (df.acquisition_date - df.campaign_date).dt.days
    df["used_discount"] = (df.first_order_discount > 0).astype(int)
    df["first_order_quantity"] = df.customer_id.map(first.quantity)
    # refund observable by day 7 only if processed within 7 days
    rd = first.refund_days
    df["first_order_refunded_7d"] = df.customer_id.map(((rd.notna()) & (rd <= EARLY_WINDOW)).astype(int))

    # early on-site engagement (sessions within 7 days, excluding the acquisition session)
    s = sessions[sessions.customer_id.notna()].merge(customers[["customer_id", "acquisition_date"]], on="customer_id")
    s["d"] = (s.timestamp.dt.normalize() - s.acquisition_date).dt.days
    early = s[(s.d >= 0) & (s.d <= EARLY_WINDOW) & (s.traffic_source != "instagram_campaign")]
    agg = early.groupby("customer_id").agg(sessions_7d=("session_id", "size"),
                                           product_views_7d=("product_views", "sum"),
                                           add_to_cart_7d=("add_to_cart", "sum"))
    df = df.merge(agg, left_on="customer_id", right_index=True, how="left")
    for col in ["sessions_7d", "product_views_7d", "add_to_cart_7d"]:
        df[col] = df[col].fillna(0).astype(int)
    df["orders_7d"] = df["orders_7d"] if "orders_7d" in df else 0
    o7 = orders.merge(customers[["customer_id", "acquisition_date"]], on="customer_id")
    o7 = o7[(o7.order_date - o7.acquisition_date).dt.days <= EARLY_WINDOW].groupby("customer_id").size() - 1
    df["orders_7d"] = df.customer_id.map(o7).fillna(0).astype(int)
    return df


def model_matrix(df: pd.DataFrame):
    """Return (X, y) with one-hot categoricals; column order is stable."""
    X = pd.get_dummies(df[NUMERIC + CATEGORICAL], columns=CATEGORICAL, drop_first=False, dtype=float)
    y = df[TARGET].astype(int)
    return X, y
