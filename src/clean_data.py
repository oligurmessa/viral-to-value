"""
clean_data.py
=============
Loads the raw star-schema CSVs, enforces types, validates referential integrity,
derives order-level contribution margin and writes the processed tables.

    python src/clean_data.py --raw data/raw --out data/processed
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

TABLES = ["campaigns", "customers", "sessions", "orders", "products"]


def load_raw(raw: Path) -> dict[str, pd.DataFrame]:
    d = {
        "campaigns": pd.read_csv(raw / "campaigns.csv", parse_dates=["campaign_date"]),
        "customers": pd.read_csv(raw / "customers.csv", parse_dates=["acquisition_date", "first_purchase_date"]),
        "sessions": pd.read_csv(raw / "sessions.csv", parse_dates=["timestamp"]),
        "orders": pd.read_csv(raw / "orders.csv", parse_dates=["order_date"]),
        "products": pd.read_csv(raw / "products.csv", parse_dates=["launch_date"]),
    }
    return d


def validate(d: dict[str, pd.DataFrame]) -> list[str]:
    """Return a list of human-readable data-quality issues (empty list == clean)."""
    issues = []
    for name, key in [("campaigns", "campaign_id"), ("customers", "customer_id"),
                      ("sessions", "session_id"), ("orders", "order_id"), ("products", "product_id")]:
        dup = d[name][key].duplicated().sum()
        if dup:
            issues.append(f"{name}: {dup} duplicate {key}")

    if not d["customers"].acquisition_campaign.isin(d["campaigns"].campaign_id).all():
        issues.append("customers: acquisition_campaign not in campaigns")
    if not d["orders"].customer_id.isin(d["customers"].customer_id).all():
        issues.append("orders: customer_id not in customers")
    if not d["orders"].product_id.isin(d["products"].product_id).all():
        issues.append("orders: product_id not in products")
    s = d["sessions"]
    if not s.loc[s.campaign_id.notna(), "campaign_id"].isin(d["campaigns"].campaign_id).all():
        issues.append("sessions: campaign_id not in campaigns")
    if not s.loc[s.customer_id.notna(), "customer_id"].isin(d["customers"].customer_id).all():
        issues.append("sessions: customer_id not in customers")

    o = d["orders"]
    if (o.net_revenue - (o.gross_revenue - o.discount_amount)).abs().max() > 0.011:
        issues.append("orders: net_revenue != gross - discount")
    if (o.refund_amount > o.net_revenue + 0.01).any():
        issues.append("orders: refund_amount exceeds net_revenue")
    if (o[["quantity", "gross_revenue", "cogs", "shipping_cost", "payment_fee"]] < 0).any().any():
        issues.append("orders: negative quantities/costs")

    first = o[o.is_first_order == 1].groupby("customer_id").size()
    if (first != 1).any() or len(first) != len(d["customers"]):
        issues.append("orders: customers without exactly one first order")

    m = o.merge(d["customers"][["customer_id", "first_purchase_date"]], on="customer_id")
    if (m.order_date < m.first_purchase_date).any():
        issues.append("orders: order before first_purchase_date")
    return issues


def process(d: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out = {k: v.copy() for k, v in d.items()}
    o = out["orders"]
    o["contribution_margin"] = (o.net_revenue - o.cogs - o.shipping_cost - o.payment_fee - o.refund_amount).round(2)
    o["is_refunded"] = (o.refund_amount > 0).astype(int)
    o["late_delivery"] = (o.delivery_days > 7).astype(int)
    o = o.merge(out["products"][["product_id", "category"]], on="product_id", how="left")
    out["orders"] = o

    c = out["campaigns"]
    c["share_rate"] = c.shares / c.reach
    c["save_rate"] = c.saves / c.reach
    c["engagement_rate"] = (c.likes + c.comments + c.shares + c.saves) / c.reach
    out["campaigns"] = c

    s = out["sessions"]
    s["session_date"] = s.timestamp.dt.normalize()
    out["sessions"] = s
    return out


def main(raw: Path, out: Path):
    d = load_raw(raw)
    issues = validate(d)
    if issues:
        print("DATA QUALITY ISSUES:")
        for i in issues:
            print("  -", i)
    else:
        print("data quality checks passed")
    p = process(d)
    out.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        p[name].to_csv(out / f"{name}.csv", index=False)
        print(f"wrote {name:<10} {len(p[name]):>9,} rows")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/processed")
    a = ap.parse_args()
    main(Path(a.raw), Path(a.out))
