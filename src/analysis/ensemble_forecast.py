"""
Portugal Data Intelligence — Ensemble Forecasting Module
=========================================================
Extends the base forecasting with additional models and ensemble methods:

1. **Holt-Winters** (Triple Exponential Smoothing) — captures trend + seasonality
2. **Linear Regression with features** — trend + cyclical components
3. **Ensemble** — weighted average of all available models based on backtesting

The ensemble automatically weights models by their inverse MAE from
expanding-window cross-validation on the most recent data.

Usage:
    from src.analysis.ensemble_forecast import EnsembleForecaster
    ef = EnsembleForecaster()
    result = ef.forecast_pillar("gdp", horizon=12)
"""

import sqlite3
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from config.settings import DATABASE_PATH
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)

# Optional: Holt-Winters from statsmodels
try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing as _HoltWinters

    HAS_HOLTWINTERS = True
except ImportError:
    HAS_HOLTWINTERS = False

# Re-use existing forecasting helpers
from src.analysis.forecasting import (
    _exponential_smoothing,
    _log_linear_forecast,
    _mean_reversion_forecast,
    _optimal_alpha,
    _sarimax_forecast,
)

# ---------------------------------------------------------------------------
# Individual model wrappers
# ---------------------------------------------------------------------------


def holt_winters_forecast(
    y: np.ndarray,
    seasonal_period: int = 4,
    horizon: int = 12,
    trend: str = "add",
    seasonal: str = "add",
) -> Optional[dict]:
    """Triple exponential smoothing (Holt-Winters) forecast.

    Parameters
    ----------
    y : np.ndarray
        Historical observations (oldest-first).
    seasonal_period : int
        Seasonal period (4 for quarterly, 12 for monthly).
    horizon : int
        Forecast horizon.

    Returns
    -------
    dict or None
        Forecast with confidence bands, or None if fitting fails.
    """
    if not HAS_HOLTWINTERS:
        return None
    if len(y) < 2 * seasonal_period:
        logger.warning("Insufficient data for Holt-Winters (%d < %d).", len(y), 2 * seasonal_period)
        return None

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = _HoltWinters(
                y,
                trend=trend,
                seasonal=seasonal,
                seasonal_periods=seasonal_period,
            )
            fit = model.fit(optimized=True, use_brute=True)

        forecast = fit.forecast(horizon)
        residuals = y - fit.fittedvalues
        sigma = float(np.std(residuals, ddof=1))

        h_arr = np.arange(1, horizon + 1)
        std_h = sigma * np.sqrt(h_arr)

        return {
            "method": "Holt-Winters",
            "forecast": np.array(forecast),
            "lower_68": forecast - 1.0 * std_h,
            "upper_68": forecast + 1.0 * std_h,
            "lower_95": forecast - 1.96 * std_h,
            "upper_95": forecast + 1.96 * std_h,
            "aic": round(float(fit.aic), 2) if hasattr(fit, "aic") else None,
            "fitted": fit.fittedvalues,
        }
    except Exception as exc:
        logger.warning("Holt-Winters failed: %s", exc)
        return None


def linear_trend_forecast(
    y: np.ndarray,
    horizon: int = 12,
) -> dict:
    """Linear trend extrapolation with seasonal dummies.

    A simple but robust baseline model:
        y_t = a + b*t + e_t

    Parameters
    ----------
    y : np.ndarray
        Historical observations.
    horizon : int
        Forecast horizon.

    Returns
    -------
    dict
        Forecast with confidence bands.
    """
    n = len(y)
    t = np.arange(n)

    slope, intercept, r_value, _p, std_err = stats.linregress(t, y)
    residuals = y - (intercept + slope * t)
    sigma = float(np.std(residuals, ddof=2))

    t_fwd = np.arange(n, n + horizon)
    forecast = intercept + slope * t_fwd

    h_arr = np.arange(1, horizon + 1)
    std_h = sigma * np.sqrt(1 + h_arr / n)

    return {
        "method": "Linear Trend",
        "forecast": forecast,
        "lower_68": forecast - 1.0 * std_h,
        "upper_68": forecast + 1.0 * std_h,
        "lower_95": forecast - 1.96 * std_h,
        "upper_95": forecast + 1.96 * std_h,
        "slope": float(slope),
        "r_squared": float(r_value**2),
        "fitted": intercept + slope * t,
    }


# ---------------------------------------------------------------------------
# Backtesting for model weighting
# ---------------------------------------------------------------------------


