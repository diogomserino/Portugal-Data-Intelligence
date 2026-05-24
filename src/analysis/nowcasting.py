"""
Portugal Data Intelligence - GDP Nowcasting
===========================================
Bridge equation approach to nowcast current-quarter GDP using
higher-frequency monthly indicators as predictors.

Usage:
    from src.analysis.nowcasting import run_nowcasting
    result = run_nowcasting()
"""

from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

from config.settings import DATABASE_PATH
from src.utils.db import get_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)

_QUARTERLY_GDP_QUERY = """
    SELECT d.year, d.quarter, f.gdp_growth_yoy
    FROM fact_gdp f
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.gdp_growth_yoy IS NOT NULL
    ORDER BY d.year, d.quarter
"""

_MONTHLY_INDICATORS_QUERY = """
    SELECT
        d.year,
        d.month,
        d.quarter,
        u.unemployment_rate,
        i.hicp,
        r.ecb_main_refinancing_rate
    FROM dim_date d
    LEFT JOIN fact_unemployment   u ON u.date_key = d.date_key
    LEFT JOIN fact_inflation       i ON i.date_key = d.date_key
    LEFT JOIN fact_interest_rates  r ON r.date_key = d.date_key
    WHERE LENGTH(d.date_key) = 7
    ORDER BY d.year, d.month
"""


def _quarterly_average(df_monthly: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Average monthly series to quarterly frequency."""
    return (
        df_monthly.groupby(["year", "quarter"])[value_col]
        .mean()
        .reset_index()
        .rename(columns={value_col: value_col})
    )


def run_nowcasting(db_path: Optional[str] = None) -> dict:
    """Nowcast GDP growth using bridge equations from monthly indicators.

    Returns
    -------
    dict
        'nowcast': estimated GDP growth for latest incomplete quarter,
        'confidence_interval': 95% CI,
        'model_fit': in-sample R², MAE,
        'predictors': list of predictor names used,
        'error': error message if failed
    """
    db_path = db_path or str(DATABASE_PATH)

    with get_connection(db_path) as conn:
        try:
            gdp_df = pd.read_sql(_QUARTERLY_GDP_QUERY, conn)
            monthly_df = pd.read_sql(_MONTHLY_INDICATORS_QUERY, conn)
        except Exception as exc:
            return {"error": f"Data load failed: {exc}"}

    if gdp_df.empty or monthly_df.empty:
        return {"error": "Insufficient data for nowcasting"}

    # Aggregate monthly indicators to quarterly
    predictor_cols = ["unemployment_rate", "hicp", "ecb_main_refinancing_rate"]
    quarterly_indicators = None
    for col in predictor_cols:
        if col not in monthly_df.columns:
            continue
        q_series = _quarterly_average(monthly_df[["year", "quarter", col]], col)
        if quarterly_indicators is None:
            quarterly_indicators = q_series
        else:
            quarterly_indicators = quarterly_indicators.merge(
                q_series, on=["year", "quarter"], how="outer"
            )

    if quarterly_indicators is None:
        return {"error": "No monthly indicator data available"}

    # Merge with GDP
    merged = gdp_df.merge(quarterly_indicators, on=["year", "quarter"], how="inner")
    merged = merged.dropna()

    if len(merged) < 8:
        return {"error": f"Insufficient observations after merge: {len(merged)}"}

    # Bridge equation: OLS regression with 1-quarter lags of indicators
    for col in predictor_cols:
        if col in merged.columns:
            merged[f"{col}_lag1"] = merged[col].shift(1)

    lag_cols = [f"{c}_lag1" for c in predictor_cols if f"{c}_lag1" in merged.columns]
    merged = merged.dropna(subset=lag_cols)

    if len(merged) < 6:
        return {"error": "Insufficient observations after lagging"}

    X = merged[lag_cols].values
    y = merged["gdp_growth_yoy"].values

    # Add intercept
    X_const = np.column_stack([np.ones(len(X)), X])
    try:
        coeffs, _, _, _ = np.linalg.lstsq(X_const, y, rcond=None)
    except np.linalg.LinAlgError as exc:
        return {"error": f"OLS failed: {exc}"}

    # In-sample fit
    y_hat = X_const @ coeffs
    residuals = y - y_hat
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else 0
    mae = round(float(np.mean(np.abs(residuals))), 4)

    # Nowcast: use latest available indicator values (current quarter lags)
    latest_row = merged.iloc[-1]
    x_latest = np.array([1.0] + [float(latest_row.get(c, 0)) for c in lag_cols])
    nowcast_val = float(x_latest @ coeffs)

    # Approximate 95% CI from residual std
    sigma = np.std(residuals, ddof=len(coeffs))
    ci_half = 1.96 * float(sigma)

    result = {
        "nowcast": round(nowcast_val, 2),
        "confidence_interval": {
            "lower_95": round(nowcast_val - ci_half, 2),
            "upper_95": round(nowcast_val + ci_half, 2),
        },
        "model_fit": {
            "r_squared": r_squared,
            "mae": mae,
            "n_observations": len(merged),
        },
        "predictors": lag_cols,
        "latest_quarter": {
            "year": int(latest_row["year"]),
            "quarter": int(latest_row["quarter"]),
        },
    }

    logger.info(
        "Nowcast GDP growth: %.2f%% [%.2f, %.2f] (R²=%.3f)",
        nowcast_val,
        nowcast_val - ci_half,
        nowcast_val + ci_half,
        r_squared,
    )
    return result
