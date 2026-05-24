"""
Portugal Data Intelligence - Fiscal Composition Analysis
=========================================================
Analysis of government expenditure by COFOG function,
revenue trends, and interest payment burden.
"""

import sqlite3
from typing import Optional

import pandas as pd

from config.settings import DATABASE_PATH
from src.utils.db import get_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)

_EXPENDITURE_COLS = [
    "health_expenditure_pct",
    "education_expenditure_pct",
    "social_protection_pct",
    "interest_payments_pct",
]


def analyse_fiscal(conn: sqlite3.Connection) -> dict:
    """Analyse fiscal revenue, expenditure composition, and interest burden."""
    try:
        df = pd.read_sql(
            """
            SELECT f.*, d.year
            FROM fact_fiscal f
            JOIN dim_date d ON f.date_key = d.date_key
            ORDER BY d.year
            """,
            conn,
        )
    except Exception as exc:
        logger.warning(f"Could not load fiscal data: {exc}")
        return {"error": str(exc)}

    if df.empty:
        return {"error": "No fiscal data available"}

    result: dict = {"n_observations": len(df)}

    # Revenue vs expenditure balance
    if "total_revenue_pct_gdp" in df.columns and "total_expenditure_pct_gdp" in df.columns:
        rev = df["total_revenue_pct_gdp"].dropna()
        exp = df["total_expenditure_pct_gdp"].dropna()
        if not rev.empty and not exp.empty:
            result["fiscal_balance"] = {
                "latest_revenue_pct_gdp": round(float(rev.iloc[-1]), 1),
                "latest_expenditure_pct_gdp": round(float(exp.iloc[-1]), 1),
                "latest_balance": round(float(rev.iloc[-1] - exp.iloc[-1]), 1),
                "avg_revenue": round(float(rev.mean()), 1),
                "avg_expenditure": round(float(exp.mean()), 1),
            }

    # Expenditure breakdown
    breakdown = {}
    for col in _EXPENDITURE_COLS:
        if col in df.columns:
            series = df[col].dropna()
            if not series.empty:
                breakdown[col] = {
                    "latest": round(float(series.iloc[-1]), 1),
                    "avg": round(float(series.mean()), 1),
                    "min": round(float(series.min()), 1),
                    "max": round(float(series.max()), 1),
                }
    if breakdown:
        result["expenditure_breakdown"] = breakdown

    # Interest burden — critical for debt sustainability
    if "interest_payments_pct" in df.columns:
        interest = df["interest_payments_pct"].dropna()
        if len(interest) >= 2:
            result["interest_burden"] = {
                "latest": round(float(interest.iloc[-1]), 2),
                "peak": round(float(interest.max()), 2),
                "peak_year": (
                    int(df.loc[df["interest_payments_pct"].idxmax(), "year"])
                    if "year" in df.columns
                    else None
                ),
                "reduction_from_peak": round(float(interest.max() - interest.iloc[-1]), 2),
            }

    return result


def run_fiscal_analysis(db_path: Optional[str] = None) -> dict:
    """Run fiscal composition analysis and return results."""
    db_path = db_path or str(DATABASE_PATH)
    with get_connection(db_path) as conn:
        return analyse_fiscal(conn)
