# Data dictionary

Star schema: two fact tables (`orders`, `sessions`) and three dimensions (`campaigns`, `customers`, `products`).
Raw tables live in `data/raw/`; `src/clean_data.py` writes typed, validated copies with derived columns to `data/processed/`.

```
campaigns ──< customers ──< orders >── products
    │              │
    └──────< sessions >────┘
```

## campaigns (dimension) — one row per Instagram campaign

| column | type | description |
|---|---|---|
| campaign_id | text, PK | `IG_001` … `IG_120` |
| campaign_date | date | day the content was published |
| campaign_name | text | human-readable label |
| content_type | text | Reel · Carousel · Story · Static Post · Live |
| campaign_type | text | Influencer · Product Drop · UGC · Discount · Organic · Paid Amplification |
| creator_tier | text | Nano · Micro · Mid · Macro · Mega · Brand (in-house content) |
| featured_category | text | product category the content pushes |
| spend | numeric | total cost: production + creator fee + paid media (USD) |
| discount_pct | int | discount code offered by the campaign (0 = none) |
| reach | int | unique accounts reached |
| impressions | int | total views |
| likes, comments, shares, saves | int | engagement counts |
| follower_gain | int | net new followers attributed to the campaign |
| *share_rate* | numeric | derived: shares / reach |
| *save_rate* | numeric | derived: saves / reach |
| *engagement_rate* | numeric | derived: (likes + comments + shares + saves) / reach |
| *is_viral* | 0/1 | derived (`metrics.add_virality`): reach ≥ p90 **and** share_rate ≥ p75 |
| *virality_score* | numeric | derived: z(log reach) + z(log share_rate) |
| *virality_tier* | text | derived: Viral · High reach, low sharing · Standard |

## customers (dimension) — one row per acquired customer

| column | type | description |
|---|---|---|
| customer_id | text, PK | `C000001` … |
| acquisition_date | date | date of the converting campaign session |
| acquisition_campaign | text, FK → campaigns | campaign that brought the customer |
| age_group | text | 18-20 · 21-24 · 25-27 · 28+ |
| region | text | US-West · US-East · US-South · US-Midwest · UK · EU · CA · AU |
| first_purchase_date | date | date of first order (= acquisition date in this dataset) |
| acquisition_device | text | mobile · desktop · tablet |

## sessions (fact) — one row per site visit

| column | type | description |
|---|---|---|
| session_id | text, PK | |
| customer_id | text, FK, nullable | null for anonymous visitors who never bought |
| timestamp | timestamp | session start |
| campaign_id | text, FK, nullable | set only for `instagram_campaign` traffic |
| traffic_source | text | instagram_campaign · direct · organic_search · email · instagram_organic · paid_social · sms |
| device | text | mobile · desktop · tablet |
| product_views | int | product pages viewed |
| add_to_cart | 0/1 | added at least one item |
| checkout_started | 0/1 | |
| purchase | 0/1 | session ended in an order |

## orders (fact) — one row per order line (single product per order)

| column | type | description |
|---|---|---|
| order_id | text, PK | |
| customer_id | text, FK → customers | |
| order_date | date | |
| product_id | text, FK → products | |
| quantity | int | |
| gross_revenue | numeric | price × quantity |
| discount_amount | numeric | promo-code discount applied |
| net_revenue | numeric | gross − discount |
| cogs | numeric | cost of goods sold |
| shipping_cost | numeric | fulfilment cost borne by the brand |
| payment_fee | numeric | 2.9 % of net + $0.30 |
| refund_amount | numeric | amount refunded (0 if none); full or partial |
| refund_days | int, nullable | days after order the refund was processed |
| delivery_days | int | days from order to delivery |
| is_first_order | 0/1 | the customer's acquisition order |
| *contribution_margin* | numeric | derived: net − COGS − shipping − fee − refund |
| *is_refunded*, *late_delivery* | 0/1 | derived flags (late = delivery_days > 7) |
| *category* | text | derived: joined from products |

## products (dimension)

| column | type | description |
|---|---|---|
| product_id | text, PK | |
| product_name | text | |
| category | text | Hoodies · T-shirts · Accessories · Sneakers · Gymwear · Limited Drops |
| price | numeric | list price |
| cogs | numeric | unit cost |
| launch_date | date | products cannot be ordered before launch |

## Derived analytical tables (`data/processed/`)

| file | grain | produced by |
|---|---|---|
| `campaigns_virality.csv` | campaign | notebook 03 — engagement rates, viral flag, virality score |
| `campaign_short_term.csv` | campaign | notebook 03 — 7-day revenue, ROAS, CAC |
| `customer_value.csv` | customer | notebook 04 — 30/60/90-day repeat, revenue, CM-LTV, days to 2nd order |
| `campaign_metrics.csv` | campaign | notebook 05 — full scorecard incl. LTV:CAC, profit, payback |
| `customer_features.csv` | customer | notebook 07 — day-7 features and target |
| `stats_*.csv`, `model_*.csv` | — | notebooks 06/07 — test results, coefficients, model metrics |
| `sql_*.csv` | — | `src/run_sql.py --export` — outputs of the SQL scripts |

## Simulation-only files (`data/simulation/`)

`campaign_latent_truth.csv` and `customer_latent_truth.csv` hold the generator's hidden variables (content intent,
virality shock, individual affinity). **They are never read by the analysis.** They exist so the generator can be
audited against `docs/methodology.md`.
