"""
generate_data.py
================
Simulates a Gen-Z DTC streetwear brand's Instagram-driven business as a star schema:

    campaigns  -> sessions -> customers -> orders -> products

DESIGN PRINCIPLE (non-biased simulation)
----------------------------------------
Virality (a heavy-tailed random "virality shock") influences ONLY:
    reach, impressions, engagement counts, follower gain, traffic volume,
    number of acquired customers, short-term revenue volume.

Long-term customer quality (repeat purchasing, margin, returns) depends on
factors that are INDEPENDENT of the virality shock:
    - discount dependency (discount used at first order)
    - hidden content intent (entertainment / product / community)
    - creator tier (trust)
    - first-order experience (late delivery, return)
    - product category and first-order value
    - customer demographics
    - large individual random variation

Because content intent and discounts are correlated with *becoming* viral
(entertainment content gets shared more, discount codes spread), viral and
non-viral cohorts can differ in composition -- but nothing in this generator
says "viral => bad customer". Some viral campaigns produce excellent customers,
some produce poor ones. The analysis has to discover why.

Usage
-----
    python src/generate_data.py --out data/raw --seed 42
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# Global simulation parameters
# --------------------------------------------------------------------------------------
FIRST_CAMPAIGN = pd.Timestamp("2025-01-06")
LAST_CAMPAIGN = pd.Timestamp("2025-09-22")
OBS_END = pd.Timestamp("2026-01-31")  # observation window end: every customer has a full 90-day window
N_CAMPAIGNS = 120

CATEGORIES = {
    #  name           n_products  price_lo price_hi cogs_ratio return_rate
    "Hoodies":        (8,  58, 98,  0.38, 0.09),
    "T-shirts":       (8,  28, 46,  0.30, 0.06),
    "Accessories":    (8,  12, 42,  0.22, 0.04),
    "Sneakers":       (5, 115, 185, 0.52, 0.17),
    "Gymwear":        (6,  36, 72,  0.34, 0.08),
    "Limited Drops":  (5,  85, 165, 0.42, 0.10),
}
CAT_NAMES = list(CATEGORIES)

# Effect of first-order category on repeat propensity (independent of virality)
CAT_AFFINITY = {"Hoodies": 0.20, "T-shirts": 0.00, "Accessories": -0.25,
                "Sneakers": -0.10, "Gymwear": 0.30, "Limited Drops": 0.10}

CAMPAIGN_TYPES = ["Influencer", "Product Drop", "UGC", "Discount", "Organic", "Paid Amplification"]
CAMPAIGN_TYPE_P = [0.30, 0.14, 0.12, 0.16, 0.13, 0.15]

CONTENT_TYPES = ["Reel", "Carousel", "Story", "Static Post", "Live"]
CONTENT_TYPE_P = [0.55, 0.16, 0.15, 0.09, 0.05]

CREATOR_TIERS = ["Nano", "Micro", "Mid", "Macro", "Mega"]
CREATOR_TIER_P = [0.18, 0.34, 0.26, 0.15, 0.07]
TIER_BASE_REACH = {"Nano": 22_000, "Micro": 95_000, "Mid": 330_000,
                   "Macro": 1_050_000, "Mega": 3_200_000, "Brand": 140_000}
TIER_FEE = {"Nano": 450, "Micro": 2_400, "Mid": 8_500, "Macro": 28_000, "Mega": 85_000, "Brand": 0}
# creator trust effect on repeat propensity (smaller creators = more trusted recommendation)
TIER_AFFINITY = {"Nano": 0.35, "Micro": 0.30, "Mid": 0.10, "Macro": -0.10, "Mega": -0.20, "Brand": 0.05}

# hidden content intent probabilities by campaign type: [entertainment, product, community]
INTENT_P = {
    "Influencer":         [0.45, 0.35, 0.20],
    "Product Drop":       [0.10, 0.70, 0.20],
    "UGC":                [0.20, 0.30, 0.50],
    "Discount":           [0.35, 0.50, 0.15],
    "Organic":            [0.50, 0.20, 0.30],
    "Paid Amplification": [0.40, 0.45, 0.15],
}
INTENT_NAMES = ["entertainment", "product", "community"]
INTENT_SHARE_MULT = {"entertainment": 2.2, "product": 0.8, "community": 1.3}
INTENT_SAVE_MULT = {"entertainment": 0.6, "product": 2.2, "community": 1.2}
INTENT_CTR_MULT = {"entertainment": 0.60, "product": 1.35, "community": 1.05}
INTENT_CONV_MULT = {"entertainment": 0.70, "product": 1.40, "community": 1.10}
INTENT_AFFINITY = {"entertainment": 0.00, "product": 0.85, "community": 0.45}

CONTENT_CTR_MULT = {"Reel": 0.9, "Carousel": 1.15, "Story": 1.35, "Static Post": 0.8, "Live": 1.0}

AGE_GROUPS = ["18-20", "21-24", "25-27", "28+"]
AGE_P = [0.30, 0.38, 0.20, 0.12]
AGE_AFFINITY = {"18-20": -0.05, "21-24": 0.10, "25-27": 0.15, "28+": 0.05}
REGIONS = ["US-West", "US-East", "US-South", "US-Midwest", "UK", "EU", "CA", "AU"]
REGION_P = [0.20, 0.22, 0.16, 0.10, 0.12, 0.10, 0.06, 0.04]
DEVICES = ["mobile", "desktop", "tablet"]
DEVICE_P = [0.87, 0.10, 0.03]

REPEAT_TRAFFIC = ["direct", "organic_search", "email", "instagram_organic", "paid_social", "sms"]
REPEAT_TRAFFIC_P = [0.30, 0.18, 0.20, 0.17, 0.08, 0.07]


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


# --------------------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------------------
def make_products(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    pid = 1
    for cat, (n, lo, hi, cogs_ratio, ret) in CATEGORIES.items():
        for _ in range(n):
            price = float(np.round(rng.uniform(lo, hi) - 0.01, 2))
            cogs = float(np.round(price * cogs_ratio * rng.uniform(0.9, 1.1), 2))
            if cat == "Limited Drops":
                launch = FIRST_CAMPAIGN + pd.Timedelta(days=int(rng.integers(0, 250)))
            else:
                launch = pd.Timestamp("2024-06-01") + pd.Timedelta(days=int(rng.integers(0, 400)))
            rows.append({"product_id": f"P{pid:03d}", "product_name": f"{cat[:-1] if cat.endswith('s') else cat} #{pid}",
                         "category": cat, "price": price, "cogs": cogs,
                         "launch_date": launch.normalize(), "return_rate_base": ret})
            pid += 1
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Campaigns
# --------------------------------------------------------------------------------------
def make_campaigns(rng: np.random.Generator) -> pd.DataFrame:
    n = N_CAMPAIGNS
    span_days = (LAST_CAMPAIGN - FIRST_CAMPAIGN).days
    dates = FIRST_CAMPAIGN + pd.to_timedelta(np.sort(rng.integers(0, span_days + 1, n)), unit="D")

    ctype = rng.choice(CAMPAIGN_TYPES, n, p=CAMPAIGN_TYPE_P)
    content = rng.choice(CONTENT_TYPES, n, p=CONTENT_TYPE_P)

    tier = np.where(np.isin(ctype, ["Influencer", "UGC"]),
                    rng.choice(CREATOR_TIERS, n, p=CREATOR_TIER_P), "Brand")
    # UGC is mostly small creators
    tier = np.where((ctype == "UGC") & np.isin(tier, ["Macro", "Mega"]), "Micro", tier)

    intent = np.array([rng.choice(INTENT_NAMES, p=INTENT_P[c]) for c in ctype])

    # discount % offered by the campaign
    discount = np.zeros(n)
    for i, c in enumerate(ctype):
        if c == "Discount":
            discount[i] = rng.choice([20, 25, 30], p=[0.45, 0.35, 0.20])
        elif c == "Influencer":
            discount[i] = rng.choice([0, 10, 15], p=[0.40, 0.35, 0.25])
        elif c == "UGC":
            discount[i] = rng.choice([0, 10], p=[0.65, 0.35])
        elif c == "Paid Amplification":
            discount[i] = rng.choice([0, 10, 15], p=[0.45, 0.35, 0.20])
        else:  # Product Drop, Organic
            discount[i] = 0

    featured = np.empty(n, dtype=object)
    for i, c in enumerate(ctype):
        if c == "Product Drop":
            featured[i] = rng.choice(["Limited Drops", "Sneakers"], p=[0.65, 0.35])
        else:
            featured[i] = rng.choice(CAT_NAMES, p=[0.26, 0.22, 0.12, 0.12, 0.18, 0.10])

    # --- spend ---------------------------------------------------------------------
    production = rng.uniform(1_200, 5_000, n)
    creator_fee = np.array([TIER_FEE[t] * rng.uniform(0.8, 1.25) for t in tier])
    paid_media = np.where(ctype == "Paid Amplification", rng.uniform(9_000, 48_000, n),
                 np.where(ctype == "Discount", rng.uniform(2_500, 12_000, n),
                 np.where(ctype == "Product Drop", rng.uniform(2_000, 9_000, n), 0.0)))
    spend = np.round(production + creator_fee + paid_media, 2)

    # --- reach: base * INDEPENDENT virality shock ----------------------------------
    virality_shock = np.exp(rng.normal(0.0, 0.85, n))          # heavy-tailed, mean-ish ~1.4
    base_reach = np.array([TIER_BASE_REACH[t] for t in tier], dtype=float)
    base_reach = base_reach + paid_media * 22.0                  # ~ $45 CPM on paid media
    base_reach *= np.where(content == "Reel", 1.35, np.where(content == "Story", 0.55, 1.0))
    reach = (base_reach * virality_shock * np.exp(rng.normal(0, 0.25, n))).astype(int)
    impressions = (reach * rng.uniform(1.15, 1.65, n)).astype(int)

    # --- engagement -------------------------------------------------------------------
    like_rate = rng.uniform(0.03, 0.09, n)
    comment_rate = rng.uniform(0.0015, 0.008, n)
    share_rate = 0.004 * np.array([INTENT_SHARE_MULT[i] for i in intent]) \
        * virality_shock ** 0.45 * np.exp(rng.normal(0, 0.35, n))
    share_rate *= np.where(discount >= 20, 1.35, 1.0)            # discount codes get forwarded
    save_rate = 0.006 * np.array([INTENT_SAVE_MULT[i] for i in intent]) * np.exp(rng.normal(0, 0.35, n))
    likes = (reach * like_rate).astype(int)
    comments = (reach * comment_rate).astype(int)
    shares = (reach * share_rate).astype(int)
    saves = (reach * save_rate).astype(int)
    follower_gain = (reach * 0.0035 * virality_shock ** 0.3
                     * np.array([{"entertainment": 0.9, "product": 1.0, "community": 1.3}[i] for i in intent])
                     * np.exp(rng.normal(0, 0.3, n))).astype(int)

    campaigns = pd.DataFrame({
        "campaign_id": [f"IG_{i+1:03d}" for i in range(n)],
        "campaign_date": dates,
        "campaign_name": [f"{c} {ct} {d.strftime('%b-%d')}" for c, ct, d in zip(ctype, content, dates)],
        "content_type": content,
        "campaign_type": ctype,
        "creator_tier": tier,
        "featured_category": featured,
        "spend": spend,
        "discount_pct": discount.astype(int),
        "reach": reach,
        "impressions": impressions,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": saves,
        "follower_gain": follower_gain,
    })
    latent = pd.DataFrame({"campaign_id": campaigns.campaign_id,
                           "content_intent": intent, "virality_shock": virality_shock})
    return campaigns, latent


# --------------------------------------------------------------------------------------
# Traffic, customers, orders
# --------------------------------------------------------------------------------------
def simulate_business(rng: np.random.Generator, campaigns: pd.DataFrame, latent: pd.DataFrame,
                      products: pd.DataFrame):
    prod_by_cat = {c: products[products.category == c] for c in CAT_NAMES}
    prod_price = products.set_index("product_id").price.to_dict()
    prod_cogs = products.set_index("product_id").cogs.to_dict()
    prod_cat = products.set_index("product_id").category.to_dict()
    prod_launch = products.set_index("product_id").launch_date.to_dict()
    prod_ret = products.set_index("product_id").return_rate_base.to_dict()

    sessions, customers, orders, cust_latent = [], [], [], []
    sess_counter = 0
    cust_counter = 0
    order_counter = 0

    def pick_product(cat: str, order_date: pd.Timestamp) -> str:
        avail = prod_by_cat[cat]
        avail = avail[avail.launch_date <= order_date]
        if avail.empty:
            avail = products[products.launch_date <= order_date]
        return str(rng.choice(avail.product_id.values))

    def build_order(customer_id, order_date, cat, discount_pct, is_first, affinity):
        nonlocal order_counter
        order_counter += 1
        pid = pick_product(cat, order_date)
        qty = int(rng.choice([1, 2, 3], p=[0.76, 0.19, 0.05]))
        gross = round(prod_price[pid] * qty, 2)
        disc_amt = round(gross * discount_pct / 100.0, 2)
        net = round(gross - disc_amt, 2)
        cogs = round(prod_cogs[pid] * qty, 2)
        shipping = round(4.9 + 1.4 * (qty - 1) + rng.uniform(0, 1.6), 2)
        fee = round(0.029 * net + 0.30, 2)
        delivery_days = int(np.clip(np.round(2 + rng.gamma(2.0, 1.4)), 1, 21))
        late = int(delivery_days > 7)
        p_ret = prod_ret[pid] * (1.5 if late else 1.0) * (1.15 if is_first else 0.85)
        refunded = rng.random() < p_ret
        refund_amt = round(net * (1.0 if rng.random() < 0.8 else 0.5), 2) if refunded else 0.0
        refund_days = int(rng.integers(3, 26)) if refunded else None
        return {
            "order_id": f"O{order_counter:07d}", "customer_id": customer_id,
            "order_date": order_date, "product_id": pid, "quantity": qty,
            "gross_revenue": gross, "discount_amount": disc_amt, "net_revenue": net,
            "cogs": cogs, "shipping_cost": shipping, "payment_fee": fee,
            "refund_amount": refund_amt, "refund_days": refund_days,
            "delivery_days": delivery_days, "is_first_order": int(is_first),
        }, late, refunded, net

    for camp, lat in zip(campaigns.itertuples(index=False), latent.itertuples(index=False)):
        intent = lat.content_intent
        shock = lat.virality_shock

        # ---- traffic: link CTR (audience dilution at extreme reach) ---------------
        ctr = 0.011 * INTENT_CTR_MULT[intent] * CONTENT_CTR_MULT[camp.content_type] \
            * (1 + camp.discount_pct / 70.0) * shock ** (-0.22) * np.exp(rng.normal(0, 0.2))
        n_visitors = int(rng.poisson(camp.reach * ctr))
        if n_visitors == 0:
            continue

        lag_days = np.minimum(rng.exponential(2.6, n_visitors), 21)
        ts = camp.campaign_date + pd.to_timedelta(lag_days * 24 * 3600 + rng.uniform(8 * 3600, 23 * 3600, n_visitors), unit="s")
        device = rng.choice(DEVICES, n_visitors, p=DEVICE_P)
        views = 1 + rng.poisson(2.2 * (1.3 if intent == "product" else 1.0), n_visitors)

        p_atc = np.clip(0.150 * INTENT_CONV_MULT[intent] * (1 + camp.discount_pct / 45.0)
                        * np.where(device == "mobile", 1.0, 1.15) * (1 + 0.05 * (views - 3)), 0.02, 0.6)
        atc = rng.random(n_visitors) < p_atc
        co = atc & (rng.random(n_visitors) < 0.46)
        buy = co & (rng.random(n_visitors) < 0.56)

        sess_ids = np.array([f"S{sess_counter + i + 1:08d}" for i in range(n_visitors)])
        sess_counter += n_visitors

        buyer_idx = np.where(buy)[0]
        cust_ids = np.array([f"C{cust_counter + i + 1:06d}" for i in range(len(buyer_idx))])
        cust_counter += len(buyer_idx)
        sess_cust = np.full(n_visitors, None, dtype=object)
        sess_cust[buyer_idx] = cust_ids

        sessions.append(pd.DataFrame({
            "session_id": sess_ids, "customer_id": sess_cust, "timestamp": ts,
            "campaign_id": camp.campaign_id, "traffic_source": "instagram_campaign",
            "device": device, "product_views": views,
            "add_to_cart": atc.astype(int), "checkout_started": co.astype(int), "purchase": buy.astype(int),
        }))

        # ---- customers & first orders ------------------------------------------------
        for j, i in enumerate(buyer_idx):
            cid = cust_ids[j]
            acq_ts = ts[i]
            acq_date = acq_ts.normalize()
            age = str(rng.choice(AGE_GROUPS, p=AGE_P))
            region = str(rng.choice(REGIONS, p=REGION_P))

            used_code = camp.discount_pct > 0 and rng.random() < 0.85
            disc = int(camp.discount_pct) if used_code else 0
            cat = camp.featured_category if rng.random() < 0.62 else str(rng.choice(CAT_NAMES, p=[0.26, 0.22, 0.12, 0.12, 0.18, 0.10]))

            noise = rng.normal(0, 0.85)
            o, late, refunded, net = build_order(cid, acq_date, cat, disc, True, 0.0)
            first_value = net

            # ---- customer quality: NO virality term -----------------------------------
            affinity = (-1.05
                        + INTENT_AFFINITY[intent]
                        + TIER_AFFINITY[camp.creator_tier]
                        - 0.045 * disc
                        + 0.0065 * (first_value - 60.0)
                        - 1.0 * refunded
                        - 0.45 * late
                        + CAT_AFFINITY[cat]
                        + AGE_AFFINITY[age]
                        + noise)
            p_rep90 = float(sigmoid(affinity))
            repeat90 = rng.random() < p_rep90
            discount_dep = 0.10 + 0.45 * disc / 30.0

            orders.append(o)
            customers.append({
                "customer_id": cid, "acquisition_date": acq_date, "acquisition_campaign": camp.campaign_id,
                "age_group": age, "region": region, "first_purchase_date": acq_date,
                "acquisition_device": device[i],
            })
            cust_latent.append({"customer_id": cid, "affinity": affinity, "p_repeat_90d": p_rep90,
                                "content_intent": intent})

            # ---- repeat orders ----------------------------------------------------------
            rep_dates = []
            if repeat90:
                gap = 90.0 * rng.beta(1.4, 2.2)
                n_more = 1 + rng.poisson(0.35 + 1.6 * p_rep90)
                t = acq_date + pd.Timedelta(days=float(max(gap, 2)))
                rep_dates.append(t)
                for _ in range(n_more - 1):
                    t = t + pd.Timedelta(days=float(rng.gamma(2.0, (34 - 14 * p_rep90) / 2.0) + 2))
                    rep_dates.append(t)
            elif rng.random() < 0.12:  # late (post-90d) re-activation
                rep_dates.append(acq_date + pd.Timedelta(days=float(91 + rng.exponential(55))))
            rep_dates = [d.normalize() for d in rep_dates if d <= OBS_END]

            for d in rep_dates:
                rcat = cat if rng.random() < 0.55 else str(rng.choice(CAT_NAMES))
                rdisc = int(rng.choice([10, 15, 20])) if rng.random() < discount_dep else 0
                ro, _, _, _ = build_order(cid, d, rcat, rdisc, False, affinity)
                orders.append(ro)
                sess_counter += 1
                sessions.append(pd.DataFrame([{
                    "session_id": f"S{sess_counter:08d}", "customer_id": cid,
                    "timestamp": d + pd.Timedelta(seconds=float(rng.uniform(8 * 3600, 23 * 3600))),
                    "campaign_id": None, "traffic_source": str(rng.choice(REPEAT_TRAFFIC, p=REPEAT_TRAFFIC_P)),
                    "device": device[i], "product_views": int(1 + rng.poisson(2.5)),
                    "add_to_cart": 1, "checkout_started": 1, "purchase": 1,
                }]))

            # ---- non-purchase browsing sessions (engagement signal) -----------------------
            n_browse = rng.poisson(0.3 + 1.8 * p_rep90)
            for _ in range(n_browse):
                sess_counter += 1
                bd = acq_date + pd.Timedelta(days=float(rng.exponential(18)) + 0.5)
                if bd > OBS_END:
                    continue
                sessions.append(pd.DataFrame([{
                    "session_id": f"S{sess_counter:08d}", "customer_id": cid,
                    "timestamp": bd + pd.Timedelta(seconds=float(rng.uniform(8 * 3600, 23 * 3600))),
                    "campaign_id": None, "traffic_source": str(rng.choice(REPEAT_TRAFFIC, p=REPEAT_TRAFFIC_P)),
                    "device": device[i], "product_views": int(1 + rng.poisson(1.8)),
                    "add_to_cart": int(rng.random() < 0.25), "checkout_started": int(rng.random() < 0.08), "purchase": 0,
                }]))

    sessions_df = pd.concat(sessions, ignore_index=True)
    sessions_df = sessions_df.sort_values("timestamp").reset_index(drop=True)
    customers_df = pd.DataFrame(customers)
    orders_df = pd.DataFrame(orders)
    latent_df = pd.DataFrame(cust_latent)
    return sessions_df, customers_df, orders_df, latent_df


# --------------------------------------------------------------------------------------
def main(out: Path, seed: int):
    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)
    sim_dir = out.parent / "simulation"
    sim_dir.mkdir(parents=True, exist_ok=True)

    products = make_products(rng)
    campaigns, camp_latent = make_campaigns(rng)
    sessions, customers, orders, cust_latent = simulate_business(rng, campaigns, camp_latent, products)

    products.drop(columns=["return_rate_base"]).to_csv(out / "products.csv", index=False)
    campaigns.to_csv(out / "campaigns.csv", index=False)
    customers.to_csv(out / "customers.csv", index=False)
    sessions.to_csv(out / "sessions.csv", index=False)
    orders.to_csv(out / "orders.csv", index=False)
    # hidden simulation variables: NOT used by the analysis, kept only to audit the generator
    camp_latent.to_csv(sim_dir / "campaign_latent_truth.csv", index=False)
    cust_latent.to_csv(sim_dir / "customer_latent_truth.csv", index=False)

    print(f"products  {len(products):>9,}")
    print(f"campaigns {len(campaigns):>9,}")
    print(f"customers {len(customers):>9,}")
    print(f"sessions  {len(sessions):>9,}")
    print(f"orders    {len(orders):>9,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    main(Path(a.out), a.seed)
