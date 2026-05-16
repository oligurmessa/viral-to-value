"""
export_powerbi.py - writes the Power BI import tables to powerbi/data/.
Run after the notebooks (needs data/processed/campaign_metrics.csv and customer_value.csv).
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P, OUT = ROOT / "data/processed", ROOT / "powerbi/data"
OUT.mkdir(parents=True, exist_ok=True)

cm = pd.read_csv(P / "campaign_metrics.csv", parse_dates=["campaign_date"])
cv = pd.read_csv(P / "customer_value.csv", parse_dates=["acquisition_date"])
cu = pd.read_csv(P / "customers.csv", parse_dates=["acquisition_date", "first_purchase_date"])
o = pd.read_csv(P / "orders.csv", parse_dates=["order_date"])
s = pd.read_csv(P / "sessions.csv", parse_dates=["timestamp"])
pr = pd.read_csv(P / "products.csv", parse_dates=["launch_date"])

dim_campaign = cm[["campaign_id", "campaign_date", "campaign_name", "campaign_type", "content_type", "creator_tier", "featured_category",
                   "spend", "discount_pct", "reach", "impressions", "likes", "comments", "shares", "saves", "follower_gain",
                   "share_rate", "save_rate", "engagement_rate", "save_to_share_ratio", "is_viral", "virality_score", "virality_tier",
                   "new_customers", "cac", "roas_7d", "revenue_7d", "repeat_90d", "cm_90d_per_customer", "ltv_cac", "campaign_profit_90d", "payback_days"]]
dim_customer = cu.merge(cv[["customer_id", "first_order_value", "first_order_discount_pct", "first_order_refunded", "days_to_second_order",
                            "repeat_30d", "repeat_60d", "repeat_90d", "net_revenue_90d", "cm_90d", "orders_90d", "cm_total"]], on="customer_id")
dim_customer["acquisition_month"] = dim_customer.acquisition_date.dt.to_period("M").astype(str)
fact_orders = o[["order_id", "customer_id", "order_date", "product_id", "quantity", "gross_revenue", "discount_amount", "net_revenue",
                 "cogs", "shipping_cost", "payment_fee", "refund_amount", "contribution_margin", "is_first_order", "is_refunded", "late_delivery"]]
sc = s[s.traffic_source == "instagram_campaign"].copy()
sc["session_date"] = sc.timestamp.dt.normalize()
fact_sessions_daily = sc.groupby(["campaign_id", "session_date"]).agg(sessions=("session_id", "size"), product_views=("product_views", "sum"),
                                                                     add_to_cart=("add_to_cart", "sum"), checkout_started=("checkout_started", "sum"),
                                                                     purchases=("purchase", "sum")).reset_index()
dates = pd.date_range("2025-01-01", "2026-01-31", freq="D")
dim_date = pd.DataFrame({"date": dates, "year": dates.year, "month": dates.month, "month_name": dates.strftime("%b"),
                         "year_month": dates.strftime("%Y-%m"), "week": dates.isocalendar().week.values, "weekday": dates.strftime("%a")})

for name, df in {"dim_campaign": dim_campaign, "dim_customer": dim_customer, "dim_product": pr, "dim_date": dim_date,
                 "fact_orders": fact_orders, "fact_sessions_daily": fact_sessions_daily}.items():
    df.to_csv(OUT / f"{name}.csv", index=False)
    print(f"{name:<20} {len(df):>8,} rows")
