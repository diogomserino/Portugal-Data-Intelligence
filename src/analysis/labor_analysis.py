"""
Portugal Data Intelligence - Labour Market Structure Analysis
=============================================================
Analysis of employment by sector, real wages, and labour productivity.
"""

import sqlite3
from typing import Optional

import pandas as pd

from config.settings import DATABASE_PATH
from src.utils.db import get_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)


def analyse_labor_detail(conn: sqlite3.Connection) -> dict:
    """Analyse employment structure, wages, and productivity."""
    try:
        df = pd.read_sql(
            """
            SELECT l.*, d.year
            FROM fact_labor_detail l
            JOIN dim_date d ON l.date_key = d.date_key
            ORDER BY d.year
            """,
            conn,
        )
    except Exception as exc:
        logger.warning(f"Could not load labor detail data: {exc}")
        return {"error": str(exc)}

    if df.empty:
        return {"error": "No labour detail data available"}

    result: dict = {"n_observations": len(df)}

    # Employment structure (latest)
    sector_cols = [
        "employment_services_pct",
        "employment_industry_pct",
        "employment_agriculture_pct",
    ]
    structure = {}
    for col in sector_cols:
        if col in df.columns:
            series = df[col].dropna()
            if not series.empty:
                structure[col] = {
                    "latest": round(float(series.iloc[-1]), 1),
                    "change_since_2010": (
                        round(float(series.iloc[-1] - series.iloc[0]), 1)
                        if len(series) > 1
                        else None
                    ),
                }
    if structure:
        result["employment_structure"] = structure

    # Real wages
    if "real_wage_index" in df.columns:
        wages = df["real_wage_index"].dropna()
        if len(wages) >= 2:
            result["real_wages"] = {
                "latest_index": round(float(wages.iloc[-1]), 1),
                "total_change_pct": round(float((wages.iloc[-1] / wages.iloc[0] - 1) * 100), 1),
                "min": round(float(wages.min()), 1),
                "max": round(float(wages.max()), 1),
            }

    # Productivity
    if "labour_productivity_index" in df.columns:
        prod = df["labour_productivity_index"].dropna()
        if len(prod) >= 2:
            result["labour_productivity"] = {
                "latest_index": round(float(prod.iloc[-1]), 1),
                "total_change_pct": round(float((prod.iloc[-1] / prod.iloc[0] - 1) * 100), 1),
            }

    return result


def run_labor_analysis(db_path: Optional[str] = None) -> dict:
    """Run labour market structure analysis and return results."""
    db_path = db_path or str(DATABASE_PATH)
    with get_connection(db_path) as conn:
        return analyse_labor_detail(conn)
