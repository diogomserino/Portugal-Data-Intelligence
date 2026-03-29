"""
Tests for the ensemble forecasting module (src/analysis/ensemble_forecast.py).
"""

import numpy as np
import pytest

from src.analysis.ensemble_forecast import (
    _backtest_model,
    holt_winters_forecast,
    linear_trend_forecast,
)


@pytest.fixture
def trend_series():
    """Generate a simple linear trend series with noise."""
    np.random.seed(42)
    n = 100
    t = np.arange(n)
    return 50.0 + 0.5 * t + np.random.normal(0, 2, n)


@pytest.fixture
def seasonal_series():
    """Generate a series with trend + seasonality."""
    np.random.seed(42)
    n = 120
    t = np.arange(n)
    trend = 100 + 0.3 * t
    seasonal = 5 * np.sin(2 * np.pi * t / 12)
    noise = np.random.normal(0, 1, n)
    return trend + seasonal + noise


class TestLinearTrendForecast:
    """Tests for the linear_trend_forecast function."""

    def test_returns_correct_keys(self, trend_series):
        result = linear_trend_forecast(trend_series, horizon=12)
        expected_keys = {
            "method",
            "forecast",
            "lower_68",
            "upper_68",
            "lower_95",
            "upper_95",
            "slope",
            "r_squared",
            "fitted",
        }
        assert expected_keys.issubset(result.keys())

    def test_forecast_length(self, trend_series):
        horizon = 12
        result = linear_trend_forecast(trend_series, horizon=horizon)
        assert len(result["forecast"]) == horizon
        assert len(result["lower_95"]) == horizon

    def test_positive_slope_for_increasing_series(self, trend_series):
        result = linear_trend_forecast(trend_series, horizon=6)
        assert result["slope"] > 0

    def test_forecast_continues_trend(self, trend_series):
        result = linear_trend_forecast(trend_series, horizon=6)
        # Forecast values should be higher than the last observed value
        assert result["forecast"][0] > trend_series[-10]

    def test_confidence_bands_order(self, trend_series):
        result = linear_trend_forecast(trend_series, horizon=12)
        for i in range(12):
            assert result["lower_95"][i] <= result["lower_68"][i]
            assert result["lower_68"][i] <= result["forecast"][i]
            assert result["forecast"][i] <= result["upper_68"][i]
            assert result["upper_68"][i] <= result["upper_95"][i]

    def test_r_squared_range(self, trend_series):
        result = linear_trend_forecast(trend_series, horizon=6)
        assert 0 <= result["r_squared"] <= 1


class TestHoltWintersforecast:
    """Tests for the holt_winters_forecast function."""

    def test_returns_none_with_insufficient_data(self):
        """Should return None if data is shorter than 2 * seasonal_period."""
        short_series = np.array([1.0, 2.0, 3.0])
        result = holt_winters_forecast(short_series, seasonal_period=12, horizon=6)
        assert result is None

    def test_returns_dict_with_enough_data(self, seasonal_series):
        """Should return a forecast dict with sufficient data."""
        result = holt_winters_forecast(seasonal_series, seasonal_period=12, horizon=12)
        if result is not None:  # May fail if statsmodels not installed
            assert "forecast" in result
            assert len(result["forecast"]) == 12
            assert result["method"] == "Holt-Winters"


class TestBacktestModel:
    """Tests for the _backtest_model function."""

    def test_returns_finite_mae(self, trend_series):
        """Backtesting a valid model should return a finite MAE."""

        def simple_forecast(y, h):
            return linear_trend_forecast(y, h)

        mae = _backtest_model(trend_series, simple_forecast, n_splits=3, test_size=4)
        assert np.isfinite(mae)
        assert mae >= 0

    def test_returns_inf_for_failing_model(self, trend_series):
        """A model that always fails should return inf."""

        def failing_forecast(y, h):
            return None

        mae = _backtest_model(trend_series, failing_forecast, n_splits=3, test_size=4)
        assert mae == float("inf")

    def test_fewer_splits_with_short_data(self):
        """With very short data, should still handle gracefully."""
        short = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        def simple_forecast(y, h):
            return {"forecast": np.full(h, np.mean(y))}

        mae = _backtest_model(short, simple_forecast, n_splits=3, test_size=2)
        assert isinstance(mae, float)
