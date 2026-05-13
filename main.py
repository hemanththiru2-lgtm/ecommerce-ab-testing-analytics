"""
main.py — Single entry point for the full pipeline.

Run: python main.py

Flow:
  1. data_preprocessing.py  → raw events → sessions.csv
  2. experiment_engine.py   → A/B split + coupon injection → ab_results.csv
  3. segmentation.py        → segment KPIs → segment_results.csv + profit_impact.csv
  All outputs written to database/experiment.db for SQL and Power BI.
"""

import sys
import time

import pandas as pd

import src.data_preprocessing as etl
import src.experiment_engine  as exp
import src.segmentation       as seg
from config import PROCESSED_DATA_PATH


def main():
    start = time.time()

    print("=" * 60)
    print("  E-Commerce A/B Testing & Profit Guardrail Pipeline")
    print("=" * 60)

    # Stage 1: ETL
    print("\n── STAGE 1: ETL (Raw → Sessions) ──────────────────────────")
    sessions = etl.run(save=True)

    # Stage 2: Experiment
    print("\n── STAGE 2: EXPERIMENT ENGINE ─────────────────────────────")
    sessions, kpi_df = exp.run(sessions, save=True)

    # Stage 3: Segmentation
    print("\n── STAGE 3: SEGMENTATION ──────────────────────────────────")
    seg.run(sessions, save=True)

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  ✅ Pipeline complete in {elapsed:.1f}s")
    print(f"  Open database/experiment.db in DBeaver or Power BI.")
    print(f"  Run sql/analytics.sql to explore results.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
