"""
Portugal Data Intelligence - Statistical Analysis Module
=========================================================
Comprehensive statistical analysis for each macroeconomic data pillar.
Calculates descriptive statistics, identifies trends, and flags notable periods.
"""

import sqlite3
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from config.settings import CRISIS_PERIODS as _CRISIS_CFG
from config.settings import DATA_PILLARS, DATABASE_PATH, END_YEAR, START_YEAR
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

# Convert from config format {"key": {"years": (s,e), "label": "..."}} to simple tuples
CRISIS_PERIODS = {k: v["years"] for k, v in _CRISIS_CFG.items()}


def _descriptive_stats(series: pd.Series) -> dict:
    """Return a dictionary of descriptive statistics for a numeric series."""
    return {
        "count": int(series.count()),
        "mean": round(float(series.mean()), 4) if series.count() > 0 else None,
        "median": round(float(series.median()), 4) if series.count() > 0 else None,
        "std": round(float(series.std()), 4) if series.count() > 1 else None,
        "min": round(float(series.min()), 4) if series.count() > 0 else None,
        "max": round(float(series.max()), 4) if series.count() > 0 else None,
        "skewness": round(float(series.skew()), 4) if series.count() > 2 else None,
    }


def _classify_trend(series: pd.Series) -> str:
    """Classify an overall trend as increasing, decreasing, or stable."""
    if series.count() < 4:
        return "insufficient_data"
    half = len(series) // 2
    first_half_mean = series.iloc[:half].mean()
    second_half_mean = series.iloc[half:].mean()
    pct_change = (
        (second_half_mean - first_half_mean) / abs(first_half_mean) * 100
        if first_half_mean != 0
        else 0
    )
    if pct_change > 5:
        return "increasing"
    elif pct_change < -5:
        return "decreasing"
    return "stable"


def _flag_notable_periods(df: pd.DataFrame, year_col: str, value_col: str) -> list:
    """Identify notable periods (crisis, COVID, etc.) and summarise behaviour."""
    findings = []
    for label, (start, end) in CRISIS_PERIODS.items():
        mask = (df[year_col] >= start) & (df[year_col] <= end)
        subset = df.loc[mask, value_col].dropna()
        if subset.empty:
            continue
        findings.append(
            {
                "period": label,
                "years": f"{start}-{end}",
                "mean": round(float(subset.mean()), 4),
                "min": round(float(subset.min()), 4),
                "max": round(float(subset.max()), 4),
            }
        )
    return findings


# ---------------------------------------------------------------------------
# Pillar analysis functions
# ---------------------------------------------------------------------------


def analyse_gdp(conn: sqlite3.Connection) -> dict:
    """
    Annual GDP summary, growth rates, and period comparisons.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.

    Returns
    -------
    dict
        Keys: 'summary', 'statistics', 'notable_findings'.
    """
    logger.info("Analysing GDP pillar...")
    try:
        df = pd.read_sql(
            """
            SELECT d.year, d.quarter, g.*
            FROM fact_gdp g
            JOIN dim_date d ON g.date_key = d.date_key
            ORDER BY d.year, d.quarter
            """,
            conn,
        )
    except Exception as exc:
        logger.error(f"Failed to query fact_gdp: {exc}")
        return {"summary": "Data unavailable", "statistics": {}, "notable_findings": []}

    if df.empty:
        logger.warning("fact_gdp returned no rows.")
        return {"summary": "No GDP data found", "statistics": {}, "notable_findings": []}

    # Identify the main value column
    value_col = None
    for candidate in ["gdp_nominal", "nominal_gdp", "gdp_real", "real_gdp", "value", "gdp"]:
        if candidate in df.columns:
            value_col = candidate
            break
    if value_col is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [
            c for c in numeric_cols if c not in ("date_key", "year", "quarter", "source_key")
        ]
        value_col = numeric_cols[0] if numeric_cols else None

    if value_col is None:
        logger.warning("No suitable numeric column found in fact_gdp.")
        return {
            "summary": "No numeric GDP column detected",
            "statistics": {},
            "notable_findings": [],
        }

    # Annual aggregation
    annual = df.groupby("year")[value_col].mean().reset_index()
    annual["growth_rate"] = annual[value_col].pct_change() * 100

    stats = {
        "level": _descriptive_stats(annual[value_col]),
        "growth_rate": _descriptive_stats(annual["growth_rate"].dropna()),
    }

    trend = _classify_trend(annual[value_col])
    notable = _flag_notable_periods(annual, "year", value_col)

    summary = (
        f"GDP analysis covers {int(annual['year'].min())}-{int(annual['year'].max())}. "
        f"Overall trend is {trend}. "
        f"Average annual growth rate: {stats['growth_rate']['mean']}%."
    )

    logger.info("GDP analysis complete.")
    return {"summary": summary, "statistics": stats, "notable_findings": notable}


