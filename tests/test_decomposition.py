"""Tests for the STL decomposition module."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.decomposition import HAS_STL, decompose_series


@pytest.mark.skipif(not HAS_STL, reason="statsmodels not installed")
class TestDecomposeSeries:
    def test_basic_decomposition(self):
        # Create a series with clear seasonal pattern
        n = 120  # 10 years monthly
        trend = np.linspace(5, 10, n)
        seasonal = 2 * np.sin(np.arange(n) * 2 * np.pi / 12)
        noise = np.random.RandomState(42).randn(n) * 0.1
        series = pd.Series(trend + seasonal + noise)

        result = decompose_series(series, period=12)
        assert result is not None
        assert "trend" in result
        assert "seasonal" in result
        assert "residual" in result
        assert "observed" in result
        assert len(result["trend"]) == n

    def test_too_short_series_returns_none(self):
        series = pd.Series([1.0, 2.0, 3.0])
        result = decompose_series(series, period=12)
        assert result is None

    def test_quarterly_decomposition(self):
        n = 60  # 15 years quarterly
        trend = np.linspace(100, 200, n)
        seasonal = 5 * np.sin(np.arange(n) * 2 * np.pi / 4)
        series = pd.Series(trend + seasonal)

        result = decompose_series(series, period=4)
        assert result is not None
        assert len(result["seasonal"]) == n

    def test_seasonal_component_has_pattern(self):
        n = 120
        trend = np.full(n, 10.0)
        seasonal = 3 * np.sin(np.arange(n) * 2 * np.pi / 12)
        series = pd.Series(trend + seasonal)

        result = decompose_series(series, period=12)
        assert result is not None
        # Seasonal component should have non-trivial amplitude
        seasonal_range = result["seasonal"].max() - result["seasonal"].min()
        assert seasonal_range > 1.0

    def test_handles_nan_in_series(self):
        n = 120
        data = np.linspace(5, 10, n) + np.sin(np.arange(n) * 2 * np.pi / 12)
        data[50] = np.nan
        series = pd.Series(data)

        # dropna reduces length but should still work
        result = decompose_series(series, period=12)
        assert result is not None
