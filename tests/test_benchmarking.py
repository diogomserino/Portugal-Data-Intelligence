"""Tests for the EU benchmarking module (src/analysis/benchmarking.py).

Validates indicator comparisons, convergence analysis, peer tables,
ranking history, and the full benchmark report.  Skipped when the
production database is not available.
"""

import pandas as pd
import pytest

from src.analysis.benchmarking import EUBenchmark
from tests.conftest import PRODUCTION_DB

pytestmark = pytest.mark.skipif(
    not PRODUCTION_DB.exists(),
    reason="Production database not available",
)

VALID_INDICATORS = [
    "gdp_growth",
    "unemployment",
    "inflation",
    "debt_to_gdp",
    "interest_rate_10y",
]

EXPECTED_COUNTRIES = {"PT", "DE", "ES", "FR", "IT", "EU_AVG", "EA_AVG"}


# ---------------------------------------------------------------------------
# Module-scoped fixture — single DB load for all tests in this file
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def bench():
    """Create a single EUBenchmark instance for the whole module."""
    return EUBenchmark(db_path=str(PRODUCTION_DB))


# ---------------------------------------------------------------------------
# compare_indicator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("indicator", VALID_INDICATORS)
def test_compare_indicator_keys(bench, indicator):
    """compare_indicator returns expected keys for each indicator."""
    result = bench.compare_indicator(indicator)

    assert isinstance(result, dict)
    expected_keys = {
        "indicator",
        "indicator_label",
        "latest_year",
        "ranking",
        "portugal_vs_eu_avg",
        "portugal_rank",
        "trend",
        "convergence_rate",
    }
    assert expected_keys.issubset(result.keys()), f"Missing keys: {expected_keys - result.keys()}"
    assert result["indicator"] == indicator
    assert isinstance(result["ranking"], list)
    assert len(result["ranking"]) > 0
    assert result["portugal_rank"] is not None
    assert 1 <= result["portugal_rank"] <= 5
    assert result["trend"] in ("converging", "diverging", "insufficient_data")


# ---------------------------------------------------------------------------
# generate_convergence_analysis
# ---------------------------------------------------------------------------


def test_convergence_analysis_covers_all_indicators(bench):
    """Convergence analysis includes results for all 5 indicators."""
    result = bench.generate_convergence_analysis()

    assert isinstance(result, dict)
    assert "indicators" in result
    assert set(result["indicators"].keys()) == set(VALID_INDICATORS)

    for indicator, info in result["indicators"].items():
        assert "trend" in info
        assert "convergence_rate" in info
        assert "gap_pp" in info

    assert "overall_assessment" in result
    assert result["overall_assessment"] in (
        "broadly converging",
        "mixed signals",
        "broadly diverging",
    )


# ---------------------------------------------------------------------------
# generate_peer_comparison_table
# ---------------------------------------------------------------------------


def test_peer_comparison_table_columns(bench):
    """Peer comparison table has expected country columns."""
    table = bench.generate_peer_comparison_table()

    assert isinstance(table, pd.DataFrame)
    assert table.shape[0] == len(VALID_INDICATORS)

    actual_columns = set(table.columns)
    assert EXPECTED_COUNTRIES.issubset(
        actual_columns
    ), f"Missing columns: {EXPECTED_COUNTRIES - actual_columns}"


# ---------------------------------------------------------------------------
# generate_ranking_history
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("indicator", VALID_INDICATORS)
def test_ranking_history_structure(bench, indicator):
    """Ranking history has year and PT_rank columns with valid data."""
    history = bench.generate_ranking_history(indicator)

    assert isinstance(history, pd.DataFrame)
    assert "year" in history.columns
    assert "PT_rank" in history.columns
    assert "PT_value" in history.columns
    assert len(history) > 0

    # All ranks should be between 1 and 5 (5 peer countries)
    assert history["PT_rank"].between(1, 5).all()


# ---------------------------------------------------------------------------
# generate_benchmark_report
# ---------------------------------------------------------------------------


def test_benchmark_report_key_findings(bench):
    """Benchmark report has key_findings list with at least 3 entries."""
    report = bench.generate_benchmark_report()

    assert isinstance(report, dict)
    assert "summary" in report
    assert isinstance(report["summary"], str)
    assert len(report["summary"]) > 0

    assert "key_findings" in report
    assert isinstance(report["key_findings"], list)
    assert (
        len(report["key_findings"]) >= 3
    ), f"Expected >= 3 key findings, got {len(report['key_findings'])}"

    assert "comparisons" in report
    assert "convergence" in report
    assert "peer_table" in report
    assert isinstance(report["peer_table"], pd.DataFrame)