def analyse_unemployment(conn: sqlite3.Connection) -> dict:
    """
    Monthly unemployment trends, youth gap, and rolling averages.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.

    Returns
    -------
    dict
        Keys: 'summary', 'statistics', 'notable_findings'.
    """
    logger.info("Analysing unemployment pillar...")
    try:
        df = pd.read_sql(
            """
            SELECT d.year, d.month, u.*
            FROM fact_unemployment u
            JOIN dim_date d ON u.date_key = d.date_key
            ORDER BY d.year, d.month
            """,
            conn,
        )
    except Exception as exc:
        logger.error(f"Failed to query fact_unemployment: {exc}")
        return {"summary": "Data unavailable", "statistics": {}, "notable_findings": []}

    if df.empty:
        logger.warning("fact_unemployment returned no rows.")
        return {"summary": "No unemployment data found", "statistics": {}, "notable_findings": []}

    # Identify main rate columns
    total_col = None
    youth_col = None
    for c in df.columns:
        cl = c.lower()
        if "youth" in cl:
            youth_col = c
        elif ("rate" in cl or "unemployment" in cl) and "youth" not in cl:
            if total_col is None:
                total_col = c

    if total_col is None:
        numeric_cols = [
            c
            for c in df.select_dtypes(include=[np.number]).columns
            if c not in ("date_key", "year", "month", "quarter", "source_key")
        ]
        total_col = numeric_cols[0] if numeric_cols else None

    if total_col is None:
        return {
            "summary": "No numeric unemployment column detected",
            "statistics": {},
            "notable_findings": [],
        }

    # Rolling average (12-month)
    df["rolling_12m"] = df[total_col].rolling(window=12, min_periods=6).mean()

    # Annual summary
    annual = df.groupby("year")[total_col].mean().reset_index()

    stats = {
        "monthly": _descriptive_stats(df[total_col]),
        "annual_average": _descriptive_stats(annual[total_col]),
    }

    if youth_col is not None:
        stats["youth_rate"] = _descriptive_stats(df[youth_col])
        gap = df[youth_col] - df[total_col]
        stats["youth_gap"] = _descriptive_stats(gap.dropna())

    trend = _classify_trend(annual[total_col])
    notable = _flag_notable_periods(annual, "year", total_col)

    peak = annual.loc[annual[total_col].idxmax()]
    summary = (
        f"Unemployment analysis covers {int(annual['year'].min())}-{int(annual['year'].max())}. "
        f"Trend is {trend}. Peak annual average: {round(float(peak[total_col]), 1)}% in {int(peak['year'])}."
    )

    logger.info("Unemployment analysis complete.")
    return {"summary": summary, "statistics": stats, "notable_findings": notable}


def analyse_credit(conn: sqlite3.Connection) -> dict:
    """
    Credit evolution, NPL trends, and portfolio composition.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.

    Returns
    -------
    dict
        Keys: 'summary', 'statistics', 'notable_findings'.
    """
    logger.info("Analysing credit pillar...")
    try:
        df = pd.read_sql(
            """
            SELECT d.year, d.month, c.*
            FROM fact_credit c
            JOIN dim_date d ON c.date_key = d.date_key
            ORDER BY d.year, d.month
            """,
            conn,
        )
    except Exception as exc:
        logger.error(f"Failed to query fact_credit: {exc}")
        return {"summary": "Data unavailable", "statistics": {}, "notable_findings": []}

    if df.empty:
        logger.warning("fact_credit returned no rows.")
        return {"summary": "No credit data found", "statistics": {}, "notable_findings": []}

    numeric_cols = [
        c
        for c in df.select_dtypes(include=[np.number]).columns
        if c not in ("date_key", "year", "month", "quarter", "source_key")
    ]

    # Identify key columns heuristically
    total_col = None
    npl_col = None
    for c in numeric_cols:
        cl = c.lower()
        if "npl" in cl or "non_performing" in cl or "nonperforming" in cl:
            npl_col = c
        elif "total" in cl or "credit" in cl:
            if total_col is None:
                total_col = c

    if total_col is None and numeric_cols:
        total_col = numeric_cols[0]

    if total_col is None:
        return {
            "summary": "No numeric credit column detected",
            "statistics": {},
            "notable_findings": [],
        }

    annual = df.groupby("year")[total_col].mean().reset_index()
    annual["yoy_change"] = annual[total_col].pct_change() * 100

    stats = {
        "total_credit": _descriptive_stats(df[total_col]),
        "annual_growth": _descriptive_stats(annual["yoy_change"].dropna()),
    }

    if npl_col is not None:
        stats["npl"] = _descriptive_stats(df[npl_col])

    # Portfolio composition: summarise all available numeric columns
    composition = {}
    for c in numeric_cols:
        if c != total_col:
            composition[c] = _descriptive_stats(df[c])
    if composition:
        stats["portfolio_components"] = composition

    trend = _classify_trend(annual[total_col])
    notable = _flag_notable_periods(annual, "year", total_col)

    summary = (
        f"Credit analysis covers {int(annual['year'].min())}-{int(annual['year'].max())}. "
        f"Overall credit trend is {trend}."
    )

    logger.info("Credit analysis complete.")
    return {"summary": summary, "statistics": stats, "notable_findings": notable}


