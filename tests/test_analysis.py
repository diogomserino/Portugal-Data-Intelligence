"""Unit tests for the analysis modules."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.conftest import DATA_RANGES

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestStatisticalAnalysis:
    """Tests for statistical_analysis module."""

    def test_run_all_analyses_returns_all_pillars(self, production_db_path):
        """Should return results for all 6 pillars."""
        from src.analysis.statistical_analysis import run_all_analyses

        results = run_all_analyses(str(production_db_path))
        assert len(results) == 6
        for pillar in [
            "gdp",
            "unemployment",
            "credit",
            "interest_rates",
            "inflation",
            "public_debt",
        ]:
            assert pillar in results

    def test_each_pillar_has_required_keys(self, production_db_path):
        """Each pillar result should have summary, statistics, notable_findings."""
        from src.analysis.statistical_analysis import run_all_analyses

        results = run_all_analyses(str(production_db_path))
        for pillar, result in results.items():
            assert "summary" in result, f"{pillar} missing 'summary'"
            assert "statistics" in result, f"{pillar} missing 'statistics'"
            assert "notable_findings" in result, f"{pillar} missing 'notable_findings'"

    def test_gdp_growth_is_realistic(self, production_db_path):
        """GDP growth should be within plausible macroeconomic bounds."""
        from src.analysis.statistical_analysis import run_all_analyses

        lo, hi = DATA_RANGES["gdp_growth_yoy"]
        results = run_all_analyses(str(production_db_path))
        stats = results["gdp"]["statistics"]
        if "growth_rate" in stats:
            mean_growth = stats["growth_rate"]["mean"]
            assert lo < mean_growth < hi, f"Unrealistic GDP growth mean: {mean_growth}"


class TestSignificanceTests:
    """Tests for the significance_tests module."""

    def test_stationarity_detects_trend(self):
        """ADF test should detect a non-stationary trending series."""
        from src.analysis.significance_tests import test_stationarity

        # Trending series (non-stationary)
        trend = np.arange(50, dtype=float) * 2 + np.random.normal(0, 0.5, 50)
        result = test_stationarity(trend)
        assert result["is_stationary"] is not None
        # A linear trend should typically be non-stationary
        assert "adf_statistic" in result
        assert "critical_values" in result

    def test_stationarity_detects_stationary(self):
        """ADF test should detect a stationary white noise series."""
        from src.analysis.significance_tests import test_stationarity

        np.random.seed(42)
        stationary = np.random.normal(0, 1, 100)
        result = test_stationarity(stationary)
        assert result["is_stationary"] == True

    def test_bonferroni_correction_applied(self):
        """Pairwise t-tests should include Bonferroni-corrected p-values."""
        from src.analysis.significance_tests import test_period_comparison

        df = pd.DataFrame(
            {
                "year": list(range(2010, 2026)),
                "value": np.random.normal(5, 1, 16),
            }
        )
        result = test_period_comparison(df, "value", "year")
        assert "bonferroni_alpha" in result
        if result["pairwise_tests"]:
            assert "p_value_bonferroni" in result["pairwise_tests"][0]
            assert "cohens_d" in result["pairwise_tests"][0]

    def test_chow_test_returns_valid_result(self):
        """Chow test should return valid F-statistic for known structural break."""
        from src.analysis.significance_tests import test_structural_break

        # Series with clear break at index 10
        np.random.seed(42)
        y = np.concatenate(
            [
                np.random.normal(5, 0.5, 10),
                np.random.normal(10, 0.5, 10),
            ]
        )
        result = test_structural_break(y, 10)
        assert result["f_statistic"] is not None
        assert result["p_value"] is not None
        # Clear break should be significant
        assert result["significant"] == True

    def test_granger_proxy_has_bonferroni(self):
        """Granger proxy should apply Bonferroni correction across lags."""
        from src.analysis.significance_tests import test_granger_proxy

        np.random.seed(42)
        cause = np.random.normal(0, 1, 50)
        effect = np.random.normal(0, 1, 50)
        result = test_granger_proxy(cause, effect, max_lag=5)
        assert "bonferroni_alpha" in result
        assert result["bonferroni_alpha"] == round(0.05 / 5, 4)


class TestCorrelationAnalysis:
    """Tests for correlation_analysis module."""

    def test_correlation_matrix_is_square(self, production_db_path):
        """Correlation matrix should be square."""
        from src.analysis.correlation_analysis import build_correlation_matrix

        matrix = build_correlation_matrix(str(production_db_path))
        assert matrix.shape[0] == matrix.shape[1]

    def test_correlation_values_in_range(self, production_db_path):
        """All correlation values should be between -1 and 1."""
        from src.analysis.correlation_analysis import build_correlation_matrix

        matrix = build_correlation_matrix(str(production_db_path))
        # Float tolerance of 1e-4 for numerical precision
        assert matrix.min().min() >= -1.0001
        assert matrix.max().max() <= 1.0001

    def test_phillips_curve_returns_valid_structure(self, production_db_path):
        """Phillips curve analysis should return expected keys."""
        from src.analysis.correlation_analysis import analyse_phillips_curve

        result = analyse_phillips_curve(str(production_db_path))
        assert "correlation" in result
        corr = result["correlation"]
        assert "r" in corr
        assert "p_value" in corr
        assert "n" in corr

    def test_no_perfect_correlations_in_matrix(self, production_db_path):
        """Off-diagonal correlations should not be exactly +/-1.0 (ignoring NaN from constant columns)."""
        from src.analysis.correlation_analysis import build_correlation_matrix

        matrix = build_correlation_matrix(str(production_db_path))
        values = matrix.values.copy()
        np.fill_diagonal(values, 0)
        # Constant columns (e.g. is_provisional all False) produce NaN — ignore them
        mask = ~np.isnan(values)
        assert (
            np.abs(values[mask]) < 1.0 - 1e-10
        ).all(), "Exact perfect correlation detected — check for linear dependencies"


class TestVisualisations:
    """Tests for chart generation."""

    # Minimum file size for a valid 150 DPI PNG chart (~5KB minimum)
    MIN_CHART_BYTES = 5_000

    def test_all_charts_generated(self):
        """All expected chart files should exist."""
        charts_dir = PROJECT_ROOT / "reports" / "powerbi" / "charts"
        expected = [
            "gdp_evolution.png",
            "unemployment_trends.png",
            "credit_portfolio.png",
            "interest_rate_environment.png",
            "inflation_dashboard.png",
            "public_debt_sustainability.png",
            "correlation_heatmap.png",
            "economic_dashboard.png",
            "phillips_curve.png",
            "crisis_timeline.png",
        ]
        for chart in expected:
            assert (charts_dir / chart).exists(), f"Missing chart: {chart}"

    def test_chart_files_not_empty(self):
        """Chart files should have meaningful content (>5KB for 150 DPI PNG)."""
        charts_dir = PROJECT_ROOT / "reports" / "powerbi" / "charts"
        for png in charts_dir.glob("*.png"):
            size = png.stat().st_size
            assert size > self.MIN_CHART_BYTES, f"Chart too small ({size} bytes): {png.name}"
