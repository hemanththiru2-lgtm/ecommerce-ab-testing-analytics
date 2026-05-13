"""
experiment_engine.py
─────────────────────
Stage 2 of the pipeline: A/B split + coupon effect injection + KPI calculation.

Input : data/processed/sessions.csv   (from data_preprocessing.py)
Output: data/processed/ab_results.csv
        database/experiment.db

Two core algorithms:
  1. Deterministic MD5 Hashing  → production-grade traffic splitting
  2. HTE Feature-Weighted Model → realistic, heterogeneous coupon response
"""

import hashlib
import os
import sqlite3

import numpy as np
import pandas as pd
from scipy import stats

from config import (
    EXPERIMENT_NAME, RANDOM_SEED, SPLIT_RATIO,
    BASE_CONVERSION_LIFT, MAX_COUPON_VALUE, MAX_COUPON_PCT,
    PRICE_MULTIPLIERS, NEW_USER_MULTIPLIER,
    CART_ABANDON_MULTIPLIER, WEEKEND_MULTIPLIER,
    CONFIDENCE_LEVEL,
    PROCESSED_DATA_PATH, AB_RESULTS_PATH, DATABASE_PATH
)

np.random.seed(RANDOM_SEED)


# =============================================================================
# ALGORITHM 1: DETERMINISTIC MD5 HASHING (Traffic Split)
# =============================================================================
def _hash_user(user_id: str, experiment_name: str) -> str:
    """
    Assign a user deterministically to Group A or B.

    Method (same as Optimizely / LaunchDarkly):
      1. Combine user_id + experiment salt  →  "12345_Coupon_Test_V1"
      2. MD5 hash the string               →  "8f4b2a9c..."
      3. Convert hex → int                 →  massive number
      4. Modulo 100                        →  bucket 0–99
      5. Bucket < 50 → "A",  ≥ 50 → "B"

    Key property: Deterministic — same user always gets same group,
    regardless of how many times the pipeline reruns.
    """
    raw     = f"{user_id}_{experiment_name}"
    hex_val = hashlib.md5(raw.encode("utf-8")).hexdigest()
    bucket  = int(hex_val, 16) % 100
    return "B" if bucket >= (SPLIT_RATIO * 100) else "A"


def assign_groups(sessions: pd.DataFrame) -> pd.DataFrame:
    """Apply MD5 hashing to every user and run SRM validation."""
    print("[EXP 1/3] Assigning A/B groups via deterministic MD5 hashing...")

    sessions = sessions.copy()
    sessions["ab_group"] = sessions["user_id"].astype(str).apply(
        lambda uid: _hash_user(uid, EXPERIMENT_NAME)
    )

    counts = sessions["ab_group"].value_counts()
    total  = len(sessions)

    print(f"         Group A (Control)  : {counts.get('A',0):,}  "
          f"({counts.get('A',0)/total*100:.1f}%)")
    print(f"         Group B (Treatment): {counts.get('B',0):,}  "
          f"({counts.get('B',0)/total*100:.1f}%)")

    # ── SRM Chi-Square Check ──────────────────────────────────────────────────
    observed = [counts.get("A", 0), counts.get("B", 0)]
    expected = [total * SPLIT_RATIO, total * (1 - SPLIT_RATIO)]
    chi2, p  = stats.chisquare(f_obs=observed, f_exp=expected)

    # Note: With 800k+ sessions, chi-square is hypersensitive.
    # We use p>0.001 as the practical threshold for large-scale data.
    srm_ok = p > 0.001
    print(f"\n         SRM Test → χ²={chi2:.4f}, p={p:.4f}  |  "
          + ("✅ PASS: Traffic split is valid" if srm_ok
             else "⚠️  WARNING: Minor split imbalance detected (common with hashing at scale)"))

    return sessions


