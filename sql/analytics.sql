-- =============================================================================
-- analytics.sql — Core A/B Test Analytics
-- Database: database/experiment.db
-- Run in: DB Browser for SQLite, DBeaver, or any SQLite-compatible client
-- =============================================================================


-- =============================================================================
-- Q1: TOP-LINE KPI SUMMARY (Executive Dashboard — Page 1 of Power BI)
-- =============================================================================
SELECT
    ab_group,
    sessions,
    conversions,
    ROUND(conversion_rate * 100, 2)         AS conversion_rate_pct,
    ROUND(gross_revenue, 2)                 AS gross_revenue,
    ROUND(discount_cost, 2)                 AS coupon_cost,
    ROUND(net_revenue, 2)                   AS net_revenue,
    ROUND(revenue_per_session, 2)           AS revenue_per_session,
    ROUND(avg_order_value, 2)               AS avg_order_value,
    ROUND(conv_lift_pct, 2)                 AS conversion_lift_pct,
    ROUND(rev_change_pct, 2)                AS net_revenue_change_pct,
    ROUND(p_value, 4)                       AS p_value,
    CASE WHEN is_significant = 1 THEN 'YES' ELSE 'NO' END AS statistically_significant,
    CASE WHEN profit_pass    = 1 THEN 'PASS' ELSE 'FAIL' END AS profit_guardrail
FROM ab_results
ORDER BY ab_group;


-- =============================================================================
-- Q2: CONVERSION LIFT & INCREMENTAL REVENUE (A vs B Side-by-Side)
-- =============================================================================
WITH g AS (
    SELECT
        ab_group,
        COUNT(*)                              AS sessions,
        SUM(converted)                        AS conversions,
        ROUND(AVG(CAST(converted AS REAL))*100, 4) AS cr_pct,
        ROUND(SUM(net_revenue), 2)            AS net_rev,
        ROUND(SUM(discount_applied), 2)       AS coupon_cost
    FROM sessions
    GROUP BY ab_group
)
SELECT
    b.cr_pct                                AS group_b_cr,
    a.cr_pct                                AS group_a_cr,
    ROUND(b.cr_pct - a.cr_pct, 4)          AS absolute_lift_pp,
    ROUND((b.cr_pct-a.cr_pct)/a.cr_pct*100,2) AS relative_lift_pct,
    ROUND(b.net_rev - a.net_rev, 2)         AS incremental_net_revenue,
    b.coupon_cost                           AS total_coupon_spend,
    ROUND((b.net_rev-a.net_rev)-b.coupon_cost,2) AS true_roi
FROM g b JOIN g a ON a.ab_group='A'
WHERE b.ab_group='B';


-- =============================================================================
-- Q3: FUNNEL ANALYSIS (Where do users drop off?)
-- =============================================================================
SELECT
    ab_group,
    COUNT(DISTINCT user_session)              AS total_sessions,
    SUM(views)                                AS total_views,
    SUM(carts)                                AS total_carts,
    SUM(purchases)                            AS total_purchases,
    ROUND(CAST(SUM(carts) AS REAL)
          / NULLIF(SUM(views),0)*100, 2)     AS view_to_cart_pct,
    ROUND(CAST(SUM(purchases) AS REAL)
          / NULLIF(SUM(carts),0)*100, 2)     AS cart_to_purchase_pct,
    ROUND(CAST(SUM(cart_abandon) AS REAL)
          / NULLIF(SUM(carts),0)*100, 2)     AS cart_abandonment_pct,
    ROUND(CAST(SUM(converted) AS REAL)
          / NULLIF(COUNT(*),0)*100, 2)       AS overall_conversion_pct
FROM sessions
GROUP BY ab_group;


-- =============================================================================
-- Q4: NEW vs RETURNING USER IMPACT
-- =============================================================================
SELECT
    ab_group,
    user_type,
    COUNT(*)                                  AS sessions,
    SUM(converted)                            AS conversions,
    ROUND(AVG(CAST(converted AS REAL))*100,2) AS conversion_rate_pct,
    ROUND(SUM(net_revenue),2)                 AS net_revenue,
    ROUND(SUM(discount_applied),2)            AS coupon_cost,
    ROUND(SUM(net_revenue)/NULLIF(COUNT(*),0),2) AS revenue_per_session
FROM sessions
GROUP BY ab_group, user_type
ORDER BY ab_group, user_type;


-- =============================================================================
-- Q5: CART ABANDONERS — Are they the best target for coupons?
-- =============================================================================
SELECT
    ab_group,
    cart_abandon,
    COUNT(*)                                  AS sessions,
    SUM(converted)                            AS conversions,
    ROUND(AVG(CAST(converted AS REAL))*100,2) AS conversion_rate_pct,
    ROUND(SUM(net_revenue),2)                 AS net_revenue
FROM sessions
GROUP BY ab_group, cart_abandon
ORDER BY ab_group, cart_abandon DESC;


-- =============================================================================
-- Q6: HOUR-OF-DAY CONVERSION PATTERN
-- =============================================================================
SELECT
    ab_group,
    hour,
    COUNT(*)                                  AS sessions,
    SUM(converted)                            AS conversions,
    ROUND(AVG(CAST(converted AS REAL))*100,2) AS conversion_rate_pct,
    ROUND(SUM(net_revenue),2)                 AS net_revenue
FROM sessions
GROUP BY ab_group, hour
ORDER BY ab_group, hour;


-- =============================================================================
-- Q7: WEEKEND vs WEEKDAY
-- =============================================================================
SELECT
    ab_group,
    CASE WHEN is_weekend=1 THEN 'Weekend' ELSE 'Weekday' END AS day_type,
    COUNT(*)                                  AS sessions,
    SUM(converted)                            AS conversions,
    ROUND(AVG(CAST(converted AS REAL))*100,2) AS conversion_rate_pct,
    ROUND(SUM(net_revenue),2)                 AS net_revenue
FROM sessions
GROUP BY ab_group, is_weekend
ORDER BY ab_group, is_weekend;
