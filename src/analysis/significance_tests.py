"""
Portugal Data Intelligence — Statistical Significance Tests
=============================================================
Adds inferential statistics to complement the descriptive analysis:
- Stationarity test (ADF) for validating correlation assumptions
- t-tests for comparing economic periods (with Bonferroni correction)
- ANOVA for multi-period comparisons
- Trend significance (linear regression t-test)
- Granger causality proxy (lagged correlation significance)
- Structural break detection (Chow test)
"""

import sqlite3
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from config.settings import CHART_PERIODS as _CHART_PERIODS
from config.settings import DATA_PILLARS, DATABASE_PATH
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Stationarity test (ADF)
# ---------------------------------------------------------------------------


def test_stationarity(y: np.ndarray, significance: float = 0.05) -> dict:
    """Augmented Dickey-Fuller test for unit root (non-stationarity).

    A stationary series is safe for Pearson correlation; a non-stationary
    series should be differenced first to avoid spurious correlations.

    Parameters
    ----------
    y : np.ndarray
        Time series values.
    significance : float
        Significance level (default 0.05).

    Returns
    -------
    dict
        adf_statistic, p_value, is_stationary, critical_values, interpretation
    """
    from scipy.stats import norm  # noqa: F811

    y = np.asarray(y, dtype=float)
    y = y[~np.isnan(y)]

    if len(y) < 8:
        return {
            "adf_statistic": None,
            "p_value": None,
            "is_stationary": None,
            "critical_values": {},
            "n_obs": len(y),
            "interpretation": "Insufficient data for ADF test (need >= 8 observations).",
        }

    # ADF implementation: regress Δy_t on y_{t-1} + lagged differences
    dy = np.diff(y)
    n_full = len(dy)

    # Select optimal lag length (max 4, limited by sample size)
    max_lags = min(4, n_full // 4)

    # Build regression matrix with lagged differences
    if max_lags > 0:
        lag_cols = [dy[max_lags - k - 1 : n_full - k - 1] for k in range(max_lags)]
        dy_trimmed = dy[max_lags:]
        y_lag = y[max_lags:-1]
        n = len(dy_trimmed)
        X = np.column_stack([np.ones(n), y_lag] + lag_cols)
    else:
        dy_trimmed = dy
        y_lag = y[:-1]
        n = len(dy_trimmed)
        X = np.column_stack([np.ones(n), y_lag])
    try:
        beta, residuals, _, _ = np.linalg.lstsq(X, dy_trimmed, rcond=None)
    except np.linalg.LinAlgError:
        return {
            "adf_statistic": None,
            "p_value": None,
            "is_stationary": None,
            "critical_values": {},
            "n_obs": n,
            "interpretation": "Numerical error in ADF regression.",
        }

    adf_coeff = beta[1]
    n_params = X.shape[1]
    resid = dy_trimmed - X @ beta
    sigma2 = float(np.sum(resid**2) / max(n - n_params, 1))

    try:
        XtX_inv = np.linalg.inv(X.T @ X)
        se_beta = float(np.sqrt(sigma2 * XtX_inv[1, 1]))
    except (np.linalg.LinAlgError, FloatingPointError):
        # If singular with lags, retry without lags (ADF(0))
        if max_lags > 0:
            X_simple = np.column_stack([np.ones(n_full), y[:-1]])
            dy_simple = dy
            try:
                beta_s, _, _, _ = np.linalg.lstsq(X_simple, dy_simple, rcond=None)
                resid_s = dy_simple - X_simple @ beta_s
                sigma2_s = float(np.sum(resid_s**2) / max(n_full - 2, 1))
                se_s = float(np.sqrt(sigma2_s * np.linalg.inv(X_simple.T @ X_simple)[1, 1]))
                adf_coeff = beta_s[1]
                se_beta = se_s
                n = n_full
            except (np.linalg.LinAlgError, FloatingPointError):
                return {
                    "adf_statistic": None,
                    "p_value": None,
                    "is_stationary": None,
                    "critical_values": {},
                    "n_obs": n,
                    "interpretation": "Singular matrix in ADF — series may be constant.",
                }
        else:
            return {
                "adf_statistic": None,
                "p_value": None,
                "is_stationary": None,
                "critical_values": {},
                "n_obs": n,
                "interpretation": "Singular matrix in ADF — series may be constant.",
            }

    adf_stat = adf_coeff / se_beta if se_beta > 0 else 0.0

    # Critical values for ADF with constant, no trend (MacKinnon 2010)
    cv = {"1%": -3.43, "5%": -2.86, "10%": -2.57}
    # Adjust for sample size (finite-sample correction for n < 100)
    if n < 50:
        cv = {"1%": -3.58, "5%": -2.93, "10%": -2.60}

    # Conservative p-value approximation
    if adf_stat < cv["1%"]:
        p_approx = 0.005
    elif adf_stat < cv["5%"]:
        p_approx = 0.03
    elif adf_stat < cv["10%"]:
        p_approx = 0.07
    else:
        p_approx = 0.15 + 0.05 * min(max(adf_stat + 2.57, 0), 5)

    is_stationary = adf_stat < cv["5%"]

    return {
        "adf_statistic": round(float(adf_stat), 4),
        "p_value": round(float(p_approx), 4),
        "is_stationary": is_stationary,
        "critical_values": cv,
        "n_obs": n,
        "interpretation": (
            f"{'Stationary' if is_stationary else 'Non-stationary'} series "
            f"(ADF={adf_stat:.3f}, 5% critical value={cv['5%']}). "
            + (
                "Safe for Pearson correlation."
                if is_stationary
                else "Use first differences or growth rates before correlation analysis."
            )
        ),
    }


# Economic period definitions (derived from central config)
PERIODS = {
    k.lower().replace("-", "_").replace(" ", "_"): (int(s), int(e))
    for k, (s, e) in _CHART_PERIODS.items()
}


def test_trend_significance(y: np.ndarray, x: Optional[np.ndarray] = None) -> dict:
    """Test if a time series has a statistically significant trend.

    Uses OLS regression: y = a + b*x + epsilon

    Parameters
    ----------
    y : np.ndarray
        Dependent variable (the time series values).
    x : np.ndarray, optional
        Independent variable (time index). If None, uses 0..len(y)-1.

    Returns
    -------
    dict
        slope, intercept, r_squared, p_value, std_err, significant, interpretation
    """
    y = np.asarray(y, dtype=float)
    mask = ~np.isnan(y)
    y = y[mask]

    if len(y) < 3:
        return {
            "slope": None,
            "intercept": None,
            "r_squared": None,
            "p_value": None,
            "std_err": None,
            "significant": None,
            "interpretation": "Insufficient data for trend test (need >= 3 observations).",
        }

    if x is None:
        x = np.arange(len(y), dtype=float)
    else:
        x = np.asarray(x, dtype=float)[mask]

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    return {
        "slope": round(slope, 6),
        "intercept": round(intercept, 4),
        "r_squared": round(r_value**2, 4),
        "p_value": round(p_value, 6),
        "std_err": round(std_err, 6),
        "significant": p_value < 0.05,
        "interpretation": (
            f"{'Significant' if p_value < 0.05 else 'Not significant'} trend "
            f"(slope={slope:.4f}, p={p_value:.4f}, R\u00b2={r_value**2:.3f})"
        ),
    }


def test_period_comparison(
    data: pd.DataFrame,
    value_col: str,
    year_col: str = "year",
) -> dict:
    """Compare means across economic periods using ANOVA and pairwise t-tests.

    Parameters
    ----------
    data : pd.DataFrame
        Must contain *year_col* and *value_col*.
    value_col : str
        Column with the numeric values to compare.
    year_col : str
        Column containing year integers.

    Returns
    -------
    dict
        anova, period_means, pairwise_tests, n_significant_pairs,
        n_total_pairs, interpretation
    """
    # Group data by period
    groups: Dict[str, np.ndarray] = {}
    for period_name, (start, end) in PERIODS.items():
        mask = (data[year_col] >= start) & (data[year_col] <= end)
        values = data.loc[mask, value_col].dropna().values
        if len(values) >= 2:
            groups[period_name] = values

    if len(groups) < 2:
        return {
            "anova": {"f_statistic": None, "p_value": None, "significant": None},
            "period_means": {},
            "pairwise_tests": [],
            "n_significant_pairs": 0,
            "n_total_pairs": 0,
            "interpretation": "Insufficient periods with >= 2 observations for comparison.",
        }

    # One-way ANOVA
    f_stat, p_value = stats.f_oneway(*groups.values())
    anova = {
        "f_statistic": round(float(f_stat), 4),
        "p_value": round(float(p_value), 6),
        "significant": p_value < 0.05,
    }

    # Period means
    period_means = {k: round(float(np.mean(v)), 4) for k, v in groups.items()}

    # Pairwise t-tests (Welch's t-test, unequal variances) with Bonferroni correction
    pairwise: List[dict] = []
    period_names = list(groups.keys())
    n_comparisons = len(period_names) * (len(period_names) - 1) // 2
    bonferroni_alpha = 0.05 / max(n_comparisons, 1)

    for i in range(len(period_names)):
        for j in range(i + 1, len(period_names)):
            a, b = period_names[i], period_names[j]
            t_stat, p_val = stats.ttest_ind(groups[a], groups[b], equal_var=False)

            # Cohen's d effect size
            pooled_std = np.sqrt((np.var(groups[a], ddof=1) + np.var(groups[b], ddof=1)) / 2)
            if pooled_std > 1e-12:
                cohens_d = float((np.mean(groups[a]) - np.mean(groups[b])) / pooled_std)
            else:
                cohens_d = 0.0

            pairwise.append(
                {
                    "period_a": a,
                    "period_b": b,
                    "t_statistic": round(float(t_stat), 4),
                    "p_value": round(float(p_val), 6),
                    "p_value_bonferroni": round(float(min(p_val * n_comparisons, 1.0)), 6),
                    "significant_nominal": p_val < 0.05,
                    "significant": p_val < bonferroni_alpha,
                    "cohens_d": round(cohens_d, 3),
                    "mean_diff": round(float(np.mean(groups[a]) - np.mean(groups[b])), 4),
                }
            )

    n_sig = sum(1 for t in pairwise if t["significant"])

    return {
        "anova": anova,
        "period_means": period_means,
        "pairwise_tests": pairwise,
        "n_significant_pairs": n_sig,
        "n_total_pairs": len(pairwise),
        "bonferroni_alpha": round(bonferroni_alpha, 4),
        "interpretation": (
            f"ANOVA {'rejects' if anova['significant'] else 'fails to reject'} "
            f"H0 of equal means (F={anova['f_statistic']}, p={anova['p_value']}). "
            f"{n_sig}/{len(pairwise)} pairwise comparisons are significant "
            f"after Bonferroni correction (alpha={bonferroni_alpha:.4f})."
        ),
    }


def test_structural_break(
    y: np.ndarray,
    break_point: int,
) -> dict:
    """Chow test approximation for structural break at a given index.

    Compares the residual sum of squares of one pooled regression against
    two separate regressions (before and after *break_point*).

    Parameters
    ----------
    y : np.ndarray
        Time series values.
    break_point : int
        Index in *y* at which to test the structural break.

    Returns
    -------
    dict
        f_statistic, p_value, significant, interpretation
    """
    y = np.asarray(y, dtype=float)
    mask = ~np.isnan(y)
    y = y[mask]
    n = len(y)

    if break_point < 3 or break_point > n - 3:
        return {
            "f_statistic": None,
            "p_value": None,
            "significant": None,
            "interpretation": (
                "Break point too close to boundaries — need at least 3 "
                "observations on each side."
            ),
        }

    x = np.arange(n, dtype=float)
    k = 2  # number of parameters per regression (slope + intercept)

    # Full (pooled) model
    slope_full, intercept_full, _, _, _ = stats.linregress(x, y)
    y_hat_full = intercept_full + slope_full * x
    rss_full = np.sum((y - y_hat_full) ** 2)

    # Sub-model 1: before break
    x1, y1 = x[:break_point], y[:break_point]
    slope1, intercept1, _, _, _ = stats.linregress(x1, y1)
    rss1 = np.sum((y1 - (intercept1 + slope1 * x1)) ** 2)

    # Sub-model 2: after break
    x2, y2 = x[break_point:], y[break_point:]
    slope2, intercept2, _, _, _ = stats.linregress(x2, y2)
    rss2 = np.sum((y2 - (intercept2 + slope2 * x2)) ** 2)

    rss_sub = rss1 + rss2
    # Chow test: df_num = k (number of restrictions from pooling)
    # df_den = n1 + n2 - 2k = n - 2k (residual df of the unrestricted model)
    n1, n2 = len(y1), len(y2)
    df_num = k
    df_den = (n1 - k) + (n2 - k)  # = n - 2k

    if df_den <= 0 or rss_sub == 0:
        return {
            "f_statistic": None,
            "p_value": None,
            "significant": None,
            "interpretation": "Degenerate model — cannot compute F-statistic.",
        }

    f_stat = ((rss_full - rss_sub) / df_num) / (rss_sub / df_den)
    p_value = 1 - stats.f.cdf(f_stat, df_num, df_den)

    return {
        "f_statistic": round(float(f_stat), 4),
        "p_value": round(float(p_value), 6),
        "significant": p_value < 0.05,
        "rss_full": round(float(rss_full), 4),
        "rss_restricted": round(float(rss_sub), 4),
        "interpretation": (
            f"{'Significant' if p_value < 0.05 else 'No significant'} structural break "
            f"detected (F={f_stat:.4f}, p={p_value:.4f})."
        ),
    }


def test_granger_proxy(
    cause: np.ndarray,
    effect: np.ndarray,
    max_lag: int = 12,
) -> dict:
    """Simplified Granger causality test using lagged correlations.

    For each lag from 1 to *max_lag*, computes the Pearson correlation
    between ``cause[:-lag]`` and ``effect[lag:]`` and records the p-value.
    Returns the lag with the strongest *significant* correlation.

    Parameters
    ----------
    cause : np.ndarray
        Potential causal series.
    effect : np.ndarray
        Potential effect series.
    max_lag : int
        Maximum number of lags to test (default 12).

    Returns
    -------
    dict
        optimal_lag, correlation_at_lag, p_value, all_lags, interpretation
    """
    cause = np.asarray(cause, dtype=float)
    effect = np.asarray(effect, dtype=float)

    # Remove rows where either series is NaN (aligned)
    valid = ~(np.isnan(cause) | np.isnan(effect))
    cause = cause[valid]
    effect = effect[valid]
    n = len(cause)

    if n < max_lag + 5:
        max_lag = max(1, n - 5)

    all_lags: List[dict] = []
    best_lag = None
    best_abs_r = -1.0
    best_result = None

    # Bonferroni correction for testing multiple lags
    bonferroni_alpha = 0.05 / max(max_lag, 1)

    for lag in range(1, max_lag + 1):
        c = cause[: n - lag]
        e = effect[lag:]
        if len(c) < 4:
            continue
        r, p = stats.pearsonr(c, e)
        lag_entry = {
            "lag": lag,
            "correlation": round(float(r), 4),
            "p_value": round(float(p), 6),
            "p_value_bonferroni": round(float(min(p * max_lag, 1.0)), 6),
            "significant": p < bonferroni_alpha,
            "n_obs": len(c),
        }
        all_lags.append(lag_entry)

        if p < bonferroni_alpha and abs(r) > best_abs_r:
            best_abs_r = abs(r)
            best_lag = lag
            best_result = lag_entry

    if best_result is None:
        return {
            "optimal_lag": None,
            "correlation_at_lag": None,
            "p_value": None,
            "bonferroni_alpha": round(bonferroni_alpha, 4),
            "all_lags": all_lags,
            "interpretation": (
                "No significant lagged correlation found between the two series "
                f"(tested lags 1-{max_lag}, Bonferroni alpha={bonferroni_alpha:.4f}). "
                "Note: this is a correlation-based proxy, not a formal Granger causality test."
            ),
        }

    return {
        "optimal_lag": best_result["lag"],
        "correlation_at_lag": best_result["correlation"],
        "p_value": best_result["p_value"],
        "bonferroni_alpha": round(bonferroni_alpha, 4),
        "all_lags": all_lags,
        "interpretation": (
            f"Strongest significant lagged correlation at lag {best_result['lag']} "
            f"(r={best_result['correlation']:.3f}, p={best_result['p_value']:.4f}, "
            f"Bonferroni-adjusted alpha={bonferroni_alpha:.4f}). "
            f"Note: lagged correlation suggests but does not prove causality. "
            f"A formal VAR-based Granger test is recommended for causal inference."
        ),
    }


# ---------------------------------------------------------------------------
# Pillar-level helpers
# ---------------------------------------------------------------------------

_PILLAR_QUERIES = {
    "gdp": (
        "SELECT d.year, d.quarter, g.* "
        "FROM fact_gdp g JOIN dim_date d ON g.date_key = d.date_key "
        "ORDER BY d.year, d.quarter"
    ),
    "unemployment": (
        "SELECT d.year, d.month, u.* "
        "FROM fact_unemployment u JOIN dim_date d ON u.date_key = d.date_key "
        "ORDER BY d.year, d.month"
    ),
    "credit": (
        "SELECT d.year, d.month, c.* "
        "FROM fact_credit c JOIN dim_date d ON c.date_key = d.date_key "
        "ORDER BY d.year, d.month"
    ),
    "interest_rates": (
        "SELECT d.year, d.month, ir.* "
        "FROM fact_interest_rates ir JOIN dim_date d ON ir.date_key = d.date_key "
        "ORDER BY d.year, d.month"
    ),
    "inflation": (
        "SELECT d.year, d.month, inf.* "
        "FROM fact_inflation inf JOIN dim_date d ON inf.date_key = d.date_key "
        "ORDER BY d.year, d.month"
    ),
    "public_debt": (
        "SELECT d.year, d.quarter, pd.* "
        "FROM fact_public_debt pd JOIN dim_date d ON pd.date_key = d.date_key "
        "ORDER BY d.year, d.quarter"
    ),
}


def _pick_primary_column(df: pd.DataFrame, pillar: str) -> Optional[str]:
    """Heuristically select the primary numeric column for a pillar."""
    skip = {"date_key", "year", "month", "quarter", "source_key"}
    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in skip]

    # Pillar-specific heuristics
    hints = {
        "gdp": ["gdp_nominal", "nominal_gdp", "gdp_real", "real_gdp", "gdp", "value"],
        "unemployment": ["unemployment_rate", "rate", "total_rate"],
        "credit": ["total_credit", "credit_total", "total"],
        "interest_rates": ["ecb_rate", "key_rate", "main_refinancing_rate", "euribor_3m"],
        "inflation": ["hicp_annual", "cpi_annual", "inflation_rate", "hicp", "cpi_estimated"],
        "public_debt": ["debt_to_gdp", "debt_gdp_ratio", "debt_ratio", "total_debt"],
    }

    for candidate in hints.get(pillar, []):
        if candidate in numeric_cols:
            return candidate

    return numeric_cols[0] if numeric_cols else None


