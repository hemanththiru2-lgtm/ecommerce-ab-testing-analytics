"""
data_preprocessing.py
─────────────────────
Stage 1 of the pipeline: Raw Kaggle clickstream → Clean session-level dataset.

Input : data/raw/2019-Nov.csv   (real Kaggle event data)
Output: data/processed/sessions.csv

This module performs real ETL work:
  1. Load and validate raw event data
  2. Clean nulls, types, and malformed prices
  3. Aggregate event rows into one row per user session
  4. Engineer features (price buckets, new/returning user, weekday/weekend)
"""

import os
import pandas as pd
import numpy as np
from config import (
    RAW_DATA_PATH, PROCESSED_DATA_PATH,
    PRICE_BINS, PRICE_LABELS, RANDOM_SEED
)

np.random.seed(RANDOM_SEED)


# ── Step 1: Load Raw Data ─────────────────────────────────────────────────────
def load_raw(path: str = RAW_DATA_PATH) -> pd.DataFrame:
    """Load the Kaggle clickstream CSV with only the required columns."""
    print("[ETL 1/3] Loading raw clickstream data...")

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"\n  ❌ File not found: '{path}'\n"
            "  Please download '2019-Nov.csv' from Kaggle and place it in data/raw/\n"
            "  Link: https://www.kaggle.com/datasets/mkechinov/"
            "ecommerce-behavior-data-from-multi-category-store"
        )

    REQUIRED_COLS = [
        "event_time", "event_type", "product_id",
        "category_code", "brand", "price",
        "user_id", "user_session"
    ]

    df = pd.read_csv(path, usecols=REQUIRED_COLS, parse_dates=["event_time"])
    print(f"         Loaded {len(df):,} raw events")
    return df


# ── Step 2: Clean Raw Data ────────────────────────────────────────────────────
def clean_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Validate, clean, and enrich the raw event DataFrame."""
    print("[ETL 2/3] Cleaning raw data...")

    before = len(df)

    # Drop rows missing critical identifiers
    df.dropna(subset=["user_id", "user_session", "event_type"], inplace=True)

    # Fix price column — coerce non-numeric to NaN, then fill with 0
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
    df["price"] = df["price"].clip(lower=0)   # No negative prices

    # Fill categorical nulls
    df["brand"]         = df["brand"].fillna("unknown").str.lower().str.strip()
    df["category_code"] = df["category_code"].fillna("unknown").str.lower()

    # Extract top-level category  ("electronics.smartphone" → "electronics")
    df["category_top"] = df["category_code"].apply(
        lambda x: x.split(".")[0] if isinstance(x, str) and "." in x else x
    )

    # Time-based features
    df["hour"]       = df["event_time"].dt.hour
    df["weekday"]    = df["event_time"].dt.day_name()
    df["is_weekend"] = df["weekday"].isin(["Saturday", "Sunday"]).astype(int)
    df["week_num"]   = df["event_time"].dt.isocalendar().week.astype(int)

    after = len(df)
    print(f"         Removed {before - after:,} invalid rows | "
          f"{after:,} events remaining")
    return df


# ── Step 3: Aggregate to Session Level ────────────────────────────────────────
def build_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse event-level rows into one row per user_session.
    This is the correct foundation for A/B testing — we compare sessions,
    not individual events.
    """
    print("[ETL 3/3] Aggregating events → session level...")

    # Event-type boolean columns (1 if that event occurred in this row)
    df["is_view"]     = (df["event_type"] == "view").astype(int)
    df["is_cart"]     = (df["event_type"] == "cart").astype(int)
    df["is_purchase"] = (df["event_type"] == "purchase").astype(int)
    df["is_remove"]   = (df["event_type"] == "remove_from_cart").astype(int)
    df["revenue"]     = df["price"] * df["is_purchase"]

    # Aggregate: one row per session
    sessions = (
        df.groupby(["user_session", "user_id"])
        .agg(
            views         = ("is_view",      "sum"),
            carts         = ("is_cart",      "sum"),
            removes       = ("is_remove",    "sum"),
            purchases     = ("is_purchase",  "sum"),
            gross_revenue = ("revenue",      "sum"),
            max_price     = ("price",        "max"),   # Most expensive item browsed
            category_top  = ("category_top", "first"),
            brand         = ("brand",        "first"),
            hour          = ("hour",         "first"),
            is_weekend    = ("is_weekend",   "first"),
            week_num      = ("week_num",     "first"),
            session_start = ("event_time",   "min"),
        )
        .reset_index()
    )

    # ── Derived Features ──────────────────────────────────────────────────────
    sessions["converted"]    = (sessions["purchases"] > 0).astype(int)
    sessions["cart_abandon"] = (
        (sessions["carts"] > 0) & (sessions["purchases"] == 0)
    ).astype(int)

    # Price bucket (realistic business segmentation)
    sessions["price_bucket"] = pd.cut(
        sessions["max_price"],
        bins=PRICE_BINS, labels=PRICE_LABELS
    ).astype(str)

    # New vs Returning user
    session_counts = (
        df.groupby("user_id")["user_session"]
        .nunique()
        .reset_index()
        .rename(columns={"user_session": "total_sessions"})
    )
    sessions = sessions.merge(session_counts, on="user_id", how="left")
    sessions["is_new_user"] = (sessions["total_sessions"] == 1).astype(int)
    sessions["user_type"]   = np.where(sessions["is_new_user"] == 1, "New", "Returning")

    # ── Summary ───────────────────────────────────────────────────────────────
    cr = sessions["converted"].mean() * 100
    print(f"         Sessions built      : {len(sessions):,}")
    print(f"         Unique users        : {sessions['user_id'].nunique():,}")
    print(f"         Baseline conv. rate : {cr:.2f}%")

    return sessions


# ── Public API ────────────────────────────────────────────────────────────────
def run(save: bool = True) -> pd.DataFrame:
    """Full ETL pipeline. Returns clean session DataFrame."""
    raw      = load_raw()
    cleaned  = clean_raw(raw)
    sessions = build_sessions(cleaned)

    if save:
        os.makedirs(os.path.dirname(PROCESSED_DATA_PATH), exist_ok=True)
        sessions.to_csv(PROCESSED_DATA_PATH, index=False)
        print(f"\n  ✅ Saved → {PROCESSED_DATA_PATH}\n")

    return sessions


if __name__ == "__main__":
    run()