# =============================================================================
# ALGORITHM 2: HTE FEATURE-WEIGHTED PROBABILITY MODEL (Coupon Injection)
# =============================================================================
def _compute_lift_probability(row: pd.Series) -> float:
    """
    Calculate each user's personal probability of converting due to the coupon.

    This is the Heterogeneous Treatment Effects (HTE) model:
    - Same coupon, different impact per user based on their features.
    - Mirrors how companies like Uber/Meta model individual-level treatment response.

    Returns a probability between 0 and 0.95.
    """
    p = BASE_CONVERSION_LIFT   # 8% base for everyone in Group B

    # ── Price sensitivity multiplier ──────────────────────────────────────────
    price = row["max_price"]
    if   price < 25:    p *= PRICE_MULTIPLIERS["lt_25"]
    elif price < 100:   p *= PRICE_MULTIPLIERS["lt_100"]
    elif price < 300:   p *= PRICE_MULTIPLIERS["lt_300"]
    elif price < 1000:  p *= PRICE_MULTIPLIERS["lt_1000"]
    else:               p *= PRICE_MULTIPLIERS["gt_1000"]

    # ── User lifecycle multiplier ─────────────────────────────────────────────
    if row["is_new_user"] == 1:
        p *= NEW_USER_MULTIPLIER        # New users are more deal-hungry

    # ── Behavioural signal multiplier ─────────────────────────────────────────
    if row["cart_abandon"] == 1:
        p *= CART_ABANDON_MULTIPLIER    # Already showed purchase intent

    # ── Temporal multiplier ───────────────────────────────────────────────────
    if row["is_weekend"] == 1:
        p *= WEEKEND_MULTIPLIER         # Leisure shopping → more impulsive

    return min(p, 0.95)   # Hard cap — never assume 100% certainty


def inject_coupon(sessions: pd.DataFrame) -> pd.DataFrame:
    """
    Apply the coupon treatment to Group B sessions.

    Two sub-effects modelled:
      a) Persuadables   — non-buyers who convert due to coupon (HTE model)
      b) Sure-Things    — existing buyers who get discount deducted (cannibalization)
    """
    print("[EXP 2/3] Injecting coupon effect (HTE model)...")

    sessions = sessions.copy()
    sessions["discount_applied"] = 0.0
    sessions["net_revenue"]      = sessions["gross_revenue"].copy()
    sessions["coupon_triggered"] = 0

    is_group_b = sessions["ab_group"] == "B"

    # ── (a) Persuadables: Non-buyers who might convert ────────────────────────
    non_buyers_b = is_group_b & (sessions["converted"] == 0)
    probs        = sessions[non_buyers_b].apply(_compute_lift_probability, axis=1)
    triggered    = np.random.binomial(1, probs.values)
    triggered_idx = sessions[non_buyers_b].index[triggered == 1]

    sessions.loc[triggered_idx, "converted"]        = 1
    sessions.loc[triggered_idx, "purchases"]        = 1
    sessions.loc[triggered_idx, "coupon_triggered"] = 1
    # Use their max browsed price as proxy revenue (they have no prior purchase)
    sessions.loc[triggered_idx, "gross_revenue"]    = sessions.loc[triggered_idx, "max_price"]

    # ── (b) Apply discount to all Group B buyers ──────────────────────────────
    # PROFESSIONAL RULE: discount = min($MAX_COUPON_VALUE, 20% of order)
    # Prevents negative revenue on cheap items — a real production safeguard.
    all_buyers_b = is_group_b & (sessions["converted"] == 1)
    discounts    = sessions.loc[all_buyers_b, "gross_revenue"].apply(
        lambda rev: min(MAX_COUPON_VALUE, rev * MAX_COUPON_PCT) if rev > 0 else 0.0
    )
    sessions.loc[all_buyers_b, "discount_applied"] = discounts.values
    sessions.loc[all_buyers_b, "net_revenue"]      = (
        sessions.loc[all_buyers_b, "gross_revenue"] - discounts.values
    ).clip(lower=0)

    # Group A: net_revenue = gross_revenue (no coupon)
    group_a_buyers = (~is_group_b) & (sessions["converted"] == 1)
    sessions.loc[group_a_buyers, "net_revenue"] = sessions.loc[group_a_buyers, "gross_revenue"]

    # ── Summary ───────────────────────────────────────────────────────────────
    a_cr  = sessions[sessions["ab_group"]=="A"]["converted"].mean() * 100
    b_cr  = sessions[sessions["ab_group"]=="B"]["converted"].mean() * 100
    total_disc = sessions["discount_applied"].sum()

    print(f"         New conversions triggered : {triggered.sum():,}")
    print(f"         Total discount cost       : ${total_disc:,.2f}")
    print(f"         Group A conversion rate   : {a_cr:.2f}%")
    print(f"         Group B conversion rate   : {b_cr:.2f}%")
    print(f"         Conversion lift           : {b_cr - a_cr:+.2f} pp")

    return sessions


