"""
Portugal Data Intelligence - Housing Market Analysis
=====================================================
Statistical analysis of house price dynamics, transaction volumes,
and mortgage lending trends.
"""

import sqlite3
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import CRISIS_PERIODS, DATABASE_PATH
from src.utils.db import get_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)


def analyse_housing(conn: sqlite3.Connection) -> dict:
    """Analyse house price trends, transactions, and affordability."""
    try:
        df = pd.read_sql(
            """
            SELECT h.*, d.year, d.quarter
            FROM fact_housing h
            JOIN dim_date d ON h.date_key = d.date_key
            ORDER BY d.year
            """,
            conn,
        )
    except Exception as exc:
        logger.warning(f"Could not load housing data: {exc}")
        return {"error": str(exc)}

    if df.empty:
        return {"error": "No housing data available"}

    result: dict = {"n_observations": len(df)}

    # House price index trend
    if "house_price_index" in df.columns:
        hpi = df["house_price_index"].dropna()
        if len(hpi) >= 2:
            result["house_price_index"] = {
                "latest": round(float(hpi.iloc[-1]), 1),
                "min": round(float(hpi.min()), 1),
                "max": round(float(hpi.max()), 1),
                "total_change_pct": round(float((hpi.iloc[-1] / hpi.iloc[0] - 1) * 100), 1),
            }

    # YoY price changes
    if "house_price_yoy_change" in df.columns:
        yoy = df["house_price_yoy_change"].dropna()
        if not yoy.empty:
            result["price_growth"] = {
                "latest_yoy": round(float(yoy.iloc[-1]), 2),
                "avg_yoy": round(float(yoy.mean()), 2),
                "peak_growth": round(float(yoy.max()), 2),
                "peak_year": (
                    int(df.loc[df["house_price_yoy_change"].idxmax(), "year"])
                    if "year" in df.columns
                    else None
                ),
            }

    # Transaction volume
    if "housing_transactions" in df.columns:
        tx = df["housing_transactions"].dropna()
        if not tx.empty:
            result["transactions"] = {
                "latest": int(tx.iloc[-1]),
                "avg": round(float(tx.mean()), 0),
                "min": int(tx.min()),
                "max": int(tx.max()),
            }

    # Average price per sqm
    if "avg_price_per_sqm" in df.columns:
        price_sqm = df["avg_price_per_sqm"].dropna()
        if not price_sqm.empty:
            result["avg_price_per_sqm"] = {
                "latest": round(float(price_sqm.iloc[-1]), 0),
                "min": round(float(price_sqm.min()), 0),
                "max": round(float(price_sqm.max()), 0),
            }

    # Crisis period behaviour
    if "year" in df.columns and "house_price_index" in df.columns:
        notable = []
        for label, period in CRISIS_PERIODS.items():
            start, end = period["years"]
            subset = df.loc[
                (df["year"] >= start) & (df["year"] <= end), "house_price_index"
            ].dropna()
            if not subset.empty:
                notable.append(
                    {
                        "period": label,
                        "years": f"{start}-{end}",
                        "avg_hpi": round(float(subset.mean()), 1),
                    }
                )
        result["notable_periods"] = notable

    return result


def run_housing_analysis(db_path: Optional[str] = None) -> dict:
    """Run housing analysis and return results."""
    db_path = db_path or str(DATABASE_PATH)
    with get_connection(db_path) as conn:
        return analyse_housing(conn)
