"""
Portugal Data Intelligence — Forecasting Module
=================================================
Provides 3-year forward projections (2026-2028) using:

1. **SARIMAX** — for GDP and inflation (primary method, requires statsmodels)
2. **Log-linear trend extrapolation** — for GDP and credit aggregates (fallback)
3. **Exponential smoothing (simple)** — for smoothing noisy series
4. **Mean-reversion (Ornstein-Uhlenbeck)** — for rates, ratios, and bounded indicators

Each forecast includes confidence bands at the 68 % and 95 % levels.
"""

import sqlite3
import warnings
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize_scalar

from config.settings import DATA_PILLARS, DATABASE_PATH
from src.utils.logger import get_logger, log_section

# Optional dependency — graceful fallback if not installed.
try:
    from statsmodels.stats.diagnostic import acorr_ljungbox
    from statsmodels.tsa.statespace.sarimax import SARIMAX as _SARIMAX

    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Standalone helper functions
# ---------------------------------------------------------------------------


def _exponential_smoothing(series: np.ndarray, alpha: float = 0.3) -> np.ndarray:
    """Simple exponential smoothing.

    Parameters
    ----------
    series : np.ndarray
        Historical observations (oldest-first).
    alpha : float
        Smoothing factor in (0, 1).  Higher = more weight on recent data.

    Returns
    -------
    np.ndarray
        Smoothed series of the same length as *series*.
    """
    result = np.empty_like(series, dtype=float)
    result[0] = series[0]
    for t in range(1, len(series)):
        result[t] = alpha * series[t] + (1.0 - alpha) * result[t - 1]
    return result


def _optimal_alpha(series: np.ndarray) -> float:
    """Find the alpha that minimises one-step-ahead SSE via bounded optimisation."""

    def _sse(alpha: float) -> float:
        smoothed = _exponential_smoothing(series, alpha)
        # One-step errors: actual[t] vs smoothed[t-1]
        errors = series[1:] - smoothed[:-1]
        return float(np.sum(errors**2))

    result = minimize_scalar(_sse, bounds=(0.01, 0.99), method="bounded")
    return float(result.x)


def _log_linear_forecast(y: np.ndarray, horizon: int) -> dict:
    """Fit a log-linear trend and project forward with prediction intervals.

    The model is:  ln(y_t) = a + b * t + e_t

    Parameters
    ----------
    y : np.ndarray
        Strictly positive historical observations (oldest-first).
    horizon : int
        Number of periods to forecast.

    Returns
    -------
    dict
        Keys: ``fitted``, ``forecast``, ``lower_68``, ``upper_68``,
        ``lower_95``, ``upper_95``, ``slope``, ``r_squared``, ``annual_growth``.
    """
    n = len(y)
    t = np.arange(n)
    if np.any(y <= 0):
        y = np.clip(y, 1e-6, None)
        logger.warning("Non-positive values clipped to 1e-6 before log transform.")
    log_y = np.log(y)

    slope, intercept, r_value, _p, std_err = stats.linregress(t, log_y)
    residuals = log_y - (intercept + slope * t)
    sigma = float(np.std(residuals, ddof=2))

    fitted = np.exp(intercept + slope * t)

    t_fwd = np.arange(n, n + horizon)
    log_forecast = intercept + slope * t_fwd

    # Prediction interval uses the residual standard error
    forecast_central = np.exp(log_forecast)
    lower_68 = np.exp(log_forecast - 1.0 * sigma)
    upper_68 = np.exp(log_forecast + 1.0 * sigma)
    lower_95 = np.exp(log_forecast - 1.96 * sigma)
    upper_95 = np.exp(log_forecast + 1.96 * sigma)

    return {
        "fitted": fitted,
        "forecast": forecast_central,
        "lower_68": lower_68,
        "upper_68": upper_68,
        "lower_95": lower_95,
        "upper_95": upper_95,
        "slope": float(slope),
        "r_squared": float(r_value**2),
        "annual_growth": float(np.exp(slope * 4) - 1) * 100,  # annualised assuming quarterly data
    }