def analyse_interest_rates(conn: sqlite3.Connection) -> dict:
    """
    Rate environment, sovereign spread, and term structure analysis.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.

    Returns
    -------
    dict
        Keys: 'summary', 'statistics', 'notable_findings'.
    """
    logger.info("Analysing interest rates pillar...")
    try:
        df = pd.read_sql(
            """
            SELECT d.year, d.month, ir.*
            FROM fact_interest_rates ir
            JOIN dim_date d ON ir.date_key = d.date_key
            ORDER BY d.year, d.month
            """,
            conn,
        )
    except Exception as exc:
        logger.error(f"Failed to query fact_interest_rates: {exc}")
        return {"summary": "Data unavailable", "statistics": {}, "notable_findings": []}

    if df.empty:
        logger.warning("fact_interest_rates returned no rows.")
        return {"summary": "No interest rate data found", "statistics": {}, "notable_findings": []}

    numeric_cols = [
        c
        for c in df.select_dtypes(include=[np.number]).columns
        if c not in ("date_key", "year", "month", "quarter", "source_key")
    ]

    # Identify key columns
    ecb_col = None
    sovereign_col = None
    euribor_col = None
    for c in numeric_cols:
        cl = c.lower()
        if "ecb" in cl or "refi" in cl or "main_refinancing" in cl or "key_rate" in cl:
            ecb_col = c
        elif "sovereign" in cl or "bond" in cl or "yield" in cl or "10y" in cl:
            sovereign_col = c
        elif "euribor" in cl:
            euribor_col = c

    stats = {}
    for c in numeric_cols:
        stats[c] = _descriptive_stats(df[c])

    # Sovereign spread over ECB rate
    if ecb_col and sovereign_col:
        df["sovereign_spread"] = df[sovereign_col] - df[ecb_col]
        stats["sovereign_spread"] = _descriptive_stats(df["sovereign_spread"].dropna())

    # Term structure proxy: sovereign vs euribor
    if sovereign_col and euribor_col:
        df["term_spread"] = df[sovereign_col] - df[euribor_col]
        stats["term_spread"] = _descriptive_stats(df["term_spread"].dropna())

    annual = (
        df.groupby("year")[numeric_cols[0]].mean().reset_index() if numeric_cols else pd.DataFrame()
    )
    trend = _classify_trend(annual[numeric_cols[0]]) if not annual.empty else "unknown"
    notable = _flag_notable_periods(annual, "year", numeric_cols[0]) if not annual.empty else []

    summary = (
        f"Interest rates analysis covers {len(numeric_cols)} rate series. "
        f"Primary rate trend is {trend}."
    )

    logger.info("Interest rates analysis complete.")
    return {"summary": summary, "statistics": stats, "notable_findings": notable}


