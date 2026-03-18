"""
metrics.py
==========
Business metrics used throughout the project.

Definitions
-----------
Contribution margin (order)  = net_revenue - COGS - shipping - payment fee - refunds
90-day CM-LTV (customer)     = sum of contribution margin of orders placed within 90 days of acquisition
CAC (campaign)               = campaign spend / new customers acquired
ROAS (7-day)                 = net revenue from the cohort in the first 7 days after the campaign / spend
LTV:CAC (campaign)           = mean 90-day CM-LTV of the cohort / CAC
Viral campaign               = reach >= 90th percentile AND share_rate >= 75th percentile
Virality score               = z(log reach) + z(log share_rate)   (continuous alternative)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WINDOWS = (30, 60, 90)
CM_COLS = ["net_revenue", "cogs", "shipping_cost", "payment_fee", "refund_amount"]


# --------------------------------------------------------------------------------------
# Virality
# --------------------------------------------------------------------------------------
def add_virality(campaigns: pd.DataFrame, reach_q: float = 0.90, share_q: float = 0.75) -> pd.DataFrame:
    c = campaigns.copy()
    if "share_rate" not in c:
        c["share_rate"] = c.shares / c.reach
    if "save_rate" not in c:
        c["save_rate"] = c.saves / c.reach
    if "engagement_rate" not in c:
        c["engagement_rate"] = (c.likes + c.comments + c.shares + c.saves) / c.reach
    c["save_to_share_ratio"] = c.saves / c.shares.clip(lower=1)

    reach_thr = c.reach.quantile(reach_q)
    share_thr = c.share_rate.quantile(share_q)
    c["is_viral"] = ((c.reach >= reach_thr) & (c.share_rate >= share_thr)).astype(int)

    def z(x):
        return (x - x.mean()) / x.std(ddof=0)
    c["virality_score"] = z(np.log(c.reach)) + z(np.log(c.share_rate))
    c["virality_tier"] = np.where(c.is_viral == 1, "Viral",
                          np.where(c.reach >= reach_thr, "High reach, low sharing", "Standard"))
    return c


# --------------------------------------------------------------------------------------
# Customer-level metrics
# --------------------------------------------------------------------------------------
def customer_value(customers: pd.DataFrame, orders: pd.DataFrame, windows=WINDOWS) -> pd.DataFrame:
    """One row per customer with repeat flags, revenue and CM at each horizon."""
    o = orders.merge(customers[["customer_id", "acquisition_date"]], on="customer_id", how="inner")
    if "contribution_margin" not in o:
        o["contribution_margin"] = o.net_revenue - o.cogs - o.shipping_cost - o.payment_fee - o.refund_amount
    o["days_since_acq"] = (o.order_date - o.acquisition_date).dt.days

    first = o[o.is_first_order == 1].set_index("customer_id")
    out = customers[["customer_id", "acquisition_campaign", "acquisition_date"]].copy().set_index("customer_id")
    out["first_order_value"] = first.net_revenue
    out["first_order_gross"] = first.gross_revenue
    out["first_order_discount"] = first.discount_amount
    out["first_order_discount_pct"] = (first.discount_amount / first.gross_revenue * 100).round(0)
    out["first_order_category"] = first.category if "category" in first else None
    out["first_order_refunded"] = (first.refund_amount > 0).astype(int)
    out["first_order_late"] = (first.delivery_days > 7).astype(int)
    out["first_order_cm"] = first.contribution_margin

    repeats = o[o.is_first_order == 0]
    second = repeats.groupby("customer_id").days_since_acq.min()
    out["days_to_second_order"] = second
    for w in windows:
        win = o[o.days_since_acq <= w]
        rep = repeats[repeats.days_since_acq <= w].groupby("customer_id").size()
        out[f"repeat_{w}d"] = out.index.isin(rep.index).astype(int)
        out[f"orders_{w}d"] = win.groupby("customer_id").size().reindex(out.index).fillna(0).astype(int)
        out[f"net_revenue_{w}d"] = win.groupby("customer_id").net_revenue.sum().reindex(out.index).fillna(0)
        out[f"cm_{w}d"] = win.groupby("customer_id").contribution_margin.sum().reindex(out.index).fillna(0)
        out[f"refunds_{w}d"] = win.groupby("customer_id").refund_amount.sum().reindex(out.index).fillna(0)
    out["orders_total"] = o.groupby("customer_id").size().reindex(out.index).fillna(0).astype(int)
    out["cm_total"] = o.groupby("customer_id").contribution_margin.sum().reindex(out.index).fillna(0)
    return out.reset_index()


# --------------------------------------------------------------------------------------
# Campaign-level metrics
# --------------------------------------------------------------------------------------
def campaign_metrics(campaigns: pd.DataFrame, customers: pd.DataFrame, orders: pd.DataFrame,
                     cust_value: pd.DataFrame | None = None) -> pd.DataFrame:
    c = add_virality(campaigns) if "is_viral" not in campaigns else campaigns.copy()
    cv = customer_value(customers, orders) if cust_value is None else cust_value

    o = orders.merge(customers[["customer_id", "acquisition_campaign"]], on="customer_id")
    o = o.merge(c[["campaign_id", "campaign_date"]], left_on="acquisition_campaign", right_on="campaign_id")
    if "contribution_margin" not in o:
        o["contribution_margin"] = o.net_revenue - o.cogs - o.shipping_cost - o.payment_fee - o.refund_amount
    o["days_since_campaign"] = (o.order_date - o.campaign_date).dt.days
    wk = o[o.days_since_campaign <= 7].groupby("acquisition_campaign").agg(
        revenue_7d=("net_revenue", "sum"), cm_7d=("contribution_margin", "sum"), orders_7d=("order_id", "size"))
    tot = o.groupby("acquisition_campaign").agg(
        revenue_total=("net_revenue", "sum"), cm_total=("contribution_margin", "sum"),
        refunds_total=("refund_amount", "sum"), gross_total=("gross_revenue", "sum"),
        discount_total=("discount_amount", "sum"))

    g = cv.groupby("acquisition_campaign").agg(
        new_customers=("customer_id", "size"),
        avg_first_order=("first_order_value", "mean"),
        first_order_refund_rate=("first_order_refunded", "mean"),
        first_order_discount_pct=("first_order_discount_pct", "mean"),
        repeat_30d=("repeat_30d", "mean"), repeat_60d=("repeat_60d", "mean"), repeat_90d=("repeat_90d", "mean"),
        revenue_90d_per_customer=("net_revenue_90d", "mean"),
        cm_90d_per_customer=("cm_90d", "mean"),
        cm_90d_median=("cm_90d", "median"),
        median_days_to_second=("days_to_second_order", "median"),
    )
    m = c.merge(g, left_on="campaign_id", right_index=True, how="left") \
         .merge(wk, left_on="campaign_id", right_index=True, how="left") \
         .merge(tot, left_on="campaign_id", right_index=True, how="left")
    m["new_customers"] = m.new_customers.fillna(0).astype(int)
    m["cac"] = m.spend / m.new_customers.replace(0, np.nan)
    m["roas_7d"] = m.revenue_7d / m.spend
    m["ltv_cac"] = m.cm_90d_per_customer / m.cac
    m["cm_90d_total"] = m.cm_90d_per_customer * m.new_customers
    m["campaign_profit_90d"] = m.cm_90d_total - m.spend
    m["refund_rate"] = m.refunds_total / m.gross_total
    m["discount_rate"] = m.discount_total / m.gross_total
    m["cost_per_reach_1k"] = m.spend / m.reach * 1000
    m["conversion_per_1k_reach"] = m.new_customers / m.reach * 1000
    return m


def payback_days(customers: pd.DataFrame, orders: pd.DataFrame, campaign_metrics_df: pd.DataFrame,
                 horizon: int = 180) -> pd.Series:
    """Days until cumulative CM per customer >= CAC, per campaign (NaN if never within horizon)."""
    o = orders.merge(customers[["customer_id", "acquisition_campaign", "acquisition_date"]], on="customer_id")
    if "contribution_margin" not in o:
        o["contribution_margin"] = o.net_revenue - o.cogs - o.shipping_cost - o.payment_fee - o.refund_amount
    o["d"] = (o.order_date - o.acquisition_date).dt.days
    cac = campaign_metrics_df.set_index("campaign_id").cac
    n = campaign_metrics_df.set_index("campaign_id").new_customers
    res = {}
    for cid, grp in o.groupby("acquisition_campaign"):
        if cid not in cac or n[cid] == 0 or np.isnan(cac[cid]):
            continue
        daily = grp.groupby("d").contribution_margin.sum().reindex(range(0, horizon + 1), fill_value=0).cumsum() / n[cid]
        hit = daily[daily >= cac[cid]]
        res[cid] = hit.index[0] if len(hit) else np.nan
    return pd.Series(res, name="payback_days")


# --------------------------------------------------------------------------------------
# Cohort retention matrix
# --------------------------------------------------------------------------------------
def cohort_matrix(customers: pd.DataFrame, orders: pd.DataFrame, freq: str = "M", periods: int = 6) -> pd.DataFrame:
    """Share of each acquisition-month cohort that placed an order in month k after acquisition."""
    o = orders.merge(customers[["customer_id", "acquisition_date"]], on="customer_id")
    o["cohort"] = o.acquisition_date.dt.to_period(freq)
    o["period"] = o.order_date.dt.to_period(freq)
    o["k"] = (o.period - o.cohort).apply(lambda x: x.n)
    size = customers.assign(cohort=customers.acquisition_date.dt.to_period(freq)).groupby("cohort").size()
    active = o[o.k <= periods].groupby(["cohort", "k"]).customer_id.nunique().unstack(fill_value=0)
    return active.div(size, axis=0)


def bootstrap_mean_diff(a: np.ndarray, b: np.ndarray, n_boot: int = 5000, seed: int = 0):
    """Bootstrap CI for mean(a) - mean(b)."""
    rng = np.random.default_rng(seed)
    a = np.asarray(a); b = np.asarray(b)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        diffs[i] = rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean()
    return diffs.mean(), np.percentile(diffs, [2.5, 97.5])


def cliffs_delta(a, b) -> float:
    """Non-parametric effect size in [-1, 1]: P(a > b) - P(a < b)."""
    a = np.asarray(a); b = np.asarray(b)
    # rank-based O(n log n) computation
    from scipy.stats import mannwhitneyu
    u = mannwhitneyu(a, b, alternative="two-sided").statistic
    return 2 * u / (len(a) * len(b)) - 1
