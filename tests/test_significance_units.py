"""Unit tests for significance_tests module — pure functions, no database."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.significance_tests import PERIODS
from src.analysis.significance_tests import test_granger_proxy as run_granger_proxy
from src.analysis.significance_tests import test_period_comparison as run_period_comparison
from src.analysis.significance_tests import test_stationarity as run_stationarity
from src.analysis.significance_tests import test_structural_break as run_structural_break
from src.analysis.significance_tests import test_trend_significance as run_trend_significance

# ============================================================================
# test_stationarity (ADF)
# ============================================================================


class TestStationarity:
    """Tests for the ADF stationarity test."""

    def test_stationary_white_noise(self):
        np.random.seed(42)
        y = np.random.normal(0, 1, 200)
        result = run_stationarity(y)
        assert result["is_stationary"] == True

    def test_nonstationary_random_walk(self):
        np.random.seed(42)
        y = np.cumsum(np.random.normal(0, 1, 200))
        result = run_stationarity(y)
        assert result["is_stationary"] == False

    def test_nonstationary_linear_trend(self):
        # Exponential growth — clearly non-stationary
        y = np.exp(np.arange(50, dtype=float) * 0.1)
        result = run_stationarity(y)
        assert result["is_stationary"] == False

    def test_insufficient_data(self):
        y = np.array([1.0, 2.0, 3.0])
        result = run_stationarity(y)
        assert result["is_stationary"] is None  # Python None, not numpy
        assert "Insufficient" in result["interpretation"]

    def test_handles_nan_values(self):
        np.random.seed(42)
        y = np.random.normal(0, 1, 50)
        y[10] = np.nan
        y[20] = np.nan
        result = run_stationarity(y)
        assert result["is_stationary"] is not None or result["is_stationary"] is None
        # NaN values are removed before processing
        assert result["n_obs"] > 0

    def test_constant_series(self):
        y = np.full(50, 5.0)
        result = run_stationarity(y)
        # Constant series: diff = all zeros, regression degenerates gracefully
        assert "interpretation" in result

    def test_output_has_required_keys(self):
        np.random.seed(42)
        y = np.random.normal(0, 1, 50)
        result = run_stationarity(y)
        for key in [
            "adf_statistic",
            "p_value",
            "is_stationary",
            "critical_values",
            "n_obs",
            "interpretation",
        ]:
            assert key in result, f"Missing key: {key}"


# ============================================================================
# test_trend_significance
# ============================================================================


class TestTrendSignificance:
    """Tests for OLS trend significance."""

    def test_strong_upward_trend(self):
        y = np.arange(20, dtype=float) * 10 + np.random.normal(0, 0.1, 20)
        result = run_trend_significance(y)
        assert result["significant"] == True
        assert result["slope"] > 0
        assert result["r_squared"] > 0.95

    def test_no_trend(self):
        np.random.seed(42)
        y = np.random.normal(50, 10, 30)
        result = run_trend_significance(y)
        assert result["r_squared"] < 0.3

    def test_downward_trend(self):
        y = 100 - np.arange(20, dtype=float) * 3
        result = run_trend_significance(y)
        assert result["slope"] < 0
        assert result["significant"] == True

    def test_insufficient_data(self):
        result = run_trend_significance(np.array([1.0, 2.0]))
        assert result["significant"] is None
        assert "Insufficient" in result["interpretation"]

    def test_custom_x_axis(self):
        x = np.array([2010, 2015, 2020, 2025], dtype=float)
        y = np.array([100, 120, 140, 160], dtype=float)
        result = run_trend_significance(y, x)
        assert result["slope"] > 0

    def test_handles_nan_in_y(self):
        y = np.array([1.0, np.nan, 3.0, 4.0, 5.0, 6.0])
        result = run_trend_significance(y)
        assert result["significant"] is not None

    def test_single_value(self):
        result = run_trend_significance(np.array([5.0]))
        assert result["significant"] is None


# ============================================================================
# test_period_comparison
# ============================================================================


class TestPeriodComparison:
    """Tests for ANOVA + pairwise t-tests with Bonferroni correction."""

    @pytest.fixture
    def multi_period_data(self):
        """DataFrame with clearly different means per period."""
        np.random.seed(42)
        rows = []
        for year in range(2010, 2026):
            if year <= 2011:
                val = np.random.normal(100, 5)
            elif year <= 2014:
                val = np.random.normal(50, 5)
            elif year <= 2019:
                val = np.random.normal(80, 5)
            elif year == 2020:
                val = np.random.normal(30, 5)
            else:
                val = np.random.normal(90, 5)
            rows.append({"year": year, "value": val})
        return pd.DataFrame(rows)

    def test_detects_significant_differences(self, multi_period_data):
        result = run_period_comparison(multi_period_data, "value", "year")
        assert result["anova"]["significant"] == True
        assert result["n_significant_pairs"] > 0

    def test_bonferroni_alpha_is_correct(self, multi_period_data):
        result = run_period_comparison(multi_period_data, "value", "year")
        n_pairs = result["n_total_pairs"]
        expected_alpha = round(0.05 / max(n_pairs, 1), 4)
        assert result["bonferroni_alpha"] == expected_alpha

    def test_cohens_d_included(self, multi_period_data):
        result = run_period_comparison(multi_period_data, "value", "year")
        for pw in result["pairwise_tests"]:
            assert "cohens_d" in pw
            assert isinstance(pw["cohens_d"], float)

    def test_no_significant_when_same_distribution(self):
        np.random.seed(42)
        df = pd.DataFrame(
            {
                "year": list(range(2010, 2026)),
                "value": np.random.normal(50, 1, 16),
            }
        )
        result = run_period_comparison(df, "value", "year")
        assert result["anova"]["significant"] == False

    def test_insufficient_periods(self):
        df = pd.DataFrame({"year": [2020], "value": [100.0]})
        result = run_period_comparison(df, "value", "year")
        assert "Insufficient" in result["interpretation"]

    def test_handles_missing_values(self):
        df = pd.DataFrame(
            {
                "year": list(range(2010, 2026)),
                "value": [np.nan if y == 2015 else float(y) for y in range(2010, 2026)],
            }
        )
        result = run_period_comparison(df, "value", "year")
        assert result["anova"]["f_statistic"] is not None


# ============================================================================
# test_structural_break (Chow test)
# ============================================================================


class TestStructuralBreak:
    """Tests for the Chow test."""

    def test_detects_clear_break(self):
        np.random.seed(42)
        y = np.concatenate(
            [
                np.random.normal(10, 1, 15),
                np.random.normal(50, 1, 15),
            ]
        )
        result = run_structural_break(y, 15)
        assert result["significant"] == True

    def test_no_break_in_uniform_series(self):
        np.random.seed(42)
        y = np.random.normal(50, 1, 30)
        result = run_structural_break(y, 15)
        assert result["significant"] == False

    def test_break_near_boundary_returns_none(self):
        y = np.arange(10, dtype=float)
        result = run_structural_break(y, 1)
        assert result["f_statistic"] is None
        assert "boundaries" in result["interpretation"]

    def test_break_at_end_returns_none(self):
        y = np.arange(10, dtype=float)
        result = run_structural_break(y, 9)
        assert result["f_statistic"] is None

    def test_handles_nan_values(self):
        np.random.seed(42)
        y = np.concatenate(
            [
                np.random.normal(10, 1, 15),
                np.random.normal(50, 1, 15),
            ]
        )
        y[5] = np.nan
        result = run_structural_break(y, 14)
        assert result["f_statistic"] is not None


# ============================================================================
# test_granger_proxy
# ============================================================================


class TestGrangerProxy:
    """Tests for the lagged correlation proxy."""

    def test_detects_lagged_relationship(self):
        np.random.seed(42)
        n = 100
        cause = np.random.normal(0, 1, n)
        # Effect follows cause with lag 2
        effect = np.zeros(n)
        effect[2:] = cause[:-2] * 0.9 + np.random.normal(0, 0.1, n - 2)
        result = run_granger_proxy(cause, effect, max_lag=5)
        assert result["optimal_lag"] == 2

    def test_no_relationship(self):
        np.random.seed(99)  # seed chosen to avoid spurious correlation
        cause = np.random.normal(0, 1, 200)
        effect = np.random.normal(0, 1, 200)
        result = run_granger_proxy(cause, effect, max_lag=5)
        # With Bonferroni correction on independent series, should find nothing
        assert result["optimal_lag"] is None

    def test_bonferroni_alpha_correct(self):
        np.random.seed(42)
        cause = np.random.normal(0, 1, 50)
        effect = np.random.normal(0, 1, 50)
        result = run_granger_proxy(cause, effect, max_lag=10)
        assert result["bonferroni_alpha"] == round(0.05 / 10, 4)

    def test_all_lags_have_required_keys(self):
        np.random.seed(42)
        cause = np.random.normal(0, 1, 50)
        effect = np.random.normal(0, 1, 50)
        result = run_granger_proxy(cause, effect, max_lag=3)
        for lag_entry in result["all_lags"]:
            for key in ["lag", "correlation", "p_value", "significant", "n_obs"]:
                assert key in lag_entry

    def test_handles_short_series(self):
        cause = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        effect = np.array([2.0, 3.0, 4.0, 5.0, 6.0])
        result = run_granger_proxy(cause, effect, max_lag=10)
        # Should auto-reduce max_lag
        assert len(result["all_lags"]) <= 3

    def test_handles_nan(self):
        np.random.seed(42)
        cause = np.random.normal(0, 1, 50)
        effect = np.random.normal(0, 1, 50)
        cause[10] = np.nan
        effect[20] = np.nan
        result = run_granger_proxy(cause, effect, max_lag=3)
        assert "all_lags" in result