def _mean_reversion_forecast(
    y: np.ndarray,
    target: float,
    speed: Optional[float] = None,
    horizon: int = 36,
) -> dict:
    """Ornstein-Uhlenbeck mean-reversion model.

    dy = speed * (target - y) * dt + sigma * dW

    If *speed* is not provided it is estimated from the data via OLS on
    the discretised equation:  y_{t+1} - y_t = speed * (target - y_t) + e_t

    Parameters
    ----------
    y : np.ndarray
        Historical observations (oldest-first).
    target : float
        Long-run equilibrium level.
    speed : float or None
        Mean-reversion speed per period.  Estimated if ``None``.
    horizon : int
        Number of periods to project.

    Returns
    -------
    dict
        Keys: ``forecast``, ``lower_68``, ``upper_68``, ``lower_95``,
        ``upper_95``, ``speed``, ``sigma``, ``target``.
    """
    dy = np.diff(y)
    x = target - y[:-1]

    if speed is None:
        if np.var(x) > 1e-12:
            slope_est, _intercept, _r, _p, _se = stats.linregress(x, dy)
            speed = max(float(slope_est), 0.001)  # enforce positive reversion
        else:
            speed = 0.05  # fallback

    residuals = dy - speed * x
    sigma = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.1

    # Simulate the expected path and bands
    forecast = np.empty(horizon)
    current = float(y[-1])
    for h in range(horizon):
        current = current + speed * (target - current)
        forecast[h] = current

    # Variance grows but is bounded:  Var_h = sigma^2 / (2*speed) * (1 - exp(-2*speed*h))
    h_arr = np.arange(1, horizon + 1)
    if speed > 1e-8:
        var_h = (sigma**2 / (2.0 * speed)) * (1.0 - np.exp(-2.0 * speed * h_arr))
    else:
        var_h = sigma**2 * h_arr

    std_h = np.sqrt(var_h)

    return {
        "forecast": forecast,
        "lower_68": forecast - 1.0 * std_h,
        "upper_68": forecast + 1.0 * std_h,
        "lower_95": forecast - 1.96 * std_h,
        "upper_95": forecast + 1.96 * std_h,
        "speed": speed,
        "sigma": sigma,
        "target": target,
    }


