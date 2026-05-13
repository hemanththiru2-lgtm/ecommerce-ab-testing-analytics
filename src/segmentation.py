"""
segmentation.py
───────────────
Stage 3 of the pipeline: Deep-dive segment KPI calculations.

Input : sessions DataFrame (from experiment_engine.py)
Output: data/processed/segment_results.csv
        Writes to database/experiment.db → table: segment_results

Answers: "Which segments benefit from the coupon, and which lose money?"
Segments: category, price bucket, user type, weekday/weekend, hour of day
"""

import os
import sqlite3

import pandas as pd

from config import (
    SEGMENT_RESULTS_PATH,
    DATABASE_PATH
)


def _segment_kpis(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    """
    Generic helper: compute KPIs for any list of grouping columns.
    Returns one row per (segment, ab_group) combination.
    """
    agg = (
        df.groupby(group_cols + ["ab_group"])
        .agg(
            sessions       = ("user_session",    "count"),
            conversions    = ("converted",        "sum"),
            gross_revenue  = ("gross_revenue",    "sum"),
            discount_cost  = ("discount_applied", "sum"),
            net_revenue    = ("net_revenue",      "sum"),
        )
        .reset_index()
    )
    agg["conversion_rate"]     = agg["conversions"] / agg["sessions"]
    agg["revenue_per_session"] = agg["net_revenue"]  / agg["sessions"]
    agg["segment_type"]        = "+".join(group_cols)
    return agg


def compute_all_segments(sessions: pd.DataFrame) -> pd.DataFrame:
    """
    Build segment KPI tables across four dimensions:
      1. Product category
      2. Price bucket
      3. User type (New vs Returning)
      4. Weekday vs Weekend

    For each segment, side-by-side A vs B comparison is ready for Power BI.
    """
    print("[SEG 1/1] Computing segment KPIs...")

    parts = [
        _segment_kpis(sessions, ["category_top"]),
        _segment_kpis(sessions, ["price_bucket"]),
        _segment_kpis(sessions, ["user_type"]),
        _segment_kpis(sessions, ["category_top", "price_bucket"]),
    ]

    seg_df = pd.concat(parts, ignore_index=True)

    # ── Profit Impact Column (the key insight) ────────────────────────────────
    # Pivot A and B side by side to calculate incremental net revenue
    b = seg_df[seg_df["ab_group"] == "B"].copy()
    a = seg_df[seg_df["ab_group"] == "A"].copy()

    key_cols = ["segment_type", "category_top", "price_bucket", "user_type"]
    key_cols = [c for c in key_cols if c in b.columns]

    merged = b.merge(
        a[key_cols + ["net_revenue", "conversion_rate"]],
        on=key_cols,
        suffixes=("_b", "_a"),
        how="left"
    )
    merged["incremental_net_revenue"] = merged["net_revenue_b"] - merged["net_revenue_a"]
    merged["conv_lift_pp"]            = (
        merged["conversion_rate_b"] - merged["conversion_rate_a"]
    ) * 100
    merged["net_profit_impact"]       = (
        merged["incremental_net_revenue"] - merged["discount_cost"]
    )
    merged["verdict"] = merged["net_profit_impact"].apply(
        lambda x: "Profitable" if x > 0 else ("Break-Even" if x >= -100 else "Loss")
    )

    print(f"         Segment rows computed : {len(seg_df):,}")
    profitable = (merged["verdict"] == "Profitable").sum()
    loss       = (merged["verdict"] == "Loss").sum()
    print(f"         Profitable segments   : {profitable}")
    print(f"         Loss-making segments  : {loss}")

    return seg_df, merged


def save_segments(seg_df: pd.DataFrame, profit_df: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(SEGMENT_RESULTS_PATH), exist_ok=True)

    seg_df.to_csv(SEGMENT_RESULTS_PATH, index=False)
    print(f"  ✅ segment_results.csv → {SEGMENT_RESULTS_PATH}")

    profit_path = SEGMENT_RESULTS_PATH.replace("segment_results", "profit_impact")
    profit_df.to_csv(profit_path, index=False)
    print(f"  ✅ profit_impact.csv   → {profit_path}")

    conn = sqlite3.connect(DATABASE_PATH)
    seg_df.to_sql("segment_results",  conn, if_exists="replace", index=False)
    profit_df.to_sql("profit_impact", conn, if_exists="replace", index=False)
    conn.close()
    print(f"  ✅ Written to          → {DATABASE_PATH}")


# ── Public API ────────────────────────────────────────────────────────────────
def run(sessions: pd.DataFrame, save: bool = True):
    seg_df, profit_df = compute_all_segments(sessions)
    if save:
        save_segments(seg_df, profit_df)
    return seg_df, profit_df


if __name__ == "__main__":
    from config import PROCESSED_DATA_PATH
    df = pd.read_csv(PROCESSED_DATA_PATH)
    run(df)