# =============================================================================
# KPI CALCULATION & GUARDRAILS
# =============================================================================
def calculate_kpis(sessions: pd.DataFrame) -> pd.DataFrame:
    """Compute per-group KPIs and run statistical + business guardrail checks."""
    print("[EXP 3/3] Calculating KPIs and guardrail checks...")

    rows = []
    for group in ["A", "B"]:
        g   = sessions[sessions["ab_group"] == group]
        n   = len(g)
        cv  = int(g["converted"].sum())
        gr  = g["gross_revenue"].sum()
        nr  = g["net_revenue"].sum()
        dc  = g["discount_applied"].sum()
        rows.append({
            "ab_group"          : group,
            "sessions"          : n,
            "conversions"       : cv,
            "conversion_rate"   : cv / n if n > 0 else 0,
            "gross_revenue"     : gr,
            "discount_cost"     : dc,
            "net_revenue"       : nr,
            "revenue_per_session": nr / n if n > 0 else 0,
            "avg_order_value"   : gr / cv if cv > 0 else 0,
        })

    kpi_df = pd.DataFrame(rows)

    a = kpi_df[kpi_df["ab_group"] == "A"].iloc[0]
    b = kpi_df[kpi_df["ab_group"] == "B"].iloc[0]

    # ── Statistical Test (Manual Two-Proportion Z-Test) ─────────────────────
    # scipy.stats.norm is always available — no external dependency needed.
    n_a  = int(a["sessions"]);    n_b  = int(b["sessions"])
    cv_a = int(a["conversions"]); cv_b = int(b["conversions"])
    p_a  = cv_a / n_a;            p_b  = cv_b / n_b
    p_pool = (cv_a + cv_b) / (n_a + n_b)
    se     = np.sqrt(p_pool * (1 - p_pool) * (1/n_a + 1/n_b))
    z_stat = (p_b - p_a) / se if se > 0 else 0
    p_val  = float(2 * (1 - stats.norm.cdf(abs(z_stat))))
    is_sig = p_val < (1 - CONFIDENCE_LEVEL)
    conv_lift    = (b["conversion_rate"] - a["conversion_rate"]) / a["conversion_rate"] * 100
    rev_change   = (b["net_revenue"] - a["net_revenue"]) / a["net_revenue"] * 100 if a["net_revenue"] > 0 else 0
    profit_pass  = b["net_revenue"] >= a["net_revenue"]

    print(f"\n  {'═'*52}")
    print(f"   KPI RESULTS")
    print(f"  {'═'*52}")
    print(f"   Conversion Lift     : {conv_lift:+.2f}%")
    print(f"   Net Revenue Change  : {rev_change:+.2f}%")
    print(f"   Total Discount Cost : ${b['discount_cost']:,.2f}")
    print(f"   Statistical Sig.    : {'✅ YES' if is_sig else '❌ NO'} (p={p_val:.4f})")
    print(f"   Profit Guardrail    : {'✅ PASS' if profit_pass else '🚨 FAIL'}")
    if not profit_pass:
        print("   ⚠  RECOMMENDATION  : DO NOT launch coupon globally.")
        print("      Investigate high-ROI segments first (see segmentation.py).")
    print(f"  {'═'*52}\n")

    # Attach summary stats to both rows for Power BI
    kpi_df["conv_lift_pct"]    = conv_lift
    kpi_df["rev_change_pct"]   = rev_change
    kpi_df["p_value"]          = p_val
    kpi_df["is_significant"]   = int(is_sig)
    kpi_df["profit_pass"]      = int(profit_pass)

    return kpi_df


# =============================================================================
# PERSISTENCE
# =============================================================================
def save_outputs(sessions: pd.DataFrame, kpi_df: pd.DataFrame) -> None:
    """Write session data and KPIs to CSV and SQLite."""
    os.makedirs(os.path.dirname(AB_RESULTS_PATH),  exist_ok=True)
    os.makedirs(os.path.dirname(DATABASE_PATH),     exist_ok=True)

    sessions.to_csv(PROCESSED_DATA_PATH, index=False)
    kpi_df.to_csv(AB_RESULTS_PATH,       index=False)
    print(f"  ✅ sessions.csv   → {PROCESSED_DATA_PATH}")
    print(f"  ✅ ab_results.csv → {AB_RESULTS_PATH}")

    conn = sqlite3.connect(DATABASE_PATH)
    sessions.to_sql("sessions",   conn, if_exists="replace", index=False)
    kpi_df.to_sql("ab_results",   conn, if_exists="replace", index=False)
    conn.close()
    print(f"  ✅ experiment.db  → {DATABASE_PATH}")


# ── Public API ────────────────────────────────────────────────────────────────
def run(sessions: pd.DataFrame, save: bool = True):
    sessions = assign_groups(sessions)
    sessions = inject_coupon(sessions)
    kpi_df   = calculate_kpis(sessions)
    if save:
        save_outputs(sessions, kpi_df)
    return sessions, kpi_df


if __name__ == "__main__":
    df = pd.read_csv(PROCESSED_DATA_PATH)
    run(df)
