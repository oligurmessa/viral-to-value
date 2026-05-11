# Methodology

## 1. Why a simulated dataset

No public dataset combines Instagram campaign-level engagement (reach, shares, saves, creator tier, discount
offered) with customer-level transactions, costs and refunds for the same business. Public options were
considered and rejected:

| dataset | what it has | what it lacks |
|---|---|---|
| UCI Online Retail II (1.07M rows) | real transactions, customer IDs, cancellations | no acquisition source, no campaigns, no costs |
| Google Merchandise Store / GA4 sample | traffic source, sessions, transactions | no Instagram campaign attributes, no margin, short window |

Forcing either into the question would mean inventing the missing half anyway. Instead the project uses a
**simulated DTC business with a fully specified schema** (`src/generate_data.py`), which makes every assumption
explicit and auditable.

> Results describe the simulated business and are not empirical claims about Instagram users generally.
> What transfers is the *method*: how to define virality, how to measure durable value, and how to separate
> composition from causation.

## 2. Simulation design principle: no baked-in answer

The single most important design constraint is that the generator must **not** encode "viral ⇒ bad customer".

**Virality** is a heavy-tailed random shock (`virality_shock ~ LogNormal(0, 0.85)`) drawn independently of
everything that determines customer quality. It multiplies reach, and (with exponent 0.45) the share rate, and
therefore drives traffic volume, number of customers acquired and short-term revenue. It also mildly *reduces*
click-through per unit reach (`shock^-0.22`, "audience dilution"), which affects acquisition efficiency but
not what happens after purchase.

**Customer quality** (`affinity`, the log-odds of repeating within 90 days) depends only on:

| factor | effect on log-odds | observable? |
|---|---|---|
| hidden content intent (entertainment / product / community) | 0 / +0.85 / +0.45 | no — but it drives save rate (product) and share rate (entertainment), so proxies exist |
| creator tier (Nano … Mega, Brand) | +0.35 … −0.20 | yes |
| discount used at first order | −0.045 per point (30 % ⇒ −1.35) | yes |
| first-order net value | +0.0065 per $ above $60 | yes |
| first order refunded | −1.0 | yes |
| late delivery (> 7 days) | −0.45 | yes |
| first-order category | −0.25 … +0.30 | yes |
| age group | −0.05 … +0.15 | yes |
| individual noise | N(0, 0.85) | no |

There is **no virality term** in that equation. Viral and non-viral cohorts differ only because the *mix* of
intent, discount and creator tier differs among campaigns that happen to go viral (entertainment content and
discount codes get shared more). Whether that composition effect is large, small or absent is left for the
analysis to find — and the notebooks show it is present but modest, and that it disappears once observable
factors are controlled.

## 3. Definitions

| metric | definition |
|---|---|
| share rate, save rate | shares / reach, saves / reach |
| engagement rate | (likes + comments + shares + saves) / reach |
| **viral** | reach ≥ 90th percentile **and** share rate ≥ 75th percentile (across the 120 campaigns) |
| virality score | z(log reach) + z(log share rate) — continuous alternative |
| virality tier | Viral · High reach, low sharing (reach ≥ p90 only) · Standard |
| contribution margin (order) | net revenue − COGS − shipping − payment fee − refund |
| 30/60/90-day repeat | second order placed within N days of acquisition |
| 90-day CM-LTV | contribution margin from orders in the first 90 days after acquisition |
| CAC | campaign spend / customers acquired by that campaign |
| 7-day ROAS | net revenue from the campaign's cohort in the 7 days after the campaign date / spend |
| LTV:CAC | mean 90-day CM-LTV of the cohort / CAC |
| 90-day campaign profit | 90-day CM-LTV × customers − spend |
| payback | first day on which cumulative CM per customer ≥ CAC (≤ 180 days) |

Attribution is **last-touch to the acquiring campaign**: a customer belongs to the campaign whose session
converted them, and all their later orders accrue to that cohort regardless of the later traffic source.

## 4. Analysis stages

| notebook | question | technique |
|---|---|---|
| 01 data quality | is the data trustworthy? | key / FK / accounting-identity checks, observation-window check |
| 02 exploratory | what does the business look like? | mix, spend vs reach, engagement, margin waterfall, funnel |
| 03 campaign | which campaigns went viral, and what happened in week 1? | virality definition, event-time revenue, 7-day ROAS, CAC |
| 04 cohorts | do acquired customers come back? | 30/60/90 repeat, repeat curves, monthly cohort heatmap, cumulative CM |
| 05 profitability | are they worth it? | CAC, CM-LTV, LTV:CAC, profit, payback, budget scenario |
| 06 statistics | is the difference real and what explains it? | Mann–Whitney, Cliff's δ, bootstrap CIs, χ², Spearman, weighted OLS, logistic with controls |
| 07 model | can durable customers be spotted by day 7? | logistic vs RF vs GBM, time-based split, permutation importance, decile lift |

The SQL scripts in `sql/` reproduce the acquisition funnel, retention, customer LTV and campaign scorecard in
PostgreSQL syntax (run locally on DuckDB via `src/run_sql.py`).

## 5. Statistical choices

- 90-day CM-LTV is right-skewed with a point mass of single-order customers, so the primary two-sample test is
  Mann–Whitney U with **Cliff's δ** as effect size; **bootstrap CIs** are reported for the difference in means
  because the mean is what enters LTV:CAC.
- Proportions (repeat, refund) use a two-proportion z-test with a Wald CI; χ² and Cramér's V for the
  repeat × virality table.
- Campaign-level analysis is restricted to cohorts with ≥ 30 customers (100 of 120) and the regression is weighted
  by cohort size.
- With n ≈ 41k customers almost any difference is "significant"; conclusions are drawn from effect sizes.
- The customer model uses a **time-based split** (acquired before / after 15 July 2025) so that evaluation
  mimics scoring future cohorts, and only features observable by day 7.

## 6. Reproducing

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/generate_data.py            # data/raw  (seed 42)
python src/clean_data.py               # data/processed
python src/run_sql.py --export         # SQL outputs
jupyter nbconvert --execute --to notebook --inplace notebooks/0*.ipynb
python src/build_report.py             # images/dashboard_preview.png, reports/executive_summary.pdf
```