def analyse_inflation(conn: sqlite3.Connection) -> dict:
    """
    Inflation regimes, core vs headline, and real rate estimation.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.

    Returns
    -------
    dict
        Keys: 'summary', 'statistics', 'notable_findings'.
    """
    logger.info("Analysing inflation pillar...")
    try:
        df = pd.read_sql(
            """
            SELECT d.year, d.month, inf.*
            FROM fact_inflation inf
            JOIN dim_date d ON inf.date_key = d.date_key
            ORDER BY d.year, d.month
            """,
            conn,
        )
    except Exception as exc:
        logger.error(f"Failed to query fact_inflation: {exc}")
        return {"summary": "Data unavailable", "statistics": {}, "notable_findings": []}

    if df.empty:
        logger.warning("fact_inflation returned no rows.")
        return {"summary": "No inflation data found", "statistics": {}, "notable_findings": []}

    numeric_cols = [
        c
        for c in df.select_dtypes(include=[np.number]).columns
        if c not in ("date_key", "year", "month", "quarter", "source_key")
    ]

    headline_col = None
    core_col = None
    for c in numeric_cols:
        cl = c.lower()
        if "core" in cl:
            core_col = c
        elif "hicp" in cl or "cpi" in cl or "inflation" in cl or "headline" in cl:
            if headline_col is None:
                headline_col = c

    if headline_col is None and numeric_cols:
        headline_col = numeric_cols[0]

    if headline_col is None:
        return {
            "summary": "No numeric inflation column detected",
            "statistics": {},
            "notable_findings": [],
        }

    stats = {"headline": _descriptive_stats(df[headline_col])}

    if core_col:
        stats["core"] = _descriptive_stats(df[core_col])
        df["core_headline_gap"] = df[headline_col] - df[core_col]
        stats["core_headline_gap"] = _descriptive_stats(df["core_headline_gap"].dropna())

    # Inflation regimes
    regimes = []
    if df[headline_col].count() > 0:
        low = df[headline_col] < 1.0
        moderate = (df[headline_col] >= 1.0) & (df[headline_col] <= 3.0)
        high = df[headline_col] > 3.0
        regimes = [
            {"regime": "low (<1%)", "months": int(low.sum())},
            {"regime": "moderate (1-3%)", "months": int(moderate.sum())},
            {"regime": "high (>3%)", "months": int(high.sum())},
        ]
    stats["regimes"] = regimes  # type: ignore[assignment]

    # Real rate estimation (using interest rate data if available)
    try:
        ir_df = pd.read_sql(
            "SELECT d.year, d.month, ir.* FROM fact_interest_rates ir "
            "JOIN dim_date d ON ir.date_key = d.date_key ORDER BY d.year, d.month",
            conn,
        )
        ir_numeric = [
            c
            for c in ir_df.select_dtypes(include=[np.number]).columns
            if c not in ("date_key", "year", "month", "quarter", "source_key")
        ]
        if ir_numeric:
            merged = df.merge(
                ir_df[["year", "month"] + ir_numeric[:1]], on=["year", "month"], how="inner"
            )
            if not merged.empty:
                merged["real_rate"] = merged[ir_numeric[0]] - merged[headline_col]
                stats["real_rate"] = _descriptive_stats(merged["real_rate"].dropna())
    except Exception:
        pass  # Real rate estimation is optional

    annual = df.groupby("year")[headline_col].mean().reset_index()
    trend = _classify_trend(annual[headline_col])
    notable = _flag_notable_periods(annual, "year", headline_col)

    summary = (
        f"Inflation analysis covers {int(annual['year'].min())}-{int(annual['year'].max())}. "
        f"Trend is {trend}. Mean headline rate: {stats['headline']['mean']}%."
    )

    logger.info("Inflation analysis complete.")
    return {"summary": summary, "statistics": stats, "notable_findings": notable}


