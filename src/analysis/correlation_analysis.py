"""
Portugal Data Intelligence - Correlation Analysis Module
=========================================================
Cross-pillar correlation analysis including Phillips curve,
interest rate transmission, and debt-GDP dynamics.

Fixes applied (March 2026):
- Use monthly/quarterly data directly instead of annual averages
- Drop linearly dependent columns (e.g., total_credit = nfc + households)
- Compute correlations on growth rates for level variables (avoids spurious correlation)
- Require statistical significance (p < 0.05) for optimal lag selection
- Report sample sizes alongside all correlation results
- Flag near-perfect correlations (|r| > 0.95) as suspicious
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from config.settings import DATA_PILLARS, DATABASE_PATH
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _safe_pearsonr(x: pd.Series, y: pd.Series) -> Tuple[Optional[float], Optional[float], int]:
    """
    Compute Pearson correlation with p-value, handling missing data gracefully.

    Returns
    -------
    tuple
        (correlation_coefficient, p_value, sample_size) or (None, None, 0) if
        insufficient data.
    """
    combined = pd.DataFrame({"x": x, "y": y}).dropna()
    n = len(combined)
    if n < 3:
        return None, None, n
    r, p = sp_stats.pearsonr(combined["x"], combined["y"])
    return round(float(r), 4), round(float(p), 6), n


def _interpret_correlation(r: Optional[float], p: Optional[float], n: int = 0) -> str:
    """Return a human-readable interpretation of a correlation result."""
    if r is None:
        return "insufficient data"
    strength = "weak"
    if abs(r) >= 0.7:
        strength = "strong"
    elif abs(r) >= 0.4:
        strength = "moderate"

    direction = "positive" if r > 0 else "negative"
    significance = (
        "statistically significant"
        if p is not None and p < 0.05
        else "not statistically significant"
    )
    return f"{strength} {direction} correlation (r={r}, p={p}, n={n}), {significance}"


def _load_monthly_pillar(conn: sqlite3.Connection, table: str, prefix: str) -> pd.DataFrame:
    """
    Load a monthly fact table and return a DataFrame with date_key, year, month,
    and prefixed numeric columns.
    """
    try:
        df = pd.read_sql(
            f"SELECT d.date_key, d.year, d.month, t.* "
            f"FROM {table} t "
            f"JOIN dim_date d ON t.date_key = d.date_key "
            f"ORDER BY d.year, d.month",
            conn,
        )
    except Exception as exc:
        logger.warning(f"Could not load {table}: {exc}")
        return pd.DataFrame()

    if df.empty:
        return df

    # Remove duplicate date_key column from the join
    df = df.loc[:, ~df.columns.duplicated()]

    # Prefix numeric columns (except keys)
    exclude = {
        "date_key",
        "year",
        "month",
        "quarter",
        "source_key",
        "id",
        "created_at",
        "is_provisional",
    }
    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude]
    rename_map = {c: f"{prefix}_{c}" for c in numeric_cols}
    df = df.rename(columns=rename_map)
    keep_cols = ["date_key", "year", "month"] + list(rename_map.values())
    return df[keep_cols]


def _load_quarterly_pillar(conn: sqlite3.Connection, table: str, prefix: str) -> pd.DataFrame:
    """
    Load a quarterly fact table, returning date_key, year, quarter, and prefixed
    numeric columns.
    """
    try:
        df = pd.read_sql(
            f"SELECT d.date_key, d.year, d.quarter, t.* "
            f"FROM {table} t "
            f"JOIN dim_date d ON t.date_key = d.date_key "
            f"ORDER BY d.year, d.quarter",
            conn,
        )
    except Exception as exc:
        logger.warning(f"Could not load {table}: {exc}")
        return pd.DataFrame()

    if df.empty:
        return df

    # Remove duplicate date_key column from the join
    df = df.loc[:, ~df.columns.duplicated()]

    exclude = {
        "date_key",
        "year",
        "month",
        "quarter",
        "source_key",
        "id",
        "created_at",
        "is_provisional",
    }
    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude]
    rename_map = {c: f"{prefix}_{c}" for c in numeric_cols}
    df = df.rename(columns=rename_map)
    keep_cols = ["date_key", "year", "quarter"] + list(rename_map.values())
    return df[keep_cols]


def _drop_linear_combination_columns(df: pd.DataFrame, numeric_cols: List[str]) -> List[str]:
    """
    Detect and remove columns that are near-perfect linear combinations of
    other columns (e.g., total_credit ~ credit_nfc + credit_households).

    Returns the filtered list of column names to keep.
    """
    if len(numeric_cols) < 3:
        return numeric_cols

    to_drop = set()
    # Check each column: if it can be almost perfectly predicted by the others,
    # flag it for removal.  We use a simple heuristic: if any column named
    # '*total*' is almost exactly the sum of other columns from the same prefix,
    # drop it.
    for col in numeric_cols:
        if "total" not in col.lower():
            continue
        # Find sibling columns with the same prefix
        prefix = col.split("_")[0]
        siblings = [
            c
            for c in numeric_cols
            if c != col and c.startswith(prefix) and "total" not in c.lower()
        ]
        if len(siblings) < 2:
            continue
        # Check if col ~ sum(siblings)
        sub = df[[col] + siblings].dropna()
        if len(sub) < 5:
            continue
        sibling_sum = sub[siblings].sum(axis=1)
        r_val = sub[col].corr(sibling_sum)
        if r_val is not None and abs(r_val) > 0.999:
            logger.warning(
                f"Dropping '{col}' from correlation matrix: it is a near-perfect "
                f"linear combination of {siblings} (r={r_val:.6f})."
            )
            to_drop.add(col)

    return [c for c in numeric_cols if c not in to_drop]


# ---------------------------------------------------------------------------
# Core analysis functions
# ---------------------------------------------------------------------------


def build_correlation_matrix(db_path: Optional[str] = None) -> pd.DataFrame:
    """
    Build a monthly correlation matrix across all available monthly indicators.

    Drops columns that are linear combinations of others and flags any
    near-perfect correlations (|r| > 0.95) in the log.

    Returns
    -------
    pd.DataFrame
        Correlation matrix of monthly indicators.
    """
    db_path = db_path or str(DATABASE_PATH)
    logger.info("Building cross-pillar correlation matrix...")

    conn = sqlite3.connect(db_path)
    try:
        monthly_pillars = {
            "unemp": "fact_unemployment",
            "credit": "fact_credit",
            "ir": "fact_interest_rates",
            "infl": "fact_inflation",
        }

        merged = None
        for prefix, table in monthly_pillars.items():
            df = _load_monthly_pillar(conn, table, prefix)
            if df.empty:
                continue
            if merged is None:
                merged = df
            else:
                merged = merged.merge(df, on=["date_key", "year", "month"], how="inner")

        if merged is None or merged.empty:
            logger.warning("No monthly data available for correlation matrix.")
            return pd.DataFrame()

        numeric_cols = [c for c in merged.columns if c not in ("date_key", "year", "month")]

        # Drop linearly dependent columns
        numeric_cols = _drop_linear_combination_columns(merged, numeric_cols)

        # Stationarity check: warn about non-stationary series and use
        # first differences for those columns to avoid spurious correlations
        from src.analysis.significance_tests import test_stationarity

        stationary_cols = []
        diff_cols = []
        for col in numeric_cols:
            series = merged[col].dropna().values
            if len(series) >= 8:
                adf_result = test_stationarity(series)
                if not adf_result["is_stationary"]:
                    logger.warning(
                        f"Non-stationary series detected: {col} "
                        f"(ADF={adf_result['adf_statistic']}). "
                        f"Using first differences for correlation."
                    )
                    diff_col = f"{col}_diff"
                    merged[diff_col] = merged[col].diff()
                    diff_cols.append(diff_col)
                else:
                    stationary_cols.append(col)
            else:
                stationary_cols.append(col)

        corr_cols = stationary_cols + diff_cols
        corr_matrix = merged[corr_cols].corr()

        # Flag near-perfect correlations
        for i in range(len(corr_matrix)):
            for j in range(i + 1, len(corr_matrix)):
                r_val = corr_matrix.iloc[i, j]
                if abs(r_val) > 0.95:
                    col_a = corr_matrix.index[i]
                    col_b = corr_matrix.columns[j]
                    logger.warning(
                        f"Near-perfect correlation detected: {col_a} vs {col_b} "
                        f"(r={r_val:.4f}). Investigate for spurious relationship."
                    )

        logger.info(
            f"Correlation matrix built: {corr_matrix.shape[0]} x {corr_matrix.shape[1]} indicators."
        )
        return corr_matrix

    finally:
        conn.close()


def analyse_phillips_curve(db_path: Optional[str] = None) -> dict:
    """
    Analyse the Phillips curve relationship: unemployment vs inflation.

    Uses MONTHLY data for more data points and realistic correlations.
    Also computes sub-period correlations and reports sample sizes.

    Returns
    -------
    dict
        Keys: 'summary', 'correlation', 'monthly_data', 'periods'.
    """
    db_path = db_path or str(DATABASE_PATH)
    logger.info("Analysing Phillips curve (unemployment vs inflation)...")

    conn = sqlite3.connect(db_path)
    try:
        unemp = _load_monthly_pillar(conn, "fact_unemployment", "unemp")
        infl = _load_monthly_pillar(conn, "fact_inflation", "infl")
    finally:
        conn.close()

    if unemp.empty or infl.empty:
        return {
            "summary": "Insufficient data for Phillips curve analysis.",
            "correlation": {},
            "monthly_data": [],
            "periods": [],
        }

    # Merge on date_key directly for monthly-to-monthly alignment
    merged = unemp.merge(infl, on=["date_key", "year", "month"], how="inner")
    if merged.empty:
        return {
            "summary": "No overlapping monthly data for Phillips curve.",
            "correlation": {},
            "monthly_data": [],
            "periods": [],
        }

    unemp_cols = [c for c in merged.columns if c.startswith("unemp_")]
    infl_cols = [c for c in merged.columns if c.startswith("infl_")]

    # Use primary indicators: unemployment_rate and hicp (first available)
    u_col = unemp_cols[0]
    i_col = infl_cols[0]

    # Overall correlation on monthly data
    r, p, n = _safe_pearsonr(merged[u_col], merged[i_col])
    interpretation = _interpret_correlation(r, p, n)

    if r is not None and abs(r) > 0.95:
        logger.warning(
            f"Phillips curve overall r={r} is suspiciously high. "
            f"Check for data issues or confounders."
        )

    # Sub-period analysis
    periods = []
    period_ranges = [
        ("pre_crisis", 2010, 2011),
        ("troika", 2011, 2014),
        ("recovery", 2015, 2019),
        ("covid", 2020, 2021),
        ("post_covid", 2022, 2025),
    ]
    for label, start, end in period_ranges:
        subset = merged[(merged["year"] >= start) & (merged["year"] <= end)]
        if len(subset) >= 3:
            sub_r, sub_p, sub_n = _safe_pearsonr(subset[u_col], subset[i_col])
            periods.append(
                {
                    "period": label,
                    "years": f"{start}-{end}",
                    "correlation": sub_r,
                    "p_value": sub_p,
                    "sample_size": sub_n,
                    "interpretation": _interpret_correlation(sub_r, sub_p, sub_n),
                }
            )

    monthly_data = (
        merged[["date_key", "year", "month", u_col, i_col]].round(4).to_dict(orient="records")
    )

    summary = (
        f"Phillips curve analysis: overall {interpretation}. " f"Based on {n} monthly observations."
    )

    logger.info("Phillips curve analysis complete.")
    return {
        "summary": summary,
        "correlation": {"r": r, "p_value": p, "n": n, "interpretation": interpretation},
        "monthly_data": monthly_data,
        "periods": periods,
    }


def analyse_interest_rate_transmission(db_path: Optional[str] = None) -> dict:
    """
    Analyse ECB rate impact on credit and inflation with lag analysis.

    Uses monthly data. When finding optimal lag, requires p < 0.05.

    Returns
    -------
    dict
        Keys: 'summary', 'credit_transmission', 'inflation_transmission'.
    """
    db_path = db_path or str(DATABASE_PATH)
    logger.info("Analysing interest rate transmission mechanism...")

    conn = sqlite3.connect(db_path)
    try:
        ir = _load_monthly_pillar(conn, "fact_interest_rates", "ir")
        credit = _load_monthly_pillar(conn, "fact_credit", "credit")
        infl = _load_monthly_pillar(conn, "fact_inflation", "infl")
    finally:
        conn.close()

    if ir.empty:
        return {
            "summary": "No interest rate data available for transmission analysis.",
            "credit_transmission": {},
            "inflation_transmission": {},
        }

    # Create a date index for lag alignment using year*12 + month
    ir_cols = [c for c in ir.columns if c.startswith("ir_")]
    ir_col = ir_cols[0] if ir_cols else None

    if ir_col is None:
        return {
            "summary": "No numeric interest rate column found.",
            "credit_transmission": {},
            "inflation_transmission": {},
        }

    ir["date_idx"] = ir["year"] * 12 + ir["month"]
    lags = [0, 3, 6, 12]

    def _lag_analysis(target_df: pd.DataFrame, target_prefix: str) -> dict:
        """Test correlations at multiple lags on monthly data."""
        target_cols = [c for c in target_df.columns if c.startswith(target_prefix)]
        if not target_cols:
            return {"lags": [], "optimal_lag": None}

        target_col = target_cols[0]
        target_df = target_df.copy()
        target_df["date_idx"] = target_df["year"] * 12 + target_df["month"]

        lag_results = []
        for lag in lags:
            ir_shifted = ir[["date_idx", ir_col]].copy()
            ir_shifted["date_idx"] = ir_shifted["date_idx"] + lag
            lag_merged = target_df[["date_idx", target_col]].merge(
                ir_shifted, on="date_idx", how="inner"
            )
            r, p, n = _safe_pearsonr(lag_merged[ir_col], lag_merged[target_col])
            lag_results.append(
                {
                    "lag_months": lag,
                    "correlation": r,
                    "p_value": p,
                    "sample_size": n,
                    "interpretation": _interpret_correlation(r, p, n),
                }
            )

        # Find optimal lag: REQUIRE p < 0.05 for significance
        significant = [
            lr
            for lr in lag_results
            if lr["correlation"] is not None
            and lr["p_value"] is not None
            and float(lr["p_value"]) < 0.05
        ]
        if significant:
            optimal = max(significant, key=lambda x: abs(float(x["correlation"] or 0)))
        else:
            # No significant results -- report None as optimal
            optimal = None
            logger.info(
                f"No statistically significant lag found for {target_prefix}. "
                f"All lags had p >= 0.05."
            )

        return {
            "lags": lag_results,
            "optimal_lag": optimal["lag_months"] if optimal else None,
            "optimal_correlation": optimal["correlation"] if optimal else None,
            "optimal_p_value": optimal["p_value"] if optimal else None,
        }

    credit_result = (
        _lag_analysis(credit, "credit_") if not credit.empty else {"lags": [], "optimal_lag": None}
    )
    infl_result = (
        _lag_analysis(infl, "infl_") if not infl.empty else {"lags": [], "optimal_lag": None}
    )

    parts = []
    if credit_result.get("optimal_lag") is not None:
        parts.append(
            f"Credit responds optimally at {credit_result['optimal_lag']}-month lag "
            f"(r={credit_result['optimal_correlation']}, p={credit_result['optimal_p_value']})"
        )
    else:
        parts.append("Credit: no statistically significant lag relationship found")
    if infl_result.get("optimal_lag") is not None:
        parts.append(
            f"Inflation responds optimally at {infl_result['optimal_lag']}-month lag "
            f"(r={infl_result['optimal_correlation']}, p={infl_result['optimal_p_value']})"
        )
    else:
        parts.append("Inflation: no statistically significant lag relationship found")

    summary = "Interest rate transmission: " + "; ".join(parts) + "."

    logger.info("Interest rate transmission analysis complete.")
    return {
        "summary": summary,
        "credit_transmission": credit_result,
        "inflation_transmission": infl_result,
    }


def analyse_debt_gdp_dynamics(db_path: Optional[str] = None) -> dict:
    """
    Analyse the interaction between public debt and GDP growth.

    Uses QUARTERLY data merged on date_key. Computes correlation on
    quarter-over-quarter GROWTH RATES (not levels) to avoid spurious
    correlation from trending time series.

    Returns
    -------
    dict
        Keys: 'summary', 'correlation', 'quarterly_data', 'divergence_periods'.
    """
    db_path = db_path or str(DATABASE_PATH)
    logger.info("Analysing debt-GDP dynamics...")

    conn = sqlite3.connect(db_path)
    try:
        debt = _load_quarterly_pillar(conn, "fact_public_debt", "debt")
        gdp = _load_quarterly_pillar(conn, "fact_gdp", "gdp")
    finally:
        conn.close()

    if debt.empty or gdp.empty:
        return {
            "summary": "Insufficient data for debt-GDP dynamics analysis.",
            "correlation": {},
            "quarterly_data": [],
            "divergence_periods": [],
        }

    # Merge on date_key directly for proper quarterly alignment
    merged = debt.merge(gdp, on=["date_key", "year", "quarter"], how="inner")
    if merged.empty:
        return {
            "summary": "No overlapping quarterly data for debt-GDP analysis.",
            "correlation": {},
            "quarterly_data": [],
            "divergence_periods": [],
        }

    debt_cols = [c for c in merged.columns if c.startswith("debt_")]
    gdp_cols = [c for c in merged.columns if c.startswith("gdp_")]

    if not debt_cols or not gdp_cols:
        return {
            "summary": "No suitable numeric columns for debt-GDP analysis.",
            "correlation": {},
            "quarterly_data": [],
            "divergence_periods": [],
        }

    debt_col = debt_cols[0]
    gdp_col = gdp_cols[0]

    # Sort by date_key to ensure proper ordering for growth rate calculation
    merged = merged.sort_values("date_key").reset_index(drop=True)

    # Compute quarter-over-quarter growth rates to avoid spurious level correlation
    merged["debt_growth"] = merged[debt_col].pct_change()
    merged["gdp_growth"] = merged[gdp_col].pct_change()

    # Drop the first row (NaN from pct_change)
    growth_data = merged.dropna(subset=["debt_growth", "gdp_growth"])

    # Correlation on growth rates
    r, p, n = _safe_pearsonr(growth_data["debt_growth"], growth_data["gdp_growth"])
    interpretation = _interpret_correlation(r, p, n)

    if r is not None and abs(r) > 0.95:
        logger.warning(
            f"Debt-GDP growth correlation r={r} is suspiciously high. " f"Check for data issues."
        )

    # Also compute level correlation for reference and flag it
    r_levels, p_levels, n_levels = _safe_pearsonr(merged[debt_col], merged[gdp_col])
    level_note = (
        f"Level correlation: r={r_levels}, p={p_levels}, n={n_levels}. "
        f"This is likely spuriously high due to common trends in macroeconomic "
        f"time series. Growth rate correlation is preferred."
    )
    if r_levels is not None and abs(r_levels) > 0.95:
        logger.warning(
            f"Debt-GDP level correlation r={r_levels} is near-perfect -- "
            f"this is expected spurious correlation from trending series. "
            f"Using growth rates instead."
        )

    # Identify divergence periods (debt rising while GDP falling or vice versa)
    annual = merged.groupby("year")[[debt_col, gdp_col]].mean().reset_index()
    annual["debt_change"] = annual[debt_col].pct_change()
    annual["gdp_change"] = annual[gdp_col].pct_change()

    divergence_periods = []
    for _, row in annual.dropna().iterrows():
        debt_dir = (
            "rising"
            if row["debt_change"] > 0.01
            else ("falling" if row["debt_change"] < -0.01 else "stable")
        )
        gdp_dir = (
            "rising"
            if row["gdp_change"] > 0.01
            else ("falling" if row["gdp_change"] < -0.01 else "stable")
        )
        if (debt_dir == "rising" and gdp_dir == "falling") or (
            debt_dir == "falling" and gdp_dir == "rising"
        ):
            divergence_periods.append(
                {
                    "year": int(row["year"]),
                    "debt_direction": debt_dir,
                    "gdp_direction": gdp_dir,
                    "debt_change_pct": round(float(row["debt_change"]) * 100, 2),
                    "gdp_change_pct": round(float(row["gdp_change"]) * 100, 2),
                }
            )

    quarterly_data = (
        growth_data[["date_key", "year", "quarter", debt_col, gdp_col, "debt_growth", "gdp_growth"]]
        .round(4)
        .to_dict(orient="records")
    )

    summary = (
        f"Debt-GDP dynamics (growth rates): {interpretation}. "
        f"Based on {n} quarterly growth observations. "
        f"{len(divergence_periods)} year(s) of divergence identified."
    )

    logger.info("Debt-GDP dynamics analysis complete.")
    return {
        "summary": summary,
        "correlation": {
            "r": r,
            "p_value": p,
            "n": n,
            "method": "growth_rates",
            "interpretation": interpretation,
        },
        "level_correlation_note": level_note,
        "quarterly_data": quarterly_data,
        "divergence_periods": divergence_periods,
    }


def generate_correlation_report(db_path: Optional[str] = None) -> dict:
    """
    Run all correlation analyses and return combined results.

    Includes a data_quality_notes section flagging suspicious correlations.

    Returns
    -------
    dict
        Combined results from all correlation analyses.
    """
    db_path = db_path or str(DATABASE_PATH)
    log_section(logger, "CORRELATION ANALYSIS - ALL CROSS-PILLAR RELATIONSHIPS")

    results = {}
    data_quality_notes = []

    # Correlation matrix
    try:
        corr_matrix = build_correlation_matrix(db_path)
        results["correlation_matrix"] = (
            corr_matrix.round(4).to_dict() if not corr_matrix.empty else {}
        )

        # Scan for suspicious correlations
        if not corr_matrix.empty:
            for i in range(len(corr_matrix)):
                for j in range(i + 1, len(corr_matrix)):
                    r_val = corr_matrix.iloc[i, j]
                    if abs(r_val) > 0.95:
                        data_quality_notes.append(
                            f"Near-perfect correlation: {corr_matrix.index[i]} vs "
                            f"{corr_matrix.columns[j]} (r={r_val:.4f}). "
                            f"May indicate a linear dependency or spurious relationship."
                        )

        logger.info("Correlation matrix generated.")
    except Exception as exc:
        logger.error(f"Correlation matrix failed: {exc}")
        results["correlation_matrix"] = {}

    # Phillips curve
    try:
        results["phillips_curve"] = analyse_phillips_curve(db_path)
        pc_r = results["phillips_curve"].get("correlation", {}).get("r")
        if pc_r is not None and abs(pc_r) > 0.95:
            data_quality_notes.append(
                f"Phillips curve r={pc_r} is unusually high for this relationship. "
                f"Typical values range from -0.3 to -0.7."
            )
        logger.info("Phillips curve analysis generated.")
    except Exception as exc:
        logger.error(f"Phillips curve analysis failed: {exc}")
        results["phillips_curve"] = {"summary": f"Failed: {exc}"}

    # Interest rate transmission
    try:
        results["interest_rate_transmission"] = analyse_interest_rate_transmission(db_path)
        logger.info("Interest rate transmission analysis generated.")
    except Exception as exc:
        logger.error(f"Interest rate transmission analysis failed: {exc}")
        results["interest_rate_transmission"] = {"summary": f"Failed: {exc}"}

    # Debt-GDP dynamics
    try:
        results["debt_gdp_dynamics"] = analyse_debt_gdp_dynamics(db_path)
        dg_r = results["debt_gdp_dynamics"].get("correlation", {}).get("r")
        if dg_r is not None and abs(dg_r) > 0.95:
            data_quality_notes.append(
                f"Debt-GDP growth correlation r={dg_r} is unusually high. "
                f"Verify that growth rates (not levels) are being used."
            )
        logger.info("Debt-GDP dynamics analysis generated.")
    except Exception as exc:
        logger.error(f"Debt-GDP dynamics analysis failed: {exc}")
        results["debt_gdp_dynamics"] = {"summary": f"Failed: {exc}"}

    # Data quality notes section
    if not data_quality_notes:
        data_quality_notes.append(
            "No suspicious correlations detected. All values within expected ranges."
        )
    results["data_quality_notes"] = data_quality_notes

    logger.info("All correlation analyses complete.")
    return results
