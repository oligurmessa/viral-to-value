-- =====================================================================
-- acquisition.sql
-- Campaign funnel: reach -> sessions -> add to cart -> checkout -> new customers
-- plus first-week revenue, CAC and 7-day ROAS per campaign.
-- =====================================================================

WITH funnel AS (
    SELECT
        s.campaign_id,
        COUNT(*)                                   AS sessions,
        SUM(s.add_to_cart)                         AS add_to_cart,
        SUM(s.checkout_started)                    AS checkout_started,
        SUM(s.purchase)                            AS purchases
    FROM sessions s
    WHERE s.traffic_source = 'instagram_campaign'
    GROUP BY s.campaign_id
),
new_customers AS (
    SELECT acquisition_campaign AS campaign_id, COUNT(*) AS new_customers
    FROM customers
    GROUP BY acquisition_campaign
),
first_week AS (                     -- revenue from the cohort within 7 days of the campaign date
    SELECT
        cu.acquisition_campaign AS campaign_id,
        SUM(o.net_revenue)      AS revenue_7d,
        COUNT(*)                AS orders_7d
    FROM orders o
    JOIN customers cu ON cu.customer_id = o.customer_id
    JOIN campaigns  c ON c.campaign_id  = cu.acquisition_campaign
    WHERE o.order_date - c.campaign_date <= 7
    GROUP BY cu.acquisition_campaign
)
SELECT
    c.campaign_id,
    c.campaign_date,
    c.campaign_type,
    c.content_type,
    c.creator_tier,
    c.discount_pct,
    c.spend,
    c.reach,
    f.sessions,
    ROUND(1000.0 * f.sessions / c.reach, 2)                          AS sessions_per_1k_reach,
    ROUND(100.0 * f.add_to_cart      / NULLIF(f.sessions, 0), 2)     AS add_to_cart_rate_pct,
    ROUND(100.0 * f.checkout_started / NULLIF(f.add_to_cart, 0), 2)  AS checkout_rate_pct,
    ROUND(100.0 * f.purchases        / NULLIF(f.checkout_started, 0), 2) AS purchase_rate_pct,
    ROUND(100.0 * f.purchases        / NULLIF(f.sessions, 0), 2)     AS session_conversion_pct,
    COALESCE(n.new_customers, 0)                                     AS new_customers,
    ROUND(c.spend / NULLIF(n.new_customers, 0), 2)                   AS cac,
    ROUND(COALESCE(w.revenue_7d, 0), 2)                              AS revenue_7d,
    ROUND(COALESCE(w.revenue_7d, 0) / c.spend, 2)                    AS roas_7d
FROM campaigns c
LEFT JOIN funnel        f ON f.campaign_id = c.campaign_id
LEFT JOIN new_customers n ON n.campaign_id = c.campaign_id
LEFT JOIN first_week    w ON w.campaign_id = c.campaign_id
ORDER BY new_customers DESC;
