"""Database-dependent tests for the backtesting module."""

import pytest

from tests.conftest import PRODUCTION_DB

pytestmark = pytest.mark.skipif(
    not PRODUCTION_DB.exists(),
    reason="Production database not available",
)


class TestRunBacktests:
    def test_run_backtests_returns_results(self):
        from src.analysis.backtesting import run_backtests

        results = run_backtests(db_path=str(PRODUCTION_DB))
        assert "gdp" in results
        assert "unemployment" in results

    def test_gdp_backtest_has_origins(self):
        from src.analysis.backtesting import run_backtests

        results = run_backtests(db_path=str(PRODUCTION_DB))
        gdp = results["gdp"]
        if "error" not in gdp:
            assert gdp["n_origins"] >= 5
            assert "aggregate" in gdp
            assert gdp["aggregate"]["mae"] >= 0

    def test_unemployment_backtest_has_origins(self):
        from src.analysis.backtesting import run_backtests

        results = run_backtests(db_path=str(PRODUCTION_DB))
        unemp = results["unemployment"]
        if "error" not in unemp:
            assert unemp["n_origins"] >= 5
            assert unemp["aggregate"]["mape"] >= 0
