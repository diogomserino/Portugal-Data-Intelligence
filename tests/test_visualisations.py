"""Smoke tests for chart generation (src/analysis/visualisations.py).

Each chart function must return a file path (str) pointing to an existing
PNG file larger than 1 KB.  Tests are skipped when the production database
is not available.
"""

from pathlib import Path

import pytest

from src.analysis.visualisations import (
    generate_all_charts,
    plot_correlation_heatmap,
    plot_credit_portfolio,
    plot_crisis_timeline,
    plot_economic_dashboard,
    plot_gdp_evolution,
    plot_inflation_dashboard,
    plot_interest_rate_environment,
    plot_phillips_curve,
    plot_public_debt_sustainability,
    plot_unemployment_trends,
)
from tests.conftest import PRODUCTION_DB

pytestmark = pytest.mark.skipif(
    not PRODUCTION_DB.exists(),
    reason="Production database not available",
)

# ---------------------------------------------------------------------------
# Parametrised smoke test for individual chart functions
# ---------------------------------------------------------------------------

CHART_FUNCTIONS = [
    pytest.param(plot_gdp_evolution, id="gdp_evolution"),
    pytest.param(plot_unemployment_trends, id="unemployment_trends"),
    pytest.param(plot_credit_portfolio, id="credit_portfolio"),
    pytest.param(plot_interest_rate_environment, id="interest_rate_environment"),
    pytest.param(plot_inflation_dashboard, id="inflation_dashboard"),
    pytest.param(plot_public_debt_sustainability, id="public_debt_sustainability"),
    pytest.param(plot_correlation_heatmap, id="correlation_heatmap"),
    pytest.param(plot_economic_dashboard, id="economic_dashboard"),
    pytest.param(plot_phillips_curve, id="phillips_curve"),
    pytest.param(plot_crisis_timeline, id="crisis_timeline"),
]

MIN_FILE_SIZE_BYTES = 1024  # 1 KB — a valid chart PNG is always larger


@pytest.mark.parametrize("chart_fn", CHART_FUNCTIONS)
def test_chart_returns_existing_png(chart_fn):
    """Chart function returns a path to a non-trivial PNG file."""
    result = chart_fn(db_path=str(PRODUCTION_DB))

    # 1. Returns a string (file path)
    assert isinstance(result, str), f"Expected str, got {type(result)}"

    path = Path(result)

    # 2. File exists on disk
    assert path.exists(), f"Chart file does not exist: {path}"

    # 3. File has .png extension
    assert path.suffix.lower() == ".png", f"Expected .png extension, got {path.suffix}"

    # 4. File size > 1 KB (non-empty chart)
    size = path.stat().st_size
    assert (
        size > MIN_FILE_SIZE_BYTES
    ), f"Chart file is too small ({size} bytes < {MIN_FILE_SIZE_BYTES}): {path.name}"


# ---------------------------------------------------------------------------
# Test generate_all_charts
# ---------------------------------------------------------------------------


def test_generate_all_charts_returns_list():
    """generate_all_charts returns a list of paths to existing PNG files."""
    results = generate_all_charts(db_path=str(PRODUCTION_DB))

    assert isinstance(results, list), f"Expected list, got {type(results)}"
    assert len(results) >= 8, f"Expected at least 8 charts, got {len(results)}"

    for filepath in results:
        assert isinstance(filepath, str)
        p = Path(filepath)
        assert p.exists(), f"Missing chart: {p}"
        assert p.suffix.lower() == ".png"
        assert p.stat().st_size > MIN_FILE_SIZE_BYTES
