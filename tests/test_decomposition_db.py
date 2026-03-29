"""Tests for src/analysis/decomposition.py with the production database."""

import numpy as np
import pandas as pd
import pytest

from tests.conftest import PRODUCTION_DB

try:
    from statsmodels.tsa.seasonal import STL  # noqa: F401

    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

pytestmark = pytest.mark.skipif(
    not PRODUCTION_DB.exists() or not HAS_STATSMODELS,
    reason="Production DB or statsmodels not available",
)


class TestRunDecomposition:
    def test_returns_dict_with_expected_keys(self):
        from src.analysis.decomposition import run_decomposition

        results = run_decomposition(db_path=str(PRODUCTION_DB))
        assert isinstance(results, dict)
        for key in ("unemployment", "inflation", "gdp"):
            assert key in results

    def test_components_have_correct_keys(self):
        from src.analysis.decomposition import run_decomposition

        results = run_decomposition(db_path=str(PRODUCTION_DB))
        for pillar, components in results.items():
            if components is None:
                continue
            for k in ("observed", "trend", "seasonal", "residual"):
                assert k in components, f"Missing '{k}' in {pillar}"
                assert isinstance(components[k], np.ndarray)
                assert len(components[k]) > 0

    def test_trend_plus_seasonal_plus_resid_equals_observed(self):
        from src.analysis.decomposition import run_decomposition

        results = run_decomposition(db_path=str(PRODUCTION_DB))
        for pillar, components in results.items():
            if components is None:
                continue
            reconstructed = components["trend"] + components["seasonal"] + components["residual"]
            np.testing.assert_allclose(
                reconstructed,
                components["observed"],
                atol=1e-6,
                err_msg=f"Reconstruction failed for {pillar}",
            )


class TestDecomposeAndPlot:
    def test_decompose_short_series_returns_none(self):
        from src.analysis.decomposition import decompose_and_plot

        short = pd.Series([1.0, 2.0, 3.0])
        result = decompose_and_plot(short, period=12, title="short_test")
        assert result is None

    def test_decompose_valid_series(self):
        from src.analysis.decomposition import decompose_and_plot

        np.random.seed(42)
        n = 100
        trend = np.linspace(5, 10, n)
        seasonal = np.sin(np.linspace(0, 2 * np.pi * (n / 12), n))
        series = pd.Series(trend + seasonal + np.random.normal(0, 0.1, n))
        result = decompose_and_plot(series, period=12, title="unit_test_series")
        assert result is not None
        assert "trend" in result
