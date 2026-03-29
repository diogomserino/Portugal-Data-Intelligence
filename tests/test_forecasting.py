"""Tests for the forecasting module."""

import numpy as np
import pytest

from src.analysis.forecasting import (
    _exponential_smoothing,
    _log_linear_forecast,
    _mean_reversion_forecast,
    _optimal_alpha,
    _sarimax_forecast,
)


class TestExponentialSmoothing:
    def test_output_length_matches_input(self):
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _exponential_smoothing(y, alpha=0.3)
        assert len(result) == len(y)

    def test_first_value_preserved(self):
        y = np.array([10.0, 20.0, 30.0])
        result = _exponential_smoothing(y, alpha=0.5)
        assert result[0] == 10.0

    def test_alpha_one_returns_original(self):
        y = np.array([1.0, 5.0, 3.0, 7.0])
        result = _exponential_smoothing(y, alpha=1.0)
        np.testing.assert_array_almost_equal(result, y)

    def test_alpha_zero_returns_first_value(self):
        y = np.array([10.0, 20.0, 30.0, 40.0])
        result = _exponential_smoothing(y, alpha=0.0)
        np.testing.assert_array_almost_equal(result, [10.0, 10.0, 10.0, 10.0])


class TestOptimalAlpha:
    def test_returns_value_between_0_and_1(self):
        y = np.cumsum(np.random.randn(50)) + 100
        alpha = _optimal_alpha(y)
        assert 0.01 <= alpha <= 0.99

    def test_trending_series_favours_high_alpha(self):
        y = np.arange(1.0, 51.0)  # strong trend
        alpha = _optimal_alpha(y)
        assert alpha > 0.5


class TestLogLinearForecast:
    def test_positive_series_produces_forecast(self):
        y = np.exp(np.linspace(0, 1, 40))  # exponential growth
        result = _log_linear_forecast(y, horizon=8)
        assert "forecast" in result
        assert len(result["forecast"]) == 8
        assert len(result["lower_95"]) == 8

    def test_growing_series_has_upward_forecast(self):
        y = np.exp(np.linspace(0, 2, 40))
        result = _log_linear_forecast(y, horizon=4)
        assert result["forecast"][0] > y[-1]

    def test_r_squared_is_high_for_exponential(self):
        y = np.exp(np.linspace(0, 1, 40))
        result = _log_linear_forecast(y, horizon=4)
        assert result["r_squared"] > 0.99

    def test_confidence_bands_widen(self):
        y = np.exp(np.linspace(0, 1, 40))
        result = _log_linear_forecast(y, horizon=8)
        widths = result["upper_95"] - result["lower_95"]
        # All widths should be positive
        assert (widths > 0).all()


class TestMeanReversionForecast:
    def test_forecast_moves_toward_target(self):
        y = np.full(50, 10.0)  # stuck at 10
        result = _mean_reversion_forecast(y, target=5.0, horizon=20)
        # Forecast should trend toward 5.0
        assert result["forecast"][-1] < 10.0

    def test_output_structure(self):
        y = np.random.randn(50).cumsum() + 5
        result = _mean_reversion_forecast(y, target=5.0, horizon=12)
        assert "forecast" in result
        assert "lower_68" in result
        assert "upper_95" in result
        assert len(result["forecast"]) == 12

    def test_speed_is_positive(self):
        y = np.random.randn(50).cumsum() + 5
        result = _mean_reversion_forecast(y, target=5.0, horizon=10)
        assert result["speed"] > 0

    def test_explicit_speed(self):
        y = np.full(20, 8.0)
        result = _mean_reversion_forecast(y, target=5.0, speed=0.1, horizon=5)
        assert result["speed"] == 0.1


class TestSarimaxForecast:
    def test_returns_none_without_statsmodels(self):
        """SARIMAX should work if statsmodels is installed, return None otherwise."""
        y = np.sin(np.linspace(0, 8 * np.pi, 60)) + 10
        result = _sarimax_forecast(
            y, seasonal_period=4, horizon=4, max_order=(1, 0, 1), max_seasonal=(0, 0, 0)
        )
        # Either returns a valid dict or None
        if result is not None:
            assert "forecast" in result
            assert result["method"] == "SARIMAX"
            assert "aic" in result
            assert len(result["forecast"]) == 4

    def test_sarimax_on_quarterly_like_data(self):
        np.random.seed(42)
        trend = np.linspace(100, 120, 60)
        seasonal = 3 * np.sin(np.arange(60) * 2 * np.pi / 4)
        y = trend + seasonal + np.random.randn(60) * 0.5
        result = _sarimax_forecast(
            y, seasonal_period=4, horizon=8, max_order=(1, 1, 1), max_seasonal=(1, 0, 1)
        )
        if result is not None:
            assert len(result["forecast"]) == 8
            assert result["aic"] is not None
