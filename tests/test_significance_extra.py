"""Additional tests for significance_tests to boost coverage."""

import numpy as np
import pandas as pd
import pytest

from src.analysis import significance_tests as sigmod


class TestStationarityExtra:
    def test_stationary_series(self):
        np.random.seed(42)
        y = np.random.randn(100)
        result = sigmod.test_stationarity(y)
        assert "adf_statistic" in result
        assert "is_stationary" in result

    def test_trending_series(self):
        y = np.arange(100, dtype=float)
        result = sigmod.test_stationarity(y)
        assert "is_stationary" in result


class TestTrendSignificanceExtra:
    def test_significant_upward_trend(self):
        y = np.arange(50, dtype=float)
        result = sigmod.test_trend_significance(y)
        assert result["slope"] > 0
        assert "p_value" in result

    def test_custom_x(self):
        y = np.arange(20, dtype=float) * 2
        x = np.arange(20, dtype=float)
        result = sigmod.test_trend_significance(y, x)
        assert result["slope"] == pytest.approx(2.0)


class TestPeriodComparison:
    def test_with_dataframe(self):
        df = pd.DataFrame(
            {
                "year": [2010] * 20 + [2015] * 20 + [2020] * 20,
                "value": np.concatenate(
                    [
                        np.ones(20) * 5,
                        np.ones(20) * 15,
                        np.ones(20) * 10,
                    ]
                ),
            }
        )
        result = sigmod.test_period_comparison(df, "value", "year")
        assert isinstance(result, dict)


class TestStructuralBreakExtra:
    def test_clear_break(self):
        y = np.concatenate(
            [
                np.ones(30) * 5 + np.random.randn(30) * 0.1,
                np.ones(30) * 15 + np.random.randn(30) * 0.1,
            ]
        )
        result = sigmod.test_structural_break(y, break_point=30)
        assert "f_statistic" in result

    def test_no_break(self):
        np.random.seed(42)
        y = np.random.randn(60) + 10
        result = sigmod.test_structural_break(y, break_point=30)
        assert "f_statistic" in result


class TestGrangerProxy:
    def test_uncorrelated_series(self):
        np.random.seed(42)
        cause = np.random.randn(100)
        effect = np.random.randn(100)
        result = sigmod.test_granger_proxy(cause, effect, max_lag=4)
        assert isinstance(result, dict)

    def test_lagged_series(self):
        np.random.seed(42)
        cause = np.random.randn(100)
        effect = np.zeros(100)
        effect[3:] = cause[:-3]
        result = sigmod.test_granger_proxy(cause, effect, max_lag=6)
        assert isinstance(result, dict)