def analyse_public_debt(conn: sqlite3.Connection) -> dict:
    """
    Debt sustainability, fiscal balance, and composition analysis.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.

    Returns
    -------
    dict
        Keys: 'summary', 'statistics', 'notable_findings'.
    """
    logger.info("Analysing public debt pillar...")
    try:
        df = pd.read_sql(
            """
            SELECT d.year, d.quarter, pd.*
            FROM fact_public_debt pd
            JOIN dim_date d ON pd.date_key = d.date_key
            ORDER BY d.year, d.quarter
            """,
            conn,
        )
    except Exception as exc:
        logger.error(f"Failed to query fact_public_debt: {exc}")
        return {"summary": "Data unavailable", "statistics": {}, "notable_findings": []}

    if df.empty:
        logger.warning("fact_public_debt returned no rows.")
        return {"summary": "No public debt data found", "statistics": {}, "notable_findings": []}

    numeric_cols = [
        c
        for c in df.select_dtypes(include=[np.number]).columns
        if c not in ("date_key", "year", "quarter", "month", "source_key")
    ]

    # Identify key columns
    debt_gdp_col = None
    debt_abs_col = None
    fiscal_col = None
    for c in numeric_cols:
        cl = c.lower()
        if "ratio" in cl or "gdp" in cl or "percent" in cl:
            debt_gdp_col = c
        elif "balance" in cl or "deficit" in cl or "fiscal" in cl:
            fiscal_col = c
        elif "debt" in cl or "total" in cl:
            if debt_abs_col is None:
                debt_abs_col = c

    primary_col = debt_gdp_col or debt_abs_col or (numeric_cols[0] if numeric_cols else None)

    if primary_col is None:
        return {
            "summary": "No numeric public debt column detected",
            "statistics": {},
            "notable_findings": [],
        }

    stats = {}
    for c in numeric_cols:
        stats[c] = _descriptive_stats(df[c])

    # Sustainability indicator: check if debt-to-GDP is declining
    annual = df.groupby("year")[primary_col].mean().reset_index()
    trend = _classify_trend(annual[primary_col])

    if fiscal_col:
        stats["fiscal_balance"] = _descriptive_stats(df[fiscal_col])

    # Composition: summarise all non-primary numeric columns
    composition = {}
    for c in numeric_cols:
        if c != primary_col:
            composition[c] = _descriptive_stats(df[c])
    if composition:
        stats["composition"] = composition

    notable = _flag_notable_periods(annual, "year", primary_col)

    latest_year = annual["year"].max()
    latest_val = annual.loc[annual["year"] == latest_year, primary_col].values
    latest_str = (
        f" Latest value ({int(latest_year)}): {round(float(latest_val[0]), 1)}."
        if len(latest_val) > 0
        else ""
    )

    summary = (
        f"Public debt analysis covers {int(annual['year'].min())}-{int(annual['year'].max())}. "
        f"Trend is {trend}.{latest_str}"
    )

    logger.info("Public debt analysis complete.")
    return {"summary": summary, "statistics": stats, "notable_findings": notable}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

PILLAR_FUNCTIONS = {
    "gdp": analyse_gdp,
    "unemployment": analyse_unemployment,
    "credit": analyse_credit,
    "interest_rates": analyse_interest_rates,
    "inflation": analyse_inflation,
    "public_debt": analyse_public_debt,
}


def run_all_analyses(db_path: Optional[str] = None) -> dict:
    """
    Run statistical analysis for every data pillar and return combined results.

    Parameters
    ----------
    db_path : str, optional
        Path to the SQLite database. Defaults to DATABASE_PATH from settings.

    Returns
    -------
    dict
        Dictionary keyed by pillar name, each containing analysis results.
    """
    db_path = db_path or str(DATABASE_PATH)
    log_section(logger, "STATISTICAL ANALYSIS - ALL PILLARS")
    results = {}

    try:
        conn = sqlite3.connect(db_path)
        logger.info(f"Connected to database: {db_path}")

        for pillar_key, analyse_fn in PILLAR_FUNCTIONS.items():
            try:
                results[pillar_key] = analyse_fn(conn)
                logger.info(f"Completed analysis for: {pillar_key}")
            except Exception as exc:
                logger.error(f"Error analysing {pillar_key}: {exc}")
                results[pillar_key] = {
                    "summary": f"Analysis failed: {exc}",
                    "statistics": {},
                    "notable_findings": [],
                }

        conn.close()
        logger.info("All statistical analyses complete.")
    except Exception as exc:
        logger.error(f"Database connection failed: {exc}")

    return results


def run_single_analysis(pillar: str, db_path: Optional[str] = None) -> dict:
    """
    Run statistical analysis for a single pillar.

    Parameters
    ----------
    pillar : str
        Pillar identifier (e.g. 'gdp', 'unemployment').
    db_path : str, optional
        Path to the SQLite database.

    Returns
    -------
    dict
        Analysis results for the specified pillar.
    """
    db_path = db_path or str(DATABASE_PATH)
    analyse_fn = PILLAR_FUNCTIONS.get(pillar)
    if analyse_fn is None:
        raise ValueError(
            f"Unknown pillar: '{pillar}'. Valid pillars: {list(PILLAR_FUNCTIONS.keys())}"
        )

    log_section(logger, f"STATISTICAL ANALYSIS - {pillar.upper()}")
    conn = sqlite3.connect(db_path)
    try:
        result = analyse_fn(conn)
    finally:
        conn.close()
    return result
