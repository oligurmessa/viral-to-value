# Power BI — Viral to Value dashboard

> The `.pbix` file has to be authored in **Power BI Desktop (Windows)**; this repository was built on macOS, so
> it ships everything needed to build the report in a few minutes — the star-schema extracts, the model
> definition, the DAX measures and the page layout — plus a static preview rendered from the same numbers
> (`images/dashboard_preview.png`). Once you build the file, save it as `powerbi/viral_to_value.pbix`.

## 1. Data sources (Power Query)

Run `python src/export_powerbi.py` to produce `powerbi/data/`:

| table | grain | source |
|---|---|---|
| `dim_campaign.csv` | campaign | campaigns + virality flags + scorecard (`campaign_metrics.csv`) |
| `dim_customer.csv` | customer | customers + 30/60/90-day value (`customer_value.csv`) |
| `dim_product.csv` | product | products |
| `dim_date.csv` | day | calendar 2025-01-01 → 2026-01-31 |
| `fact_orders.csv` | order | orders with contribution margin |
| `fact_sessions_daily.csv` | campaign × day | sessions aggregated by campaign and date (keeps the model small) |

Import all six with Power Query (`Get Data → Text/CSV`), set the date columns to Date, and mark `dim_date`
as the date table.

## 2. Model (relationships)

```
dim_date[date]            1 ──* fact_orders[order_date]
dim_date[date]            1 ──* fact_sessions_daily[session_date]
dim_date[date]            1 ──* dim_customer[acquisition_date]      (inactive; use USERELATIONSHIP)
dim_customer[customer_id] 1 ──* fact_orders[customer_id]
dim_campaign[campaign_id] 1 ──* dim_customer[acquisition_campaign]
dim_campaign[campaign_id] 1 ──* fact_sessions_daily[campaign_id]
dim_product[product_id]   1 ──* fact_orders[product_id]
```

Single-direction filters everywhere except `dim_campaign → dim_customer → fact_orders`, which is the path that
lets a campaign slicer filter orders. All measures are in `measures.dax`; paste them into a `_Measures` table.

## 3. Pages

### Page 1 — Executive overview
- KPI cards (row): **Marketing Spend · Net Revenue · Contribution Margin · Customers Acquired · CAC · 90-Day
  CM-LTV · LTV:CAC · 90-Day Repeat Rate**
- Slicer: `dim_campaign[virality_tier]` (Viral / High reach, low sharing / Standard) and `campaign_type`
- Clustered bar: CAC, CM-LTV and LTV:CAC by `virality_tier`
- Line: daily net revenue (`fact_orders`) with campaign dates as a reference layer

### Page 2 — Campaign performance
- **Scatter**: x = `virality_score`, y = `[CM-LTV 90d]`, size = `[Customers Acquired]`, legend = `is_viral`,
  tooltip = campaign name, type, creator tier, discount, CAC, ROAS 7d. This is the project's headline visual.
- Table: campaign scorecard (reach, share rate, save rate, spend, customers, CAC, ROAS 7d, repeat 90d,
  CM-LTV 90d, LTV:CAC, profit 90d, payback days) with conditional colour on LTV:CAC (< 1 red, ≥ 3 green)
- Bar: share of spend vs share of 90-day CM by campaign type

### Page 3 — Customer durability
- Matrix heatmap: acquisition month × months since acquisition → `[Retention %]`
- Clustered column: 30 / 60 / 90-day repeat rate, viral vs non-viral
- Histogram (binned column): days to second order
- Line: cumulative CM per customer by days since acquisition, viral vs non-viral

### Page 4 — Financial performance
- Cards: CAC · ROAS 7d · Contribution Margin · CM-LTV 90d · LTV:CAC · Payback (median days) · Refund Rate ·
  Discount Rate
- Waterfall: gross revenue → discounts → COGS → shipping → fees → refunds → contribution margin
- Bar: LTV:CAC by campaign, sorted, colour by `is_viral`, reference lines at 1× and 3×
- Scatter: discount rate vs CM-LTV 90d (size = customers)

## 4. Formatting conventions

- Viral = orange `#EB6834`, non-viral = blue `#2A78D6`, "high reach, low sharing" = aqua `#1BAF7A`;
  keep these fixed across pages.
- Currency in USD with no decimals on cards, one decimal on ratios.
- Every page carries the footnote: *Simulated DTC dataset — see docs/methodology.md.*
