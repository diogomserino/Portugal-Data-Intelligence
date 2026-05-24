"""
Portugal Data Intelligence - Inequality and Income Analysis
===========================================================
Analysis of income inequality, poverty risk, and living standards
using EU-SILC survey data from Eurostat.
"""

import sqlite3
from typing import Optional

import pandas as pd

from config.settings import DATABASE_PATH
from src.utils.db import get_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)


def analyse_inequality(conn: sqlite3.Connection) -> dict:
    """Analyse Gini coefficient, income quintile ratio, and poverty risk."""
    try:
        df = pd.read_sql(
            """
            SELECT i.*, d.year
            FROM fact_inequality i
            JOIN dim_date d ON i.date_key = d.date_key
            ORDER BY d.year
            """,
            conn,
        )
    except Exception as exc:
        logger.warning(f"Could not load inequality data: {exc}")
        return {"error": str(exc)}

    if df.empty:
        return {"error": "No inequality data available"}

    result: dict = {"n_observations": len(df)}

    # Gini coefficient
    if "gini_index" in df.columns:
        gini = df["gini_index"].dropna()
        if len(gini) >= 2:
            result["gini"] = {
                "latest": round(float(gini.iloc[-1]), 1),
                "avg": round(float(gini.mean()), 1),
                "min": round(float(gini.min()), 1),
                "max": round(float(gini.max()), 1),
                "trend": "improving" if gini.iloc[-1] < gini.iloc[0] else "worsening",
            }

    # S80/S20 income quintile ratio
    if "s80_s20_ratio" in df.columns:
        ratio = df["s80_s20_ratio"].dropna()
        if not ratio.empty:
            result["income_quintile_ratio"] = {
                "latest": round(float(ratio.iloc[-1]), 1),
                "avg": round(float(ratio.mean()), 1),
                "min": round(float(ratio.min()), 1),
                "max": round(float(ratio.max()), 1),
            }

    # At-risk-of-poverty rate
    if "poverty_risk_rate" in df.columns:
        poverty = df["poverty_risk_rate"].dropna()
        if len(poverty) >= 2:
            result["poverty_risk"] = {
                "latest": round(float(poverty.iloc[-1]), 1),
                "avg": round(float(poverty.mean()), 1),
                "peak": round(float(poverty.max()), 1),
                "peak_year": (
                    int(df.loc[df["poverty_risk_rate"].idxmax(), "year"])
                    if "year" in df.columns
                    else None
                ),
                "change_since_2010": round(float(poverty.iloc[-1] - poverty.iloc[0]), 1),
            }

    # Median income index relative to EU27
    if "median_income_index" in df.columns:
        income = df["median_income_index"].dropna()
        if len(income) >= 2:
            result["median_income"] = {
                "latest_index_eu27": round(float(income.iloc[-1]), 1),
                "change_since_2010": round(float(income.iloc[-1] - income.iloc[0]), 1),
            }

    return result


def run_inequality_analysis(db_path: Optional[str] = None) -> dict:
    """Run inequality and income analysis and return results."""
    db_path = db_path or str(DATABASE_PATH)
    with get_connection(db_path) as conn:
        return analyse_inequality(conn)
