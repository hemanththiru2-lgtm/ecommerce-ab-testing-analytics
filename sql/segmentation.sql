-- =============================================================================
-- segmentation.sql — Segment Deep-Dive Analytics
-- The project's strongest business insight layer.
-- =============================================================================


-- =============================================================================
-- Q1: PROFIT IMPACT BY CATEGORY (The Core Segment Question)
-- "Which product categories benefit from the coupon?"
-- =============================================================================
SELECT
    category_top,
    verdict,
    COUNT(*)                                    AS segment_count,
    ROUND(SUM(net_profit_impact), 2)            AS total_profit_impact,
    ROUND(AVG(conv_lift_pp), 2)                 AS avg_conv_lift_pp,
    ROUND(SUM(discount_cost), 2)                AS total_coupon_spend
FROM profit_impact
WHERE segment_type = 'category_top'
GROUP BY category_top, verdict
ORDER BY total_profit_impact DESC;


-- =============================================================================
-- Q2: PRICE BUCKET ANALYSIS (ROI by price tier)
-- "Does the coupon work better for cheap or expensive products?"
-- =============================================================================
SELECT
    price_bucket,
    ROUND(AVG(conv_lift_pp), 2)                 AS avg_conversion_lift_pp,
    ROUND(SUM(incremental_net_revenue), 2)       AS incremental_revenue,
    ROUND(SUM(discount_cost), 2)                AS coupon_spend,
    ROUND(SUM(net_profit_impact), 2)            AS net_roi,
    verdict
FROM profit_impact
WHERE segment_type = 'price_bucket'
GROUP BY price_bucket, verdict
ORDER BY net_roi DESC;


-- =============================================================================
-- Q3: CATEGORY × PRICE BUCKET CROSS ANALYSIS
-- "Where exactly does the coupon win vs. lose?"
-- =============================================================================
SELECT
    category_top,
    price_bucket,
    ROUND(conv_lift_pp, 2)                      AS conversion_lift_pp,
    ROUND(incremental_net_revenue, 2)            AS incremental_revenue,
    ROUND(discount_cost, 2)                      AS coupon_cost,
    ROUND(net_profit_impact, 2)                  AS net_roi,
    verdict
FROM profit_impact
WHERE segment_type = 'category_top+price_bucket'
ORDER BY net_profit_impact ASC;   -- Worst performers first


-- =============================================================================
-- Q4: TOP 10 PROFITABLE SEGMENT OPPORTUNITIES
-- "Where should we roll out the coupon selectively?"
-- =============================================================================
SELECT
    segment_type,
    category_top,
    price_bucket,
    user_type,
    ROUND(conv_lift_pp, 2)                      AS conv_lift_pp,
    ROUND(net_profit_impact, 2)                  AS net_roi,
    verdict
FROM profit_impact
WHERE verdict = 'Profitable'
ORDER BY net_profit_impact DESC
LIMIT 10;


-- =============================================================================
-- Q5: TOP 10 LOSS-MAKING SEGMENTS
-- "Where should we NEVER show the coupon?"
-- =============================================================================
SELECT
    segment_type,
    category_top,
    price_bucket,
    user_type,
    ROUND(conv_lift_pp, 2)                      AS conv_lift_pp,
    ROUND(net_profit_impact, 2)                  AS net_roi,
    verdict
FROM profit_impact
WHERE verdict = 'Loss'
ORDER BY net_profit_impact ASC
LIMIT 10;


-- =============================================================================
-- Q6: NEW vs RETURNING USER — Segment Profit Breakdown
-- =============================================================================
SELECT
    user_type,
    ROUND(AVG(conv_lift_pp), 2)                 AS avg_conv_lift_pp,
    ROUND(SUM(incremental_net_revenue), 2)       AS total_incremental_rev,
    ROUND(SUM(discount_cost), 2)                AS total_coupon_spend,
    ROUND(SUM(net_profit_impact), 2)            AS total_net_roi,
    ROUND(
        CAST(SUM(CASE WHEN verdict='Profitable' THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(COUNT(*),0) * 100, 1
    )                                           AS profitable_segment_pct
FROM profit_impact
WHERE user_type IS NOT NULL
GROUP BY user_type
ORDER BY total_net_roi DESC;


-- =============================================================================
-- Q7: FINAL BUSINESS RECOMMENDATION SUMMARY
-- This is the exact data that feeds the Power BI "Recommendation" page
-- =============================================================================
SELECT
    'Total Segments Analysed'   AS metric, COUNT(*)               AS value FROM profit_impact
UNION ALL
SELECT 'Profitable Segments',   COUNT(*) FROM profit_impact WHERE verdict='Profitable'
UNION ALL
SELECT 'Break-Even Segments',   COUNT(*) FROM profit_impact WHERE verdict='Break-Even'
UNION ALL
SELECT 'Loss-Making Segments',  COUNT(*) FROM profit_impact WHERE verdict='Loss'
UNION ALL
SELECT 'Total Coupon Spend ($)', ROUND(SUM(discount_cost),2) FROM profit_impact
UNION ALL
SELECT 'Net ROI ($)',            ROUND(SUM(net_profit_impact),2) FROM profit_impact
UNION ALL
SELECT 'Avg Conv Lift (pp)',     ROUND(AVG(conv_lift_pp),2) FROM profit_impact;