def run_all_significance_tests(db_path: Optional[str] = None) -> dict:
    """Run comprehensive significance tests across all pillars.

    For each pillar the function computes:
    1. **Trend significance** — is the overall trend statistically significant?
    2. **Period comparison** — are the economic periods statistically different
       (ANOVA + pairwise Welch t-tests)?
    3. **Structural break tests** — Chow test at the start of the troika era
       (index for 2012) and at the COVID shock (index for 2020).

    Parameters
    ----------
    db_path : str, optional
        Path to the SQLite database.  Defaults to ``DATABASE_PATH``.

    Returns
    -------
    dict
        Keyed by pillar name, each value is a dict with keys
        ``trend_test``, ``period_comparison``, ``structural_breaks``.
    """
    db_path = db_path or str(DATABASE_PATH)
    logger.info("Running significance tests across all pillars...")
    results: Dict[str, dict] = {}

    try:
        conn = sqlite3.connect(db_path)
    except Exception as exc:
        logger.error(f"Cannot connect to database: {exc}")
        return results

    try:
        for pillar, query in _PILLAR_QUERIES.items():
            try:
                df = pd.read_sql(query, conn)
            except Exception as exc:
                logger.warning(f"Could not load {pillar}: {exc}")
                results[pillar] = {"error": str(exc)}
                continue

            if df.empty:
                results[pillar] = {"error": "No data"}
                continue

            col = _pick_primary_column(df, pillar)
            if col is None:
                results[pillar] = {"error": "No suitable numeric column"}
                continue

            # Annual aggregation for period-level tests
            annual = df.groupby("year")[col].mean().reset_index()
            values = annual[col].dropna().values

            # 0. Stationarity test (ADF)
            stationarity = test_stationarity(values)

            # 1. Trend significance
            trend = test_trend_significance(values)

            # 2. Period comparison
            period_cmp = test_period_comparison(annual, col, "year")

            # 3. Structural breaks — troika start (2012) and COVID (2020)
            breaks: Dict[str, dict] = {}
            years = annual["year"].values
            for label, break_year in [("troika_2012", 2012), ("covid_2020", 2020)]:
                idx = np.searchsorted(years, break_year)
                if 3 <= idx <= len(values) - 3:
                    breaks[label] = test_structural_break(values, int(idx))
                else:
                    breaks[label] = {
                        "f_statistic": None,
                        "p_value": None,
                        "significant": None,
                        "interpretation": f"Break point {break_year} too close to series boundary.",
                    }

            results[pillar] = {
                "primary_column": col,
                "n_observations": len(values),
                "stationarity_test": stationarity,
                "trend_test": trend,
                "period_comparison": period_cmp,
                "structural_breaks": breaks,
            }
            logger.info(f"Significance tests complete for {pillar}.")
    finally:
        conn.close()
    logger.info("All significance tests finished.")
    return results


if __name__ == "__main__":
    results = run_all_significance_tests()

    for pillar, res in results.items():
        print(f"\n{'=' * 60}")
        print(f"  {pillar.upper()}")
        print(f"{'=' * 60}")

        if "error" in res:
            print(f"  Error: {res['error']}")
            continue

        print(f"  Primary column : {res['primary_column']}")
        print(f"  Observations   : {res['n_observations']}")
        print(f"\n  Trend test:")
        print(f"    {res['trend_test']['interpretation']}")
        print(f"\n  Period comparison:")
        print(f"    {res['period_comparison']['interpretation']}")
        for pw in res["period_comparison"]["pairwise_tests"]:
            sig = "*" if pw["significant"] else " "
            print(
                f"    {sig} {pw['period_a']:15s} vs {pw['period_b']:15s}  "
                f"t={pw['t_statistic']:+7.3f}  p={pw['p_value']:.4f}  "
                f"diff={pw['mean_diff']:+.4f}"
            )
        print(f"\n  Structural breaks:")
        for label, brk in res["structural_breaks"].items():
            print(f"    {label}: {brk['interpretation']}")