def _backtest_model(
    y: np.ndarray,
    forecast_fn,
    n_splits: int = 3,
    test_size: int = 4,
) -> float:
    """Expanding-window backtest returning mean absolute error.

    Parameters
    ----------
    y : np.ndarray
        Full historical series.
    forecast_fn : callable
        Function(y_train, horizon) -> dict with "forecast" key.
    n_splits : int
        Number of train/test splits.
    test_size : int
        Number of periods in each test window.

    Returns
    -------
    float
        Mean absolute error across all splits. Returns inf on failure.
    """
    n = len(y)
    min_train = max(12, n - n_splits * test_size)
    errors = []

    for i in range(n_splits):
        train_end = n - (n_splits - i) * test_size
        if train_end < min_train:
            continue
        y_train = y[:train_end]
        y_test = y[train_end : train_end + test_size]

        try:
            result = forecast_fn(y_train, test_size)
            if result is None:
                return float("inf")
            pred = result["forecast"][: len(y_test)]
            mae = float(np.mean(np.abs(y_test - pred)))
            errors.append(mae)
        except Exception:
            return float("inf")

    return float(np.mean(errors)) if errors else float("inf")


# ---------------------------------------------------------------------------
# Ensemble Forecaster
# ---------------------------------------------------------------------------

PILLAR_CONFIG = {
    "gdp": {
        "table": "fact_gdp",
        "column": "real_gdp",
        "seasonal_period": 4,
        "granularity": "quarterly",
    },
    "unemployment": {
        "table": "fact_unemployment",
        "column": "unemployment_rate",
        "seasonal_period": 12,
        "granularity": "monthly",
    },
    "inflation": {
        "table": "fact_inflation",
        "column": "hicp",
        "seasonal_period": 12,
        "granularity": "monthly",
    },
    "interest_rates": {
        "table": "fact_interest_rates",
        "column": "ecb_main_refinancing_rate",
        "seasonal_period": 12,
        "granularity": "monthly",
    },
    "credit": {
        "table": "fact_credit",
        "column": "total_credit",
        "seasonal_period": 12,
        "granularity": "monthly",
    },
    "public_debt": {
        "table": "fact_public_debt",
        "column": "debt_to_gdp_ratio",
        "seasonal_period": 4,
        "granularity": "quarterly",
    },
}