def _sarimax_forecast(
    y: np.ndarray,
    seasonal_period: int = 4,
    horizon: int = 12,
    max_order: Tuple[int, int, int] = (2, 1, 2),
    max_seasonal: Tuple[int, int, int] = (1, 1, 1),
) -> Optional[dict]:
    """Fit SARIMAX with AIC-based order selection and return forecast.

    Tries all combinations up to *max_order* and *max_seasonal*, picks
    the model with lowest AIC.  Returns None if statsmodels is not
    available or all fits fail.

    Parameters
    ----------
    y : np.ndarray
        Historical observations (oldest-first).
    seasonal_period : int
        Seasonal period (4 for quarterly, 12 for monthly).
    horizon : int
        Number of periods to forecast.

    Returns
    -------
    dict or None
        Keys: ``forecast``, ``lower_68``, ``upper_68``, ``lower_95``,
        ``upper_95``, ``method``, ``order``, ``seasonal_order``,
        ``aic``, ``bic``, ``ljung_box_pvalue``.
    """
    if not HAS_STATSMODELS:
        return None

    best_aic = np.inf
    best_model = None
    best_order = None
    best_sorder = None

    p_range = range(max_order[0] + 1)
    d_range = range(max_order[1] + 1)
    q_range = range(max_order[2] + 1)
    P_range = range(max_seasonal[0] + 1)
    D_range = range(max_seasonal[1] + 1)
    Q_range = range(max_seasonal[2] + 1)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for p, d, q in product(p_range, d_range, q_range):
            for P, D, Q in product(P_range, D_range, Q_range):
                if p + q + P + Q == 0:
                    continue  # skip trivial model
                order = (p, d, q)
                sorder = (P, D, Q, seasonal_period)
                try:
                    model = _SARIMAX(
                        y,
                        order=order,
                        seasonal_order=sorder,
                        enforce_stationarity=False,
                        enforce_invertibility=False,
                    )
                    result = model.fit(disp=False, maxiter=100)
                    if result.aic < best_aic:
                        best_aic = result.aic
                        best_model = result
                        best_order = order
                        best_sorder = sorder
                except Exception:
                    continue

    if best_model is None:
        return None

    # Forecast
    fc = best_model.get_forecast(steps=horizon)
    predicted = fc.predicted_mean
    ci_95_raw = fc.conf_int(alpha=0.05)
    ci_68_raw = fc.conf_int(alpha=0.32)

    # conf_int() may return a DataFrame or ndarray depending on statsmodels version
    def _ci_columns(ci):
        if hasattr(ci, "iloc"):
            return np.array(ci.iloc[:, 0]), np.array(ci.iloc[:, 1])
        ci = np.asarray(ci)
        return ci[:, 0], ci[:, 1]

    ci_68_lo, ci_68_hi = _ci_columns(ci_68_raw)
    ci_95_lo, ci_95_hi = _ci_columns(ci_95_raw)

    # Ljung-Box test on residuals
    try:
        lb = acorr_ljungbox(best_model.resid, lags=[min(10, len(y) // 5)], return_df=True)
        lb_pvalue = float(lb["lb_pvalue"].iloc[0])
    except Exception:
        lb_pvalue = None

    logger.info(
        "SARIMAX selected: order=%s seasonal=%s AIC=%.1f BIC=%.1f LB-p=%.3f",
        best_order,
        best_sorder,
        best_model.aic,
        best_model.bic,
        lb_pvalue if lb_pvalue is not None else -1,
    )

    return {
        "forecast": np.array(predicted),
        "lower_68": ci_68_lo,
        "upper_68": ci_68_hi,
        "lower_95": ci_95_lo,
        "upper_95": ci_95_hi,
        "method": "SARIMAX",
        "order": best_order,
        "seasonal_order": best_sorder[:3] if best_sorder else None,
        "aic": round(float(best_model.aic), 2),
        "bic": round(float(best_model.bic), 2),
        "ljung_box_pvalue": round(lb_pvalue, 4) if lb_pvalue is not None else None,
    }


# ---------------------------------------------------------------------------
# Main Forecaster class
# ---------------------------------------------------------------------------


class Forecaster:
    """Generate quantitative forecasts for Portuguese macroeconomic indicators."""

    def __init__(self, db_path: Optional[str] = None):
        """Load data from the SQLite database.

        Parameters
        ----------
        db_path : str or None
            Path to the SQLite database.  Falls back to the project default.
        """
        self.db_path = str(db_path or DATABASE_PATH)
        logger.info("Forecaster initialised — database: %s", self.db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._load_data()

    # ------------------------------------------------------------------
    # Internal data loading
    # ------------------------------------------------------------------

    def _load_data(self):
        """Read all fact tables into DataFrames."""
        logger.info("Loading historical data from database...")

        self.gdp = pd.read_sql(
            "SELECT date_key, nominal_gdp, real_gdp, gdp_growth_yoy, gdp_per_capita "
            "FROM fact_gdp ORDER BY date_key",
            self._conn,
        )
        self.unemployment = pd.read_sql(
            "SELECT date_key, unemployment_rate, youth_unemployment_rate "
            "FROM fact_unemployment ORDER BY date_key",
            self._conn,
        )
        self.inflation = pd.read_sql(
            "SELECT date_key, hicp, core_inflation FROM fact_inflation ORDER BY date_key",
            self._conn,
        )
        self.interest_rates = pd.read_sql(
            "SELECT date_key, ecb_main_refinancing_rate, euribor_3m, euribor_12m, "
            "portugal_10y_bond_yield FROM fact_interest_rates ORDER BY date_key",
            self._conn,
        )
        self.credit = pd.read_sql(
            "SELECT date_key, total_credit, credit_nfc, credit_households "
            "FROM fact_credit ORDER BY date_key",
            self._conn,
        )
        self.public_debt = pd.read_sql(
            "SELECT date_key, total_debt, debt_to_gdp_ratio, budget_deficit, "
            "budget_deficit_annual FROM fact_public_debt ORDER BY date_key",
            self._conn,
        )

        # Validate that we have data for each pillar
        for name, df in [
            ("GDP", self.gdp),
            ("Unemployment", self.unemployment),
            ("Inflation", self.inflation),
            ("Interest Rates", self.interest_rates),
            ("Credit", self.credit),
            ("Public Debt", self.public_debt),
        ]:
            if df.empty:
                logger.warning("No data loaded for %s — forecasts will be unavailable.", name)

        logger.info(
            "Data loaded — GDP: %d obs, Unemployment: %d obs, Inflation: %d obs, "
            "Rates: %d obs, Credit: %d obs, Debt: %d obs",
            len(self.gdp),
            len(self.unemployment),
            len(self.inflation),
            len(self.interest_rates),
            len(self.credit),
            len(self.public_debt),
        )

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    @staticmethod
    def _quarterly_labels(start_key: str, n: int) -> List[str]:
        """Generate *n* quarterly labels following *start_key* (e.g. '2025-Q4')."""
        year, q = int(start_key[:4]), int(start_key[-1])
        labels = []
        for _ in range(n):
            q += 1
            if q > 4:
                q = 1
                year += 1
            labels.append(f"{year}-Q{q}")
        return labels

    @staticmethod
    def _monthly_labels(start_key: str, n: int) -> List[str]:
        """Generate *n* monthly labels following *start_key* (e.g. '2025-12')."""
        year, month = int(start_key[:4]), int(start_key[5:7])
        labels = []
        for _ in range(n):
            month += 1
            if month > 12:
                month = 1
                year += 1
            labels.append(f"{year}-{month:02d}")
        return labels

    @staticmethod
    def _format_forecast_rows(
        labels, central, lower_68, upper_68, lower_95, upper_95
    ) -> List[dict]:
        """Zip forecast arrays into a list of dictionaries."""
        rows = []
        for i, lbl in enumerate(labels):
            rows.append(
                {
                    "period": lbl,
                    "central": round(float(central[i]), 2),
                    "lower_68": round(float(lower_68[i]), 2),
                    "upper_68": round(float(upper_68[i]), 2),
                    "lower_95": round(float(lower_95[i]), 2),
                    "upper_95": round(float(upper_95[i]), 2),
                }
            )
        return rows

    # ------------------------------------------------------------------
    # Pillar forecasts
    # ------------------------------------------------------------------

    def forecast_gdp(self, horizon: int = 12) -> dict:
        """Forecast GDP for next *horizon* quarters.

        Primary: SARIMAX with automatic order selection (requires statsmodels).
        Fallback: log-linear trend on real GDP.

        Returns
        -------
        dict
            Structured forecast with historical summary, central projections,
            68 % and 95 % confidence bands, and diagnostics.
        """
        log_section(logger, "GDP Forecast")
        y = self.gdp["real_gdp"].dropna().values.astype(float)
        min_obs = 2 * 4 + 1  # 2 * seasonal_period + 1 for SARIMAX
        if len(y) < min_obs:
            logger.warning(
                "Insufficient GDP data for forecasting (%d observations, need %d).", len(y), min_obs
            )
            return {"error": "Insufficient GDP data", "observations": len(y)}
        labels = self._quarterly_labels(self.gdp["date_key"].iloc[-1], horizon)

        # Try SARIMAX first
        sarimax_result = _sarimax_forecast(y, seasonal_period=4, horizon=horizon)
        if sarimax_result is not None:
            forecast_rows = self._format_forecast_rows(
                labels,
                sarimax_result["forecast"],
                sarimax_result["lower_68"],
                sarimax_result["upper_68"],
                sarimax_result["lower_95"],
                sarimax_result["upper_95"],
            )
            output = {
                "indicator": "Real GDP (EUR millions)",
                "method": "SARIMAX",
                "horizon_quarters": horizon,
                "historical_latest": {
                    "period": self.gdp["date_key"].iloc[-1],
                    "value": round(float(y[-1]), 2),
                },
                "forecast": forecast_rows,
                "diagnostics": {
                    "order": sarimax_result["order"],
                    "seasonal_order": sarimax_result["seasonal_order"],
                    "aic": sarimax_result["aic"],
                    "bic": sarimax_result["bic"],
                    "ljung_box_pvalue": sarimax_result["ljung_box_pvalue"],
                },
            }
            logger.info("GDP forecast via SARIMAX — AIC=%.1f", sarimax_result["aic"])
            return output

        # Fallback to log-linear
        logger.info("SARIMAX unavailable — falling back to log-linear trend")
        result = _log_linear_forecast(y, horizon)
        forecast_rows = self._format_forecast_rows(
            labels,
            result["forecast"],
            result["lower_68"],
            result["upper_68"],
            result["lower_95"],
            result["upper_95"],
        )
        output = {
            "indicator": "Real GDP (EUR millions)",
            "method": "log-linear trend (fallback)",
            "horizon_quarters": horizon,
            "historical_latest": {
                "period": self.gdp["date_key"].iloc[-1],
                "value": round(float(y[-1]), 2),
            },
            "forecast": forecast_rows,
            "annual_growth_forecast_pct": round(result["annual_growth"], 2),
            "r_squared": round(result["r_squared"], 4),
        }
        logger.info(
            "GDP forecast (fallback): annual growth ~%.2f %%, R-squared %.4f",
            result["annual_growth"],
            result["r_squared"],
        )
        return output

    def forecast_unemployment(self, horizon: int = 36) -> dict:
        """Forecast unemployment for next *horizon* months.

        Uses exponential smoothing combined with mean-reversion toward the
        long-run historical average.
        """
        log_section(logger, "Unemployment Forecast")
        y = self.unemployment["unemployment_rate"].dropna().values.astype(float)
        if len(y) < 12:
            logger.warning(
                "Insufficient unemployment data for forecasting (%d observations).", len(y)
            )
            return {"error": "Insufficient unemployment data", "observations": len(y)}

        long_run_mean = float(np.mean(y))
        alpha = _optimal_alpha(y)
        smoothed = _exponential_smoothing(y, alpha)
        logger.info("Optimal smoothing alpha: %.3f, long-run mean: %.2f %%", alpha, long_run_mean)

        mr = _mean_reversion_forecast(smoothed, target=long_run_mean, horizon=horizon)

        labels = self._monthly_labels(self.unemployment["date_key"].iloc[-1], horizon)
        forecast_rows = self._format_forecast_rows(
            labels,
            mr["forecast"],
            mr["lower_68"],
            mr["upper_68"],
            mr["lower_95"],
            mr["upper_95"],
        )

        output = {
            "indicator": "Unemployment rate (%)",
            "method": "exponential smoothing + mean-reversion",
            "horizon_months": horizon,
            "historical_latest": {
                "period": self.unemployment["date_key"].iloc[-1],
                "value": round(float(y[-1]), 2),
            },
            "long_run_mean": round(long_run_mean, 2),
            "mean_reversion_speed": round(mr["speed"], 4),
            "smoothing_alpha": round(alpha, 3),
            "forecast": forecast_rows,
        }
        logger.info("Unemployment forecast generated — %d periods", horizon)
        return output

    def forecast_inflation(self, horizon: int = 36) -> dict:
        """Forecast inflation (HICP) for next *horizon* months.

        Primary: SARIMAX with automatic order selection.
        Fallback: mean-reversion toward the ECB 2 % target.
        """
        log_section(logger, "Inflation Forecast")
        y = self.inflation["hicp"].dropna().values.astype(float)
        if len(y) < 12:
            logger.warning("Insufficient inflation data for forecasting (%d observations).", len(y))
            return {"error": "Insufficient inflation data", "observations": len(y)}
        labels = self._monthly_labels(self.inflation["date_key"].iloc[-1], horizon)

        # Try SARIMAX first
        sarimax_result = _sarimax_forecast(y, seasonal_period=12, horizon=horizon)
        if sarimax_result is not None:
            forecast_rows = self._format_forecast_rows(
                labels,
                sarimax_result["forecast"],
                sarimax_result["lower_68"],
                sarimax_result["upper_68"],
                sarimax_result["lower_95"],
                sarimax_result["upper_95"],
            )
            output = {
                "indicator": "HICP inflation (%)",
                "method": "SARIMAX",
                "horizon_months": horizon,
                "historical_latest": {
                    "period": self.inflation["date_key"].iloc[-1],
                    "value": round(float(y[-1]), 2),
                },
                "forecast": forecast_rows,
                "diagnostics": {
                    "order": sarimax_result["order"],
                    "seasonal_order": sarimax_result["seasonal_order"],
                    "aic": sarimax_result["aic"],
                    "bic": sarimax_result["bic"],
                    "ljung_box_pvalue": sarimax_result["ljung_box_pvalue"],
                },
            }
            logger.info("Inflation forecast via SARIMAX — AIC=%.1f", sarimax_result["aic"])
            return output

        # Fallback to mean-reversion
        logger.info("SARIMAX unavailable — falling back to mean-reversion")
        ecb_target = 2.0
        mr = _mean_reversion_forecast(y, target=ecb_target, horizon=horizon)
        forecast_rows = self._format_forecast_rows(
            labels,
            mr["forecast"],
            mr["lower_68"],
            mr["upper_68"],
            mr["lower_95"],
            mr["upper_95"],
        )
        output = {
            "indicator": "HICP inflation (%)",
            "method": "mean-reversion to ECB target (fallback)",
            "ecb_target_pct": ecb_target,
            "horizon_months": horizon,
            "historical_latest": {
                "period": self.inflation["date_key"].iloc[-1],
                "value": round(float(y[-1]), 2),
            },
            "mean_reversion_speed": round(mr["speed"], 4),
            "sigma": round(mr["sigma"], 4),
            "forecast": forecast_rows,
        }
        logger.info("Inflation forecast (fallback) — target %.1f %%", ecb_target)
        return output

    def forecast_interest_rates(self, horizon: int = 36) -> dict:
        """Forecast ECB rate and Euribor 12M for next *horizon* months.

        Both series are modelled with mean-reversion toward their respective
        long-run averages.
        """
        log_section(logger, "Interest Rates Forecast")

        ecb = self.interest_rates["ecb_main_refinancing_rate"].dropna().values.astype(float)
        euribor = self.interest_rates["euribor_12m"].dropna().values.astype(float)
        if len(ecb) < 12 or len(euribor) < 12:
            logger.warning("Insufficient interest rate data for forecasting.")
            return {"error": "Insufficient interest rate data"}

        ecb_lr = float(np.mean(ecb))
        euribor_lr = float(np.mean(euribor))

        mr_ecb = _mean_reversion_forecast(ecb, target=ecb_lr, horizon=horizon)
        mr_euribor = _mean_reversion_forecast(euribor, target=euribor_lr, horizon=horizon)

        labels = self._monthly_labels(self.interest_rates["date_key"].iloc[-1], horizon)

        output = {
            "indicator": "Interest Rates",
            "method": "mean-reversion",
            "horizon_months": horizon,
            "ecb_rate": {
                "latest": round(float(ecb[-1]), 3),
                "long_run_mean": round(ecb_lr, 3),
                "forecast": self._format_forecast_rows(
                    labels,
                    mr_ecb["forecast"],
                    mr_ecb["lower_68"],
                    mr_ecb["upper_68"],
                    mr_ecb["lower_95"],
                    mr_ecb["upper_95"],
                ),
            },
            "euribor_12m": {
                "latest": round(float(euribor[-1]), 3),
                "long_run_mean": round(euribor_lr, 3),
                "forecast": self._format_forecast_rows(
                    labels,
                    mr_euribor["forecast"],
                    mr_euribor["lower_68"],
                    mr_euribor["upper_68"],
                    mr_euribor["lower_95"],
                    mr_euribor["upper_95"],
                ),
            },
        }
        logger.info(
            "Interest rates forecast generated — ECB LR: %.3f, Euribor LR: %.3f",
            ecb_lr,
            euribor_lr,
        )
        return output

    def forecast_credit(self, horizon: int = 36) -> dict:
        """Forecast total credit for next *horizon* months.

        Uses a log-linear trend fitted to the most recent 3 years (36 months).
        """
        log_section(logger, "Credit Forecast")
        y_all = self.credit["total_credit"].dropna().values.astype(float)
        if len(y_all) < 12:
            logger.warning(
                "Insufficient credit data for forecasting (%d observations).", len(y_all)
            )
            return {"error": "Insufficient credit data", "observations": len(y_all)}
        y = y_all[-36:]  # use recent 3 years only

        result = _log_linear_forecast(y, horizon)
        # Adjust annual growth label — monthly series, so annualise by *12
        annual_growth = float(np.exp(result["slope"] * 12) - 1) * 100

        labels = self._monthly_labels(self.credit["date_key"].iloc[-1], horizon)
        forecast_rows = self._format_forecast_rows(
            labels,
            result["forecast"],
            result["lower_68"],
            result["upper_68"],
            result["lower_95"],
            result["upper_95"],
        )

        output = {
            "indicator": "Total Credit (EUR millions)",
            "method": "log-linear trend (recent 3 years)",
            "horizon_months": horizon,
            "historical_latest": {
                "period": self.credit["date_key"].iloc[-1],
                "value": round(float(y_all[-1]), 2),
            },
            "annual_growth_forecast_pct": round(annual_growth, 2),
            "r_squared": round(result["r_squared"], 4),
            "forecast": forecast_rows,
        }
        logger.info("Credit forecast: annual growth ~%.2f %%", annual_growth)
        return output

    def forecast_public_debt(self, horizon: int = 12) -> dict:
        """Forecast debt-to-GDP ratio for next *horizon* quarters.

        Uses the debt dynamics equation:
            d(t+1) = d(t) * (1 + r) / (1 + g) - pb
        where *r* is the implicit interest rate, *g* is nominal GDP growth,
        and *pb* is the primary balance as a share of GDP.
        """
        log_section(logger, "Public Debt Forecast")

        debt_ratio = self.public_debt["debt_to_gdp_ratio"].dropna().values.astype(float)
        nom_gdp = self.gdp["nominal_gdp"].dropna().values.astype(float)
        if len(debt_ratio) < 4 or len(nom_gdp) < 5:
            logger.warning("Insufficient public debt data for forecasting.")
            return {"error": "Insufficient public debt data"}

        # --- Budget deficit fallback ---
        budget = self.public_debt["budget_deficit"].dropna().values.astype(float)
        if len(budget) < 4 and "budget_deficit_annual" in self.public_debt.columns:
            budget_annual = self.public_debt["budget_deficit_annual"].dropna().values.astype(float)
            if len(budget_annual) >= 4:
                logger.info("budget_deficit has < 4 values; falling back to budget_deficit_annual")
                budget = budget_annual
        if len(budget) < 1:
            logger.warning("No budget deficit data available — assuming balanced budget (0.0 %%)")
            budget = np.array([0.0])

        # Derive implicit parameters from the most recent data
        latest_debt = float(debt_ratio[-1])
        latest_budget = float(budget[-1])  # as % of GDP
        total_debt_eur = self.public_debt["total_debt"].dropna().values.astype(float)  # noqa: F841

        # --- Bond yield with empty guard ---
        bond_yield = self.interest_rates["portugal_10y_bond_yield"].dropna().values.astype(float)
        if len(bond_yield) == 0:
            logger.warning("No bond yield data — defaulting to 3 %% annual rate")
            r_annual = 0.03
        else:
            r_annual = float(bond_yield[-1]) / 100.0
        r_q = (1.0 + r_annual) ** 0.25 - 1.0

        # --- Nominal GDP quarterly growth with NaN/inf guard ---
        gdp_growth = np.diff(nom_gdp[-5:]) / nom_gdp[-5:-1]
        gdp_growth_clean = gdp_growth[np.isfinite(gdp_growth)]
        if len(gdp_growth_clean) == 0:
            logger.warning("GDP growth values are all non-finite — defaulting to 0.5 %% quarterly")
            g_q = 0.005
        else:
            g_q = float(np.mean(gdp_growth_clean))
        # Clamp denominator away from zero to prevent division by zero
        if abs(1.0 + g_q) < 1e-6:
            logger.warning("1 + g_q near zero (%.6f) — clamping to 1e-6", 1.0 + g_q)
            g_q = 1e-6 - 1.0 if g_q < 0 else 0.005

        # Primary balance (quarterly, approximate) — budget deficit includes interest
        # Use the budget deficit directly as an approximation
        pb_q = float(latest_budget) / 4.0  # quarterly share

        labels = self._quarterly_labels(self.public_debt["date_key"].iloc[-1], horizon)

        # Simulate path with overflow protection
        forecast_central = np.empty(horizon)
        d = latest_debt
        max_debt_ratio = 500.0  # reasonable upper bound
        for h in range(horizon):
            d = d * (1.0 + r_q) / (1.0 + g_q) - pb_q
            if not np.isfinite(d):
                d = latest_debt
            d = min(d, max_debt_ratio)
            forecast_central[h] = d

        # Uncertainty: historical volatility of quarterly debt-ratio changes
        debt_changes = np.diff(debt_ratio)
        sigma_q = float(np.std(debt_changes)) if len(debt_changes) > 1 else 1.0
        h_arr = np.arange(1, horizon + 1)
        std_h = sigma_q * np.sqrt(h_arr)

        forecast_rows = self._format_forecast_rows(
            labels,
            forecast_central,
            forecast_central - 1.0 * std_h,
            forecast_central + 1.0 * std_h,
            forecast_central - 1.96 * std_h,
            forecast_central + 1.96 * std_h,
        )

        output = {
            "indicator": "Debt-to-GDP ratio (%)",
            "method": "debt dynamics equation",
            "horizon_quarters": horizon,
            "assumptions": {
                "implicit_annual_rate_pct": round(r_annual * 100, 2),
                "quarterly_gdp_growth_pct": round(g_q * 100, 2),
                "primary_balance_gdp_pct": round(float(latest_budget), 2),
            },
            "historical_latest": {
                "period": self.public_debt["date_key"].iloc[-1],
                "value": round(latest_debt, 2),
            },
            "forecast": forecast_rows,
        }
        logger.info(
            "Debt forecast: r=%.2f %%, g=%.2f %%, pb=%.2f %% of GDP",
            r_annual * 100,
            g_q * 100,
            latest_budget,
        )
        return output

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------

    def generate_all_forecasts(self) -> dict:
        """Run all pillar forecasts and return a combined dictionary."""
        log_section(logger, "Running All Forecasts")
        results = {}
        for name, method in [
            ("gdp", self.forecast_gdp),
            ("unemployment", self.forecast_unemployment),
            ("inflation", self.forecast_inflation),
            ("interest_rates", self.forecast_interest_rates),
            ("credit", self.forecast_credit),
            ("public_debt", self.forecast_public_debt),
        ]:
            try:
                results[name] = method()
            except Exception as exc:
                logger.error("Forecast failed for %s: %s", name, exc)
                results[name] = {"error": str(exc)}
        logger.info("All forecasts complete — %d pillars", len(results))
        return results

    def close(self):
        """Close the database connection."""
        self._conn.close()
        logger.info("Database connection closed.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("=" * 72)
    print("  PORTUGAL DATA INTELLIGENCE — MACROECONOMIC FORECASTS")
    print("=" * 72)

    fc = Forecaster()
    all_forecasts = fc.generate_all_forecasts()

    for pillar, data in all_forecasts.items():
        print(f"\n{'-' * 72}")
        print(f"  {pillar.upper()}")
        print(f"{'-' * 72}")

        if "error" in data:
            print(f"  ERROR: {data['error']}")
            continue

        # Print method and latest value
        print(f"  Method   : {data.get('method', 'n/a')}")
        latest = data.get("historical_latest", {})
        print(f"  Latest   : {latest.get('period', '?')} = {latest.get('value', '?')}")

        # Print diagnostics if available
        if "annual_growth_forecast_pct" in data:
            print(f"  Annual growth forecast: {data['annual_growth_forecast_pct']} %")
        if "r_squared" in data:
            print(f"  R-squared: {data['r_squared']}")
        if "long_run_mean" in data:
            print(f"  Long-run mean: {data['long_run_mean']}")
        if "assumptions" in data:
            print(f"  Assumptions: {json.dumps(data['assumptions'], indent=4)}")

        # Print selected forecast rows (first 4 and last 2)
        fc_rows = data.get("forecast", [])
        if not fc_rows and "ecb_rate" in data:
            fc_rows = data["ecb_rate"].get("forecast", [])
            print("  (showing ECB rate forecast)")

        if fc_rows:
            print(f"\n  {'Period':<12} {'Central':>12} {'68% band':>20} {'95% band':>20}")
            print(f"  {'-' * 64}")
            display_rows = fc_rows[:4] + (fc_rows[-2:] if len(fc_rows) > 6 else [])
            shown_indices = set()
            for i, row in enumerate(fc_rows[:4]):
                shown_indices.add(i)
                print(
                    f"  {row['period']:<12} {row['central']:>12,.2f} "
                    f"[{row['lower_68']:>8,.2f}, {row['upper_68']:>8,.2f}] "
                    f"[{row['lower_95']:>8,.2f}, {row['upper_95']:>8,.2f}]"
                )
            if len(fc_rows) > 6:
                print(f"  {'...':^64}")
                for row in fc_rows[-2:]:
                    print(
                        f"  {row['period']:<12} {row['central']:>12,.2f} "
                        f"[{row['lower_68']:>8,.2f}, {row['upper_68']:>8,.2f}] "
                        f"[{row['lower_95']:>8,.2f}, {row['upper_95']:>8,.2f}]"
                    )

    fc.close()
    print(f"\n{'=' * 72}")
    print("  Forecasts complete.")
    print(f"{'=' * 72}")
