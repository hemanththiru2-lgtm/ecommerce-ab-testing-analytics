-- =============================================================================
-- schema.sql — Database Schema Definition
-- Shows SQL Engineering (not just querying)
-- Run once to validate table structure after main.py generates experiment.db
-- =============================================================================

-- Drop existing tables for clean re-runs
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS ab_results;
DROP TABLE IF EXISTS segment_results;
DROP TABLE IF EXISTS profit_impact;

-- =============================================================================
-- TABLE: sessions
-- One row per user session. The primary fact table.
-- =============================================================================
CREATE TABLE sessions (
    user_session        TEXT        NOT NULL,
    user_id             INTEGER     NOT NULL,
    views               INTEGER     DEFAULT 0,
    carts               INTEGER     DEFAULT 0,
    removes             INTEGER     DEFAULT 0,
    purchases           INTEGER     DEFAULT 0,
    gross_revenue       REAL        DEFAULT 0.0,
    max_price           REAL        DEFAULT 0.0,
    category_top        TEXT,
    brand               TEXT,
    hour                INTEGER,
    is_weekend          INTEGER     CHECK (is_weekend IN (0,1)),
    week_num            INTEGER,
    session_start       TIMESTAMP,
    converted           INTEGER     CHECK (converted IN (0,1)),
    cart_abandon        INTEGER     CHECK (cart_abandon IN (0,1)),
    price_bucket        TEXT,
    total_sessions      INTEGER,
    is_new_user         INTEGER     CHECK (is_new_user IN (0,1)),
    user_type           TEXT        CHECK (user_type IN ('New','Returning')),
    ab_group            TEXT        CHECK (ab_group IN ('A','B')),
    discount_applied    REAL        DEFAULT 0.0,
    net_revenue         REAL        DEFAULT 0.0,
    coupon_triggered    INTEGER     CHECK (coupon_triggered IN (0,1)),

    PRIMARY KEY (user_session)
);

-- =============================================================================
-- TABLE: ab_results
-- One row per A/B group. Top-level KPI summary.
-- =============================================================================
CREATE TABLE ab_results (
    ab_group            TEXT        PRIMARY KEY,
    sessions            INTEGER,
    conversions         INTEGER,
    conversion_rate     REAL,
    gross_revenue       REAL,
    discount_cost       REAL,
    net_revenue         REAL,
    revenue_per_session REAL,
    avg_order_value     REAL,
    conv_lift_pct       REAL,
    rev_change_pct      REAL,
    p_value             REAL,
    is_significant      INTEGER     CHECK (is_significant IN (0,1)),
    profit_pass         INTEGER     CHECK (profit_pass IN (0,1))
);

-- =============================================================================
-- TABLE: segment_results
-- KPIs broken down by segment dimension and A/B group.
-- =============================================================================
CREATE TABLE segment_results (
    segment_type        TEXT,
    category_top        TEXT,
    price_bucket        TEXT,
    user_type           TEXT,
    ab_group            TEXT        CHECK (ab_group IN ('A','B')),
    sessions            INTEGER,
    conversions         INTEGER,
    gross_revenue       REAL,
    discount_cost       REAL,
    net_revenue         REAL,
    conversion_rate     REAL,
    revenue_per_session REAL
);

-- =============================================================================
-- TABLE: profit_impact
-- Group B segments with incremental revenue vs. coupon cost comparison.
-- The key "business decision" table for Power BI.
-- =============================================================================
CREATE TABLE profit_impact (
    segment_type            TEXT,
    category_top            TEXT,
    price_bucket            TEXT,
    user_type               TEXT,
    sessions                INTEGER,
    net_revenue_b           REAL,
    net_revenue_a           REAL,
    discount_cost           REAL,
    incremental_net_revenue REAL,
    conv_lift_pp            REAL,
    net_profit_impact       REAL,
    verdict                 TEXT    CHECK (verdict IN ('Profitable','Break-Even','Loss'))
);

-- =============================================================================
-- INDEXES — Improve query performance on large datasets
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_sessions_ab_group    ON sessions(ab_group);
CREATE INDEX IF NOT EXISTS idx_sessions_converted   ON sessions(converted);
CREATE INDEX IF NOT EXISTS idx_sessions_category    ON sessions(category_top);
CREATE INDEX IF NOT EXISTS idx_sessions_user_type   ON sessions(user_type);
CREATE INDEX IF NOT EXISTS idx_profit_verdict       ON profit_impact(verdict);