class EnsembleForecaster:
    """Multi-model ensemble forecaster with automatic weighting.

    Runs multiple forecasting models on the same series and combines
    them using inverse-MAE weights from backtesting.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DATABASE_PATH)
        self._conn = sqlite3.connect(self.db_path)
        logger.info("EnsembleForecaster initialised — database: %s", self.db_path)

    def _load_series(self, pillar: str) -> Tuple[np.ndarray, pd.DataFrame]:
        """Load the primary time series for a pillar."""
        config = PILLAR_CONFIG.get(pillar)
        if config is None:
            raise ValueError(f"Unknown pillar: {pillar}")

        df = pd.read_sql(
            f"SELECT date_key, {config['column']} FROM {config['table']} ORDER BY date_key",
            self._conn,
        )
        y = df[config["column"]].dropna().values.astype(float)
        return y, df

    def forecast_pillar(self, pillar: str, horizon: int = 12) -> dict:
        """Generate ensemble forecast for a pillar.

        Parameters
        ----------
        pillar : str
            One of: gdp, unemployment, inflation, interest_rates, credit, public_debt.
        horizon : int
            Number of periods to forecast.

        Returns
        -------
        dict
            Ensemble forecast with individual model results and weights.
        """
        log_section(logger, f"Ensemble Forecast: {pillar.upper()}")

        config = PILLAR_CONFIG[pillar]
        y, df = self._load_series(pillar)

        if len(y) < 12:
            return {"error": f"Insufficient data for {pillar}", "observations": len(y)}

        seasonal_period = config["seasonal_period"]

        # --- Run all models ---
        models = {}

        # 1. SARIMAX
        sarimax = _sarimax_forecast(y, seasonal_period=seasonal_period, horizon=horizon)
        if sarimax is not None:
            models["SARIMAX"] = sarimax

        # 2. Holt-Winters
        hw = holt_winters_forecast(y, seasonal_period=seasonal_period, horizon=horizon)
        if hw is not None:
            models["Holt-Winters"] = hw

        # 3. Linear Trend
        lt = linear_trend_forecast(y, horizon=horizon)
        models["Linear Trend"] = lt

        # 4. Mean Reversion (for rates and ratios)
        if pillar in ("unemployment", "interest_rates", "inflation", "public_debt"):
            target = float(np.mean(y))
            mr = _mean_reversion_forecast(y, target=target, horizon=horizon)
            models["Mean Reversion"] = mr

        # 5. Log-Linear (for positive series)
        if pillar in ("gdp", "credit") and np.all(y > 0):
            ll = _log_linear_forecast(y, horizon=horizon)
            models["Log-Linear"] = ll

        if not models:
            return {"error": "All models failed"}

        # --- Backtest each model to get weights ---
        logger.info("Backtesting %d models for weighting...", len(models))
        mae_scores = {}

        def _make_sarimax_fn(sp):
            def fn(y_train, h):
                return _sarimax_forecast(y_train, sp, h)

            return fn

        def _make_hw_fn(sp):
            def fn(y_train, h):
                return holt_winters_forecast(y_train, sp, h)

            return fn

        def _make_linear_fn():
            def fn(y_train, h):
                return linear_trend_forecast(y_train, h)

            return fn

        def _make_mr_fn(t):
            def fn(y_train, h):
                return _mean_reversion_forecast(y_train, t, horizon=h)

            return fn

        def _make_loglin_fn():
            def fn(y_train, h):
                return _log_linear_forecast(y_train, h) if np.all(y_train > 0) else None

            return fn

        for name in models:
            if name == "SARIMAX":
                fn = _make_sarimax_fn(seasonal_period)
            elif name == "Holt-Winters":
                fn = _make_hw_fn(seasonal_period)
            elif name == "Linear Trend":
                fn = _make_linear_fn()
            elif name == "Mean Reversion":
                target = float(np.mean(y))
                fn = _make_mr_fn(target)
            elif name == "Log-Linear":
                fn = _make_loglin_fn()
            else:
                continue

            mae = _backtest_model(y, fn, n_splits=3, test_size=seasonal_period)
            mae_scores[name] = mae
            logger.info("  %s: MAE = %.4f", name, mae)

        # Compute inverse-MAE weights (exclude models with inf MAE)
        valid_models = {k: v for k, v in mae_scores.items() if np.isfinite(v) and v > 0}
        if not valid_models:
            # Fall back to equal weights
            valid_models = {k: 1.0 for k in models}

        inv_mae = {k: 1.0 / v for k, v in valid_models.items()}
        total_inv = sum(inv_mae.values())
        weights = {k: round(v / total_inv, 4) for k, v in inv_mae.items()}

        logger.info("Model weights: %s", weights)

        # --- Compute ensemble forecast ---
        ensemble_forecast = np.zeros(horizon)
        ensemble_lower_68 = np.zeros(horizon)
        ensemble_upper_68 = np.zeros(horizon)
        ensemble_lower_95 = np.zeros(horizon)
        ensemble_upper_95 = np.zeros(horizon)

        for name, weight in weights.items():
            m = models[name]
            ensemble_forecast += weight * m["forecast"][:horizon]
            ensemble_lower_68 += weight * m["lower_68"][:horizon]
            ensemble_upper_68 += weight * m["upper_68"][:horizon]
            ensemble_lower_95 += weight * m["lower_95"][:horizon]
            ensemble_upper_95 += weight * m["upper_95"][:horizon]

        # --- Build output ---
        individual_results = {}
        for name, m in models.items():
            individual_results[name] = {
                "weight": weights.get(name, 0),
                "mae": round(mae_scores.get(name, float("inf")), 4),
                "forecast_mean": round(float(np.mean(m["forecast"][:horizon])), 2),
            }

        return {
            "pillar": pillar,
            "method": "Ensemble (inverse-MAE weighted)",
            "models_used": list(weights.keys()),
            "horizon": horizon,
            "granularity": config["granularity"],
            "historical_latest": {
                "period": df["date_key"].iloc[-1] if not df.empty else None,
                "value": round(float(y[-1]), 2),
            },
            "ensemble_forecast": [round(float(v), 2) for v in ensemble_forecast],
            "lower_68": [round(float(v), 2) for v in ensemble_lower_68],
            "upper_68": [round(float(v), 2) for v in ensemble_upper_68],
            "lower_95": [round(float(v), 2) for v in ensemble_lower_95],
            "upper_95": [round(float(v), 2) for v in ensemble_upper_95],
            "individual_models": individual_results,
            "weights": weights,
        }

    def forecast_all(self) -> dict:
        """Run ensemble forecast for all pillars."""
        log_section(logger, "Running All Ensemble Forecasts")
        results = {}
        for pillar in PILLAR_CONFIG:
            try:
                results[pillar] = self.forecast_pillar(pillar)
            except Exception as exc:
                logger.error("Ensemble forecast failed for %s: %s", pillar, exc)
                results[pillar] = {"error": str(exc)}
        return results

    def close(self):
        """Close the database connection."""
        self._conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("=" * 72)
    print("  PORTUGAL DATA INTELLIGENCE — ENSEMBLE FORECASTS")
    print("=" * 72)

    ef = EnsembleForecaster()
    results = ef.forecast_all()

    for pillar, data in results.items():
        print(f"\n{'-' * 72}")
        print(f"  {pillar.upper()}")
        print(f"{'-' * 72}")

        if "error" in data:
            print(f"  ERROR: {data['error']}")
            continue

        print(f"  Method: {data['method']}")
        print(f"  Models: {', '.join(data['models_used'])}")
        print(f"  Weights: {data['weights']}")
        print(f"  Latest: {data['historical_latest']}")
        print(f"  Forecast (first 4): {data['ensemble_forecast'][:4]}")

        for name, info in data["individual_models"].items():
            print(f"    {name}: weight={info['weight']:.3f}, MAE={info['mae']:.4f}")

    ef.close()
    print(f"\n{'=' * 72}")
