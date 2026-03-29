"""
Portugal Data Intelligence — Forecast Backtesting Module
==========================================================
Evaluates forecast accuracy using expanding-window cross-validation.
Computes MAE, RMSE, MAPE, and directional accuracy for each forecast
origin.

Usage:
    from src.analysis.backtesting import run_backtests
    results = run_backtests()
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from config.settings import DATABASE_PATH, REPORTS_DIR
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)


def _mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def _mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    mask = actual != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def _directional_accuracy(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Fraction of periods where the predicted direction (up/down) was correct."""
    if len(actual) < 2:
        return float("nan")
    actual_dir = np.diff(actual) >= 0
    pred_dir = np.diff(predicted) >= 0
    n = min(len(actual_dir), len(pred_dir))
    if n == 0:
        return float("nan")
    return float(np.mean(actual_dir[:n] == pred_dir[:n]) * 100)


def expanding_window_backtest(
    series: np.ndarray,
    forecast_fn: Callable[[np.ndarray, int], np.ndarray],
    min_train: int = 20,
    step_ahead: int = 4,
    step_size: int = 4,
) -> Dict[str, Any]:
    """Run expanding-window cross-validation on a time series.

    Parameters
    ----------
    series : np.ndarray
        Full historical series.
    forecast_fn : callable
        Function(training_data, horizon) -> np.ndarray of predictions.
    min_train : int
        Minimum training set size before first evaluation.
    step_ahead : int
        Number of periods to forecast at each origin.
    step_size : int
        Number of periods to advance between origins.

    Returns
    -------
    dict
        Aggregated and per-origin metrics.
    """
    n = len(series)
    origins = []
    all_actual = []
    all_predicted = []

    t = min_train
    while t + step_ahead <= n:
        train = series[:t]
        actual = series[t : t + step_ahead]

        try:
            predicted = forecast_fn(train, step_ahead)
            predicted = predicted[: len(actual)]  # trim if needed
        except Exception as exc:
            logger.warning("Forecast failed at origin t=%d: %s", t, exc)
            t += step_size
            continue

        origins.append(
            {
                "train_end": t - 1,
                "forecast_start": t,
                "forecast_end": t + len(actual) - 1,
                "mae": round(_mae(actual, predicted), 4),
                "rmse": round(_rmse(actual, predicted), 4),
                "mape": round(_mape(actual, predicted), 2),
            }
        )
        all_actual.append(actual)
        all_predicted.append(predicted)
        t += step_size

    if not origins:
        return {"error": "No valid forecast origins", "origins": []}

    flat_actual = np.concatenate(all_actual)
    flat_predicted = np.concatenate(all_predicted)

    return {
        "n_origins": len(origins),
        "step_ahead": step_ahead,
        "aggregate": {
            "mae": round(_mae(flat_actual, flat_predicted), 4),
            "rmse": round(_rmse(flat_actual, flat_predicted), 4),
            "mape": round(_mape(flat_actual, flat_predicted), 2),
            "directional_accuracy_pct": round(
                _directional_accuracy(flat_actual, flat_predicted), 1
            ),
        },
        "origins": origins,
    }


def _log_linear_predict(train: np.ndarray, horizon: int) -> np.ndarray:
    """Simple log-linear predictor for backtesting."""
    from scipy import stats

    t = np.arange(len(train))
    log_y = np.log(np.clip(train, 1e-6, None))
    slope, intercept, *_ = stats.linregress(t, log_y)
    t_fwd = np.arange(len(train), len(train) + horizon)
    result: np.ndarray = np.exp(intercept + slope * t_fwd)
    return result


def _mean_reversion_predict(train: np.ndarray, horizon: int) -> np.ndarray:
    """Simple mean-reversion predictor for backtesting."""
    target = float(np.mean(train))
    speed = 0.05
    dy = np.diff(train)
    x = target - train[:-1]
    if np.var(x) > 1e-12:
        from scipy import stats

        s, *_ = stats.linregress(x, dy)
        speed = max(float(s), 0.001)

    forecast = np.empty(horizon)
    current = float(train[-1])
    for h in range(horizon):
        current += speed * (target - current)
        forecast[h] = current
    return forecast


def run_backtests(db_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Run backtests for GDP and unemployment from the database.

    Returns
    -------
    dict
        Pillar name -> backtest results.
    """
    log_section(logger, "FORECAST BACKTESTING")

    from src.utils.db import get_connection

    results = {}

    with get_connection(db_path) as conn:
        # GDP (quarterly, 4-step-ahead)
        try:
            gdp = (
                pd.read_sql("SELECT real_gdp FROM fact_gdp ORDER BY date_key", conn)["real_gdp"]
                .dropna()
                .values.astype(float)
            )

            results["gdp"] = expanding_window_backtest(
                gdp,
                forecast_fn=_log_linear_predict,
                min_train=20,
                step_ahead=4,
                step_size=4,
            )
            logger.info(
                "GDP backtest: %d origins, MAE=%.2f, MAPE=%.1f%%",
                results["gdp"]["n_origins"],
                results["gdp"]["aggregate"]["mae"],
                results["gdp"]["aggregate"]["mape"],
            )
        except Exception as exc:
            logger.error("GDP backtest failed: %s", exc)
            results["gdp"] = {"error": str(exc)}

        # Unemployment (monthly, 12-step-ahead)
        try:
            unemp = (
                pd.read_sql(
                    "SELECT unemployment_rate FROM fact_unemployment ORDER BY date_key",
                    conn,
                )["unemployment_rate"]
                .dropna()
                .values.astype(float)
            )

            results["unemployment"] = expanding_window_backtest(
                unemp,
                forecast_fn=_mean_reversion_predict,
                min_train=36,
                step_ahead=12,
                step_size=12,
            )
            logger.info(
                "Unemployment backtest: %d origins, MAE=%.2f, MAPE=%.1f%%",
                results["unemployment"]["n_origins"],
                results["unemployment"]["aggregate"]["mae"],
                results["unemployment"]["aggregate"]["mape"],
            )
        except Exception as exc:
            logger.error("Unemployment backtest failed: %s", exc)
            results["unemployment"] = {"error": str(exc)}

    # Save results
    out_path = REPORTS_DIR / "backtesting_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("Backtesting results saved to %s", out_path)

    return results
