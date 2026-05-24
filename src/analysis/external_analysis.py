"""
Portugal Data Intelligence - External Accounts Analysis
========================================================
Analysis of trade balance, current account, REER, and export dynamics.
"""

import sqlite3
from typing import Optional

import pandas as pd

from config.settings import CRISIS_PERIODS, DATABASE_PATH
from src.utils.db import get_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)


def analyse_external_accounts(conn: sqlite3.Connection) -> dict:
    """Analyse external competitiveness and current account dynamics."""
    try:
        df = pd.read_sql(
            """
            SELECT e.*, d.year, d.quarter
            FROM fact_external_accounts e
            JOIN dim_date d ON e.date_key = d.date_key
            ORDER BY d.year, d.quarter
            """,
            conn,
        )
    except Exception as exc:
        logger.warning(f"Could not load external accounts data: {exc}")
        return {"error": str(exc)}

    if df.empty:
        return {"error": "No external accounts data available"}

    result: dict = {"n_observations": len(df)}

    # Current account
    if "current_account_pct_gdp" in df.columns:
        ca = df["current_account_pct_gdp"].dropna()
        if not ca.empty:
            result["current_account"] = {
                "latest": round(float(ca.iloc[-1]), 2),
                "avg": round(float(ca.mean()), 2),
                "min": round(float(ca.min()), 2),
                "max": round(float(ca.max()), 2),
                "years_in_surplus": int((ca > 0).sum()),
            }

    # Trade balance
    if "trade_balance_pct_gdp" in df.columns:
        tb = df["trade_balance_pct_gdp"].dropna()
        if not tb.empty:
            result["trade_balance"] = {
                "latest": round(float(tb.iloc[-1]), 2),
                "avg": round(float(tb.mean()), 2),
                "improvement_since_2010": (
                    round(float(tb.iloc[-1] - tb.iloc[0]), 2) if len(tb) > 1 else None
                ),
            }

    # REER — competitiveness
    if "reer_index" in df.columns:
        reer = df["reer_index"].dropna()
        if not reer.empty:
            result["reer"] = {
                "latest": round(float(reer.iloc[-1]), 1),
                "avg": round(float(reer.mean()), 1),
                "min": round(float(reer.min()), 1),
                "max": round(float(reer.max()), 1),
            }

    # Export growth
    if "export_growth_yoy" in df.columns:
        exp = df["export_growth_yoy"].dropna()
        if not exp.empty:
            result["export_growth"] = {
                "latest_yoy": round(float(exp.iloc[-1]), 2),
                "avg_yoy": round(float(exp.mean()), 2),
            }

    # Crisis period behaviour
    if "year" in df.columns and "current_account_pct_gdp" in df.columns:
        notable = []
        for label, period in CRISIS_PERIODS.items():
            start, end = period["years"]
            subset = df.loc[
                (df["year"] >= start) & (df["year"] <= end), "current_account_pct_gdp"
            ].dropna()
            if not subset.empty:
                notable.append(
                    {
                        "period": label,
                        "years": f"{start}-{end}",
                        "avg_current_account_pct_gdp": round(float(subset.mean()), 2),
                    }
                )
        result["notable_periods"] = notable

    return result


def run_external_analysis(db_path: Optional[str] = None) -> dict:
    """Run external accounts analysis and return results."""
    db_path = db_path or str(DATABASE_PATH)
    with get_connection(db_path) as conn:
        return analyse_external_accounts(conn)
