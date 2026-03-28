-- =====================================================================
-- retention.sql
-- Customer order sequence with window functions, then 30/60/90-day
-- repeat-purchase rates and time-to-second-order per acquisition campaign.
-- =====================================================================

WITH ordered AS (
    SELECT
        o.customer_id,
        o.order_id,
        o.order_date,
        cu.acquisition_campaign,
        cu.acquisition_date,
        ROW_NUMBER() OVER (PARTITION BY o.customer_id ORDER BY o.order_date, o.order_id)         AS order_seq,
        LAG(o.order_date) OVER (PARTITION BY o.customer_id ORDER BY o.order_date, o.order_id)   AS prev_order_date,
        o.order_date - cu.acquisition_date                                                    AS days_since_acq
    FROM orders o
    JOIN customers cu ON cu.customer_id = o.customer_id
),
second_order AS (
    SELECT customer_id, acquisition_campaign, days_since_acq AS days_to_second_order,
           order_date - prev_order_date AS gap_days
    FROM ordered
    WHERE order_seq = 2
),
per_customer AS (
    SELECT
        cu.customer_id,
        cu.acquisition_campaign,
        CASE WHEN s.days_to_second_order <= 30 THEN 1 ELSE 0 END AS repeat_30d,
        CASE WHEN s.days_to_second_order <= 60 THEN 1 ELSE 0 END AS repeat_60d,
        CASE WHEN s.days_to_second_order <= 90 THEN 1 ELSE 0 END AS repeat_90d,
        s.days_to_second_order
    FROM customers cu
    LEFT JOIN second_order s ON s.customer_id = cu.customer_id
)
SELECT
    c.campaign_id,
    c.campaign_type,
    c.content_type,
    c.creator_tier,
    c.discount_pct,
    COUNT(*)                                                       AS new_customers,
    ROUND(100.0 * AVG(p.repeat_30d), 1)                            AS repeat_30d_pct,
    ROUND(100.0 * AVG(p.repeat_60d), 1)                            AS repeat_60d_pct,
    ROUND(100.0 * AVG(p.repeat_90d), 1)                            AS repeat_90d_pct,
    ROUND(AVG(p.days_to_second_order), 1)                          AS avg_days_to_second_order,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY p.days_to_second_order) AS median_days_to_second_order
FROM per_customer p
JOIN campaigns c ON c.campaign_id = p.acquisition_campaign
GROUP BY c.campaign_id, c.campaign_type, c.content_type, c.creator_tier, c.discount_pct
HAVING COUNT(*) >= 30                                              -- ignore tiny cohorts
ORDER BY repeat_90d_pct DESC;
