"""Tests for the Forecaster class in src/analysis/forecasting.py."""

from pathlib import Path

import pytest

from tests.conftest import PRODUCTION_DB

pytestmark = pytest.mark.skipif(not PRODUCTION_DB.exists(), reason="Production DB not available")


@pytest.fixture(scope="module")
def forecaster():
    from src.analysis.forecasting import Forecaster

    fc = Forecaster(db_path=str(PRODUCTION_DB))
    yield fc
    fc.close()


# -- Static helpers (no DB needed, but grouped here for clarity) --------


class TestStaticHelpers:
    def test_quarterly_labels(self):
        from src.analysis.forecasting import Forecaster

        labels = Forecaster._quarterly_labels("2025-Q4", 4)
        assert labels == ["2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"]

    def test_quarterly_labels_wrap(self):
        from src.analysis.forecasting import Forecaster

        labels = Forecaster._quarterly_labels("2024-Q3", 2)
        assert labels == ["2024-Q4", "2025-Q1"]

    def test_monthly_labels(self):
        from src.analysis.forecasting import Forecaster

        labels = Forecaster._monthly_labels("2025-12", 3)
        assert labels == ["2026-01", "2026-02", "2026-03"]

    def test_monthly_labels_no_wrap(self):
        from src.analysis.forecasting import Forecaster

        labels = Forecaster._monthly_labels("2025-06", 2)
        assert labels == ["2025-07", "2025-08"]


# -- Forecast method validation helper ---------------------------------


def _check_forecast_dict(result, expected_indicator_substr):
    """Common assertions for all forecast methods."""
    assert isinstance(result, dict)
    assert "indicator" in result
    assert expected_indicator_substr.lower() in result["indicator"].lower()
    assert "method" in result
    # Interest rates structure is nested differently
    if "forecast" in result:
        rows = result["forecast"]
        assert isinstance(rows, list)
        assert len(rows) > 0
        row = rows[0]
        for key in ("period", "central", "lower_68", "upper_68"):
            assert key in row, f"Missing key '{key}' in forecast row"


# -- Pillar forecast tests ----------------------------------------------


class TestForecasterGDP:
    def test_forecast_gdp(self, forecaster):
        result = forecaster.forecast_gdp(horizon=4)
        _check_forecast_dict(result, "GDP")
        assert len(result["forecast"]) == 4


class TestForecasterUnemployment:
    def test_forecast_unemployment(self, forecaster):
        result = forecaster.forecast_unemployment(horizon=12)
        _check_forecast_dict(result, "Unemployment")
        assert len(result["forecast"]) == 12


class TestForecasterInflation:
    def test_forecast_inflation(self, forecaster):
        result = forecaster.forecast_inflation(horizon=12)
        _check_forecast_dict(result, "inflation")
        assert len(result["forecast"]) == 12


class TestForecasterInterestRates:
    def test_forecast_interest_rates(self, forecaster):
        result = forecaster.forecast_interest_rates(horizon=12)
        assert isinstance(result, dict)
        assert "indicator" in result
        assert "method" in result
        # Interest rates has nested ecb_rate / euribor_12m
        assert "ecb_rate" in result or "forecast" in result
        if "ecb_rate" in result:
            ecb_rows = result["ecb_rate"]["forecast"]
            assert isinstance(ecb_rows, list)
            assert len(ecb_rows) == 12


class TestForecasterCredit:
    def test_forecast_credit(self, forecaster):
        result = forecaster.forecast_credit(horizon=12)
        _check_forecast_dict(result, "Credit")
        assert len(result["forecast"]) == 12


class TestForecasterPublicDebt:
    def test_forecast_public_debt(self, forecaster):
        result = forecaster.forecast_public_debt(horizon=4)
        assert "error" not in result, f"Public debt forecast returned error: {result.get('error')}"
        _check_forecast_dict(result, "Debt")
        assert len(result["forecast"]) == 4


class TestGenerateAll:
    def test_generate_all_forecasts(self, forecaster):
        results = forecaster.generate_all_forecasts()
        assert isinstance(results, dict)
        expected_keys = {
            "gdp",
            "unemployment",
            "inflation",
            "interest_rates",
            "credit",
            "public_debt",
        }
        assert expected_keys == set(results.keys())
        for key, val in results.items():
            assert "error" not in val, f"{key} forecast returned error: {val.get('error')}"


class TestClose:
    def test_close_is_callable(self):
        from src.analysis.forecasting import Forecaster

        fc = Forecaster(db_path=str(PRODUCTION_DB))
        fc.close()
        # After closing, connection should be unusable
        with pytest.raises(Exception):
            fc._conn.execute("SELECT 1")
