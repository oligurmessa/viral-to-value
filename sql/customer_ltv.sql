-- =====================================================================
-- customer_ltv.sql
-- Customer-level economics: first-order value, discount use, refunds,
-- and 30/60/90-day net revenue and contribution-margin LTV.
-- Contribution margin = net revenue - COGS - shipping - payment fee - refunds
-- =====================================================================

WITH order_cm AS (
    SELECT
        o.*,
        o.net_revenue - o.cogs - o.shipping_cost - o.payment_fee - o.refund_amount AS contribution_margin,
        o.order_date - cu.acquisition_date                                         AS days_since_acq,
        cu.acquisition_campaign
    FROM orders o
    JOIN customers cu ON cu.customer_id = o.customer_id
)
SELECT
    cu.customer_id,
    cu.acquisition_campaign,
    cu.acquisition_date,
    cu.age_group,
    cu.region,
    MAX(CASE WHEN oc.is_first_order = 1 THEN oc.net_revenue END)                          AS first_order_value,
    MAX(CASE WHEN oc.is_first_order = 1 AND oc.discount_amount > 0 THEN 1 ELSE 0 END)     AS used_discount_first_order,
    MAX(CASE WHEN oc.is_first_order = 1 AND oc.refund_amount > 0 THEN 1 ELSE 0 END)       AS first_order_refunded,
    COUNT(*)                                                                              AS orders_total,
    COUNT(*) FILTER (WHERE oc.days_since_acq <= 90)                                       AS orders_90d,
    CASE WHEN COUNT(*) FILTER (WHERE oc.is_first_order = 0 AND oc.days_since_acq <= 90) > 0 THEN 1 ELSE 0 END AS repeat_90d,
    ROUND(SUM(CASE WHEN oc.days_since_acq <= 30 THEN oc.net_revenue ELSE 0 END), 2)        AS net_revenue_30d,
    ROUND(SUM(CASE WHEN oc.days_since_acq <= 60 THEN oc.net_revenue ELSE 0 END), 2)        AS net_revenue_60d,
    ROUND(SUM(CASE WHEN oc.days_since_acq <= 90 THEN oc.net_revenue ELSE 0 END), 2)        AS net_revenue_90d,
    ROUND(SUM(CASE WHEN oc.days_since_acq <= 30 THEN oc.contribution_margin ELSE 0 END), 2) AS cm_ltv_30d,
    ROUND(SUM(CASE WHEN oc.days_since_acq <= 60 THEN oc.contribution_margin ELSE 0 END), 2) AS cm_ltv_60d,
    ROUND(SUM(CASE WHEN oc.days_since_acq <= 90 THEN oc.contribution_margin ELSE 0 END), 2) AS cm_ltv_90d,
    ROUND(SUM(CASE WHEN oc.days_since_acq <= 90 THEN oc.refund_amount ELSE 0 END), 2)      AS refunds_90d,
    ROUND(SUM(oc.contribution_margin), 2)                                                 AS cm_ltv_total
FROM customers cu
JOIN order_cm oc ON oc.customer_id = cu.customer_id
GROUP BY cu.customer_id, cu.acquisition_campaign, cu.acquisition_date, cu.age_group, cu.region
ORDER BY cm_ltv_90d DESC;
