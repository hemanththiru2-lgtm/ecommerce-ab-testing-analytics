# =============================================================================
# config.py — Central Configuration for the A/B Testing Pipeline
# =============================================================================
# All tunable parameters live here. Change these values to re-run the
# experiment with different assumptions — no need to touch any other file.
# =============================================================================

# ── Paths ─────────────────────────────────────────────────────────────────────
RAW_DATA_PATH       = "data/raw/2019-Dec.csv"
PROCESSED_DATA_PATH = "data/processed/sessions.csv"
AB_RESULTS_PATH     = "data/processed/ab_results.csv"
SEGMENT_RESULTS_PATH= "data/processed/segment_results.csv"
DATABASE_PATH       = "database/experiment.db"

# ── Experiment Parameters ─────────────────────────────────────────────────────
EXPERIMENT_NAME     = "Coupon_Test_V1"   # Salt used for deterministic MD5 hashing
RANDOM_SEED         = 42                 # Controls numpy reproducibility
SPLIT_RATIO         = 0.5               # 0.5 = 50/50 A/B split

# ── Coupon Effect Parameters ──────────────────────────────────────────────────
BASE_CONVERSION_LIFT = 0.08             # Base 8% chance for non-buyers to convert
MAX_COUPON_VALUE     = 50.0             # Maximum dollar discount ($50 cap)
MAX_COUPON_PCT       = 0.20             # Coupon never exceeds 20% of order value

# ── HTE Feature Multipliers ───────────────────────────────────────────────────
# These control how different user segments respond to the coupon.
# Multipliers are applied on top of BASE_CONVERSION_LIFT.
PRICE_MULTIPLIERS = {
    "lt_25":   2.0,   # Items under $25   → Impulse buy territory
    "lt_100":  1.5,   # $25–$100
    "lt_300":  1.0,   # $100–$300         → Neutral
    "lt_1000": 0.5,   # $300–$1k          → Less impulsive
    "gt_1000": 0.2,   # $1k+              → High consideration purchase
}
NEW_USER_MULTIPLIER     = 1.5           # New users are more deal-hungry
CART_ABANDON_MULTIPLIER = 2.0           # Cart abandoners are warmest leads
WEEKEND_MULTIPLIER      = 1.2           # Weekend shoppers are more leisure-driven

# ── Guardrails ────────────────────────────────────────────────────────────────
CONFIDENCE_LEVEL        = 0.95          # For two-proportion z-test
REFUND_SPIKE_THRESHOLD  = 0.015        # Flag experiment if refund rate rises >1.5%

# ── Price Bucket Definitions ──────────────────────────────────────────────────
PRICE_BINS   = [0, 25, 100, 300, 1000, float("inf")]
PRICE_LABELS = ["<$25", "$25-$100", "$100-$300", "$300-$1k", "$1k+"]
