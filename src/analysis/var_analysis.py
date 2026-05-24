"""
Portugal Data Intelligence - VAR/VECM Analysis
================================================
Vector Autoregression analysis for cross-pillar macroeconomic dynamics.
Produces impulse response functions, Granger causality tests, and
forecast error variance decomposition.

Usage:
    from src.analysis.var_analysis import run_var_analysis
    results = run_var_analysis()
"""

from typing import Optional

import numpy as np
import pandas as pd

from config.settings import DATABASE_PATH
from src.utils.db import get_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from statsmodels.tsa.stattools import grangercausalitytests
    from statsmodels.tsa.vector_ar.var_model import VAR

    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

_VAR_QUERY = """
    SELECT
        d.year,
        d.quarter,
        g.gdp_growth_yoy,
        u.unemployment_rate,
        i.hicp,
        r.ecb_main_refinancing_rate,
        p.debt_to_gdp_ratio
    FROM dim_date d
    LEFT JOIN fact_gdp        g ON g.date_key = d.date_key
    LEFT JOIN fact_unemployment u ON (
        SUBSTR(d.date_key, 1, 4) || '-' ||
        CASE d.quarter WHEN 1 THEN '03' WHEN 2 THEN '06' WHEN 3 THEN '09' ELSE '12' END
        = u.date_key
    )
    LEFT JOIN fact_inflation   i ON (
        SUBSTR(d.date_key, 1, 4) || '-' ||
        CASE d.quarter WHEN 1 THEN '03' WHEN 2 THEN '06' WHEN 3 THEN '09' ELSE '12' END
        = i.date_key
    )
    LEFT JOIN fact_interest_rates r ON (
        SUBSTR(d.date_key, 1, 4) || '-' ||
        CASE d.quarter WHEN 1 THEN '03' WHEN 2 THEN '06' WHEN 3 THEN '09' ELSE '12' END
        = r.date_key
    )
    LEFT JOIN fact_public_debt p ON p.date_key = d.date_key
    WHERE d.date_key LIKE '%-Q_'
    ORDER BY d.year, d.quarter
"""

_VAR_COLS = [
    "gdp_growth_yoy",
    "unemployment_rate",
    "hicp",
    "ecb_main_refinancing_rate",
    "debt_to_gdp_ratio",
]


def run_var_analysis(db_path: Optional[str] = None, max_lags: int = 4) -> dict:
    """Run VAR analysis on the main macroeconomic pillars.

    Returns
    -------
    dict
        Keys: 'selected_lag', 'granger_causality', 'irf_summary', 'fevd', 'error'
    """
    if not HAS_STATSMODELS:
        return {"error": "statsmodels not available"}

    db_path = db_path or str(DATABASE_PATH)

    with get_connection(db_path) as conn:
        try:
            df = pd.read_sql(_VAR_QUERY, conn)
        except Exception as exc:
            return {"error": f"Query failed: {exc}"}

    if df.empty:
        return {"error": "No data returned"}

    # Keep only columns with enough non-null observations
    df_var = df[_VAR_COLS].dropna()

    if len(df_var) < max_lags * 2 + 5:
        return {"error": f"Insufficient data: {len(df_var)} rows after dropna"}

    result: dict = {"n_observations": len(df_var)}

    try:
        model = VAR(df_var)
        lag_selection = model.select_order(maxlags=max_lags)
        selected_lag = int(lag_selection.selected_orders.get("aic", 1))
        selected_lag = max(1, min(selected_lag, max_lags))
        result["selected_lag"] = selected_lag

        fitted = model.fit(selected_lag)
        result["aic"] = round(float(fitted.aic), 2)
        result["bic"] = round(float(fitted.bic), 2)

        # Impulse response function (10 periods)
        irf = fitted.irf(10)
        irf_df = pd.DataFrame(
            irf.irfs[:, 0, :],  # shock to gdp_growth_yoy, response of all variables
            columns=_VAR_COLS,
        )
        result["irf_gdp_shock"] = {
            col: [round(float(v), 4) for v in irf_df[col].tolist()] for col in _VAR_COLS
        }

        # Forecast error variance decomposition
        fevd = fitted.fevd(10)
        result["fevd"] = {
            col: {col2: round(float(fevd.decomp[j][-1, i]), 4) for i, col2 in enumerate(_VAR_COLS)}
            for j, col in enumerate(_VAR_COLS)
        }

    except Exception as exc:
        logger.warning(f"VAR estimation failed: {exc}")
        result["error"] = str(exc)
        return result

    # Granger causality (pairwise)
    granger = {}
    for target in _VAR_COLS[:3]:  # limit to key variables
        granger[target] = {}
        for cause in _VAR_COLS:
            if cause == target:
                continue
            try:
                test_data = df_var[[target, cause]].dropna()
                gc = grangercausalitytests(test_data, maxlag=selected_lag, verbose=False)
                min_pval = min(gc[lag][0]["ssr_ftest"][1] for lag in range(1, selected_lag + 1))
                granger[target][cause] = round(float(min_pval), 4)
            except Exception:
                granger[target][cause] = None

    result["granger_causality"] = granger

    logger.info(
        "VAR analysis complete: %d observations, lag=%d, AIC=%.1f",
        len(df_var),
        selected_lag,
        result.get("aic", float("nan")),
    )
    return result
