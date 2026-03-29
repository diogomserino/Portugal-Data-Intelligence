"""Tests for the forecast backtesting module."""

import numpy as np
import pytest

from src.analysis.backtesting import (
    _directional_accuracy,
    _mae,
    _mape,
    _rmse,
    expanding_window_backtest,
)


class TestMetrics:
    def test_mae_perfect(self):
        a = np.array([1.0, 2.0, 3.0])
        assert _mae(a, a) == 0.0

    def test_mae_known(self):
        a = np.array([1.0, 2.0, 3.0])
        p = np.array([2.0, 3.0, 4.0])
        assert _mae(a, p) == 1.0

    def test_rmse_perfect(self):
        a = np.array([1.0, 2.0, 3.0])
        assert _rmse(a, a) == 0.0

    def test_rmse_known(self):
        a = np.array([1.0, 2.0, 3.0])
        p = np.array([2.0, 3.0, 4.0])
        assert _rmse(a, p) == 1.0

    def test_mape_perfect(self):
        a = np.array([1.0, 2.0, 3.0])
        assert _mape(a, a) == 0.0

    def test_mape_known(self):
        a = np.array([100.0, 200.0])
        p = np.array([110.0, 220.0])
        assert _mape(a, p) == 10.0

    def test_mape_handles_zeros(self):
        a = np.array([0.0, 1.0])
        p = np.array([0.5, 1.5])
        result = _mape(a, p)
        # Should skip zero entries
        assert result == pytest.approx(50.0)

    def test_directional_accuracy_perfect(self):
        a = np.array([1.0, 2.0, 3.0, 4.0])
        p = np.array([1.0, 2.0, 3.0, 4.0])
        assert _directional_accuracy(a, p) == 100.0

    def test_directional_accuracy_wrong(self):
        a = np.array([1.0, 2.0, 3.0])
        p = np.array([3.0, 2.0, 1.0])  # opposite direction
        assert _directional_accuracy(a, p) == 0.0

    def test_directional_accuracy_short_series(self):
        a = np.array([1.0])
        p = np.array([2.0])
        result = _directional_accuracy(a, p)
        assert np.isnan(result)


class TestExpandingWindowBacktest:
    def _linear_predictor(self, train, horizon):
        """Simple linear extrapolation for testing."""
        slope = (train[-1] - train[0]) / max(len(train) - 1, 1)
        last = train[-1]
        return np.array([last + slope * (i + 1) for i in range(horizon)])

    def test_produces_origins(self):
        series = np.linspace(100, 200, 50)
        result = expanding_window_backtest(
            series,
            self._linear_predictor,
            min_train=20,
            step_ahead=4,
            step_size=4,
        )
        assert result["n_origins"] > 0
        assert "aggregate" in result
        assert "mae" in result["aggregate"]

    def test_min_origins(self):
        series = np.linspace(100, 200, 50)
        result = expanding_window_backtest(
            series,
            self._linear_predictor,
            min_train=20,
            step_ahead=4,
            step_size=4,
        )
        # Should have at least 5 origins: (20, 24, 28, 32, 36, 40, 44) = 7
        assert result["n_origins"] >= 5

    def test_too_short_series(self):
        series = np.array([1.0, 2.0, 3.0])
        result = expanding_window_backtest(
            series,
            self._linear_predictor,
            min_train=10,
            step_ahead=4,
            step_size=4,
        )
        assert result.get("error") or result["n_origins"] == 0

    def test_perfect_predictor(self):
        series = np.arange(100.0)

        def perfect(train, horizon):
            return np.arange(len(train), len(train) + horizon, dtype=float)

        result = expanding_window_backtest(
            series,
            perfect,
            min_train=20,
            step_ahead=4,
            step_size=4,
        )
        assert result["aggregate"]["mae"] == 0.0

    def test_failed_predictor_skipped(self):
        series = np.linspace(100, 200, 50)

        def failing(train, horizon):
            raise ValueError("fail")

        result = expanding_window_backtest(
            series,
            failing,
            min_train=20,
            step_ahead=4,
            step_size=4,
        )
        assert result.get("error") or result["n_origins"] == 0
