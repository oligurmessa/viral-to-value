# Assumptions and limitations

Everything below is a modelling choice in `src/generate_data.py` or in the analysis. Change the generator
parameters and the dollar values change; the analytical method does not.

## Business setting

- Fictional Gen-Z DTC streetwear brand selling only through its own website, USD, one country-agnostic
  price list.
- 120 Instagram campaigns from 6 Jan to 22 Sep 2025 (≈ 3 per week). Orders are observed through
  31 Jan 2026, so every customer has ≥ 90 days of history.
- Six campaign types (Influencer 30 %, Discount 16 %, Paid Amplification 15 %, Product Drop 14 %,
  Organic 13 %, UGC 12 %) and five content types (Reels 55 %).

## Costs and spend

- Campaign spend = content production ($1.2k–5k) + creator fee by tier (Nano $450 … Mega $85k, ±20 %) +
  paid media (Paid Amplification $9k–48k, Discount $2.5k–12k, Product Drop $2k–9k). Organic campaigns still
  carry production cost, so CAC is never zero.
- Discounts are treated as a **revenue reduction** (in `discount_amount`), not as marketing spend, so CAC
  understates the true cost of discount campaigns and CM-LTV carries it instead.
- COGS ratio by category: Accessories 22 %, T-shirts 30 %, Gymwear 34 %, Hoodies 38 %, Limited Drops 42 %,
  Sneakers 52 % (±10 %). Shipping $4.90 + $1.40 per extra unit (+ up to $1.60 noise). Payment fee 2.9 % + $0.30.
- Refunds: base return rate by category (Accessories 4 % … Sneakers 17 %), ×1.5 if delivery was late,
  ×1.15 on first orders; 80 % of refunds are full, 20 % half. **COGS is not recovered on returns** (no restocking
  credit), which is conservative.
- No overhead, no customer-service cost, no retention-marketing cost (email/SMS), no returns handling cost.

## Traffic and conversion

- Link click-through per unit reach depends on hidden content intent (product 1.35×, community 1.05×,
  entertainment 0.6×), content type (Story 1.35× … Static 0.8×), discount (+1 % per 0.7 discount points) and
  audience dilution at extreme reach (`shock^-0.22`).
- On-site conversion: add-to-cart ≈ 15 % base, ×1.4 for product-intent content, ×(1 + discount/45);
  checkout 46 % of carts; purchase 56 % of checkouts. Session-to-purchase conversion is ≈ 5–7 %, which is high
  for cold Instagram traffic in the real world; scale it down and CAC rises proportionally.
- Every converting session becomes a **new** customer. There is no existing customer base and no
  cross-campaign re-acquisition, so attribution is clean by construction. Real data would need an attribution
  rule and would have more noise.

## Customer behaviour

- The 90-day repeat log-odds have **no virality term** (see `methodology.md` §2). Repeaters' first gap is
  90 × Beta(1.4, 2.2) days (mean ≈ 35); later gaps ~ Gamma with mean 20–34 days depending on affinity.
- 12 % of non-repeaters re-activate after day 90 (so "no repeat in 90 days" is not "churned forever").
- Discount dependency: probability a repeat order uses a promo code = 0.10 + 0.45 × (first-order discount / 30).
- Repeat orders re-buy the first category 55 % of the time.

## Analytical limitations

- **Last-touch attribution** to the acquiring campaign; later orders are credited to that cohort even if an
  email or a later Reel triggered them.
- Viral is defined by within-portfolio percentiles (p90 reach, p75 share rate); with 120 campaigns that yields
  8 viral campaigns. Customer-level tests have thousands of observations; campaign-level comparisons within the
  viral group are small-sample and treated as directional.
- LTV is truncated at 90 days (plus a 180-day view for payback). Long-lived customers are worth more than the
  90-day figure shows; this understates value uniformly, not differentially.
- The budget-reallocation scenario in notebook 05 assumes CAC does not rise when top-quartile campaigns are
  scaled — an upper bound, not a forecast.
- The customer model is evaluated on a single time-based holdout; no hyperparameter search was run, and the
  reported AUC (≈ 0.68) should be read as "useful, not decisive".
- All results are from **one random seed (42)**. Re-running with another seed changes numbers but, by
  construction, not the mechanism.
