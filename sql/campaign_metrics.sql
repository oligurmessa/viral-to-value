-- =====================================================================
-- campaign_metrics.sql
-- The executive view: one row per campaign with virality classification,
-- CAC, 7-day ROAS, 90-day CM-LTV per customer, LTV:CAC and 90-day profit.
--
-- Viral := reach >= 90th percentile AND share_rate >= 75th percentile
-- =====================================================================

WITH engagement AS (
    SELECT
        c.*,
        shares::NUMERIC / reach                                   AS share_rate,
        saves::NUMERIC  / reach                                   AS save_rate,
        (likes + comments + shares + saves)::NUMERIC / reach      AS engagement_rate
    FROM campaigns c
),
thresholds AS (
    SELECT
        percentile_cont(0.90) WITHIN GROUP (ORDER BY reach)      AS reach_p90,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY share_rate) AS share_p75
    FROM engagement
),
classified AS (
    SELECT e.*,
           CASE WHEN e.reach >= t.reach_p90 AND e.share_rate >= t.share_p75 THEN 1 ELSE 0 END AS is_viral
    FROM engagement e CROSS JOIN thresholds t
),
order_cm AS (
    SELECT
        cu.acquisition_campaign                                                        AS campaign_id,
        o.customer_id,
        o.order_date,
        o.net_revenue,
        o.gross_revenue,
        o.discount_amount,
        o.refund_amount,
        o.is_first_order,
        o.net_revenue - o.cogs - o.shipping_cost - o.payment_fee - o.refund_amount    AS contribution_margin,
        o.order_date - cu.acquisition_date                                             AS days_since_acq,
        o.order_date - c.campaign_date                                                 AS days_since_campaign
    FROM orders o
    JOIN customers cu ON cu.customer_id = o.customer_id
    JOIN campaigns  c ON c.campaign_id  = cu.acquisition_campaign
),
cohort AS (
    SELECT
        campaign_id,
        COUNT(DISTINCT customer_id)                                                    AS new_customers,
        SUM(CASE WHEN days_since_campaign <= 7 THEN net_revenue ELSE 0 END)            AS revenue_7d,
        SUM(CASE WHEN days_since_acq <= 90 THEN contribution_margin ELSE 0 END)        AS cm_90d_total,
        SUM(CASE WHEN days_since_acq <= 90 THEN net_revenue ELSE 0 END)                AS revenue_90d_total,
        COUNT(DISTINCT CASE WHEN is_first_order = 0 AND days_since_acq <= 90 THEN customer_id END) AS repeaters_90d,
        SUM(refund_amount) / NULLIF(SUM(gross_revenue), 0)                             AS refund_rate,
        SUM(discount_amount) / NULLIF(SUM(gross_revenue), 0)                           AS discount_rate,
        AVG(CASE WHEN is_first_order = 1 THEN net_revenue END)                         AS avg_first_order_value
    FROM order_cm
    GROUP BY campaign_id
)
SELECT
    k.campaign_id,
    k.campaign_date,
    k.campaign_type,
    k.content_type,
    k.creator_tier,
    k.discount_pct,
    k.is_viral,
    k.reach,
    ROUND(100 * k.share_rate, 3)                                        AS share_rate_pct,
    ROUND(100 * k.save_rate, 3)                                         AS save_rate_pct,
    ROUND(100 * k.engagement_rate, 2)                                   AS engagement_rate_pct,
    k.spend,
    COALESCE(h.new_customers, 0)                                        AS new_customers,
    ROUND(k.spend / NULLIF(h.new_customers, 0), 2)                      AS cac,
    ROUND(h.revenue_7d / k.spend, 2)                                    AS roas_7d,
    ROUND(h.avg_first_order_value, 2)                                   AS avg_first_order_value,
    ROUND(100.0 * h.repeaters_90d / NULLIF(h.new_customers, 0), 1)      AS repeat_90d_pct,
    ROUND(h.revenue_90d_total / NULLIF(h.new_customers, 0), 2)          AS revenue_90d_per_customer,
    ROUND(h.cm_90d_total / NULLIF(h.new_customers, 0), 2)               AS cm_ltv_90d_per_customer,
    ROUND((h.cm_90d_total / NULLIF(h.new_customers, 0))
          / NULLIF(k.spend / NULLIF(h.new_customers, 0), 0), 2)         AS ltv_to_cac,
    ROUND(h.cm_90d_total - k.spend, 2)                                  AS profit_90d,
    ROUND(100 * h.refund_rate, 1)                                       AS refund_rate_pct,
    ROUND(100 * h.discount_rate, 1)                                     AS discount_rate_pct
FROM classified k
LEFT JOIN cohort h ON h.campaign_id = k.campaign_id
ORDER BY ltv_to_cac DESC NULLS LAST;
