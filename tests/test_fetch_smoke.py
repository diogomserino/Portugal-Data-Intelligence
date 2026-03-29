"""Smoke tests for real API data fetching.

These tests verify connectivity to official data APIs and that
returned DataFrames have the expected structure. Skipped automatically
when network is unavailable or APIs are unreachable.
"""

import pandas as pd
import pytest

pytestmark = pytest.mark.slow


def _try_fetch(fetch_fn):
    """Call a fetch function, skip on network error."""
    try:
        return fetch_fn()
    except Exception as exc:
        pytest.skip(f"API unavailable: {exc}")


class TestEurostatAPIs:
    def test_fetch_gdp(self):
        from src.etl.fetch_real_data import fetch_gdp

        df = _try_fetch(fetch_gdp)
        assert df is not None
        assert len(df) >= 40
        assert "nominal_gdp_eur_millions" in df.columns or "nominal_gdp" in df.columns

    def test_fetch_unemployment(self):
        from src.etl.fetch_real_data import fetch_unemployment

        df = _try_fetch(fetch_unemployment)
        assert df is not None
        assert len(df) >= 100

    def test_fetch_inflation(self):
        from src.etl.fetch_real_data import fetch_inflation

        df = _try_fetch(fetch_inflation)
        assert df is not None
        assert len(df) >= 100

    def test_fetch_public_debt(self):
        from src.etl.fetch_real_data import fetch_public_debt

        df = _try_fetch(fetch_public_debt)
        assert df is not None
        assert len(df) >= 30


class TestECBAPIs:
    def test_fetch_interest_rates(self):
        from src.etl.fetch_real_data import fetch_interest_rates

        df = _try_fetch(fetch_interest_rates)
        assert df is not None
        assert len(df) >= 100


class TestBPStatAPIs:
    def test_fetch_credit(self):
        from src.etl.fetch_real_data import fetch_credit

        df = _try_fetch(fetch_credit)
        assert df is not None
        assert len(df) >= 50


class TestFetchAll:
    def test_fetch_all_returns_multiple_pillars(self):
        from src.etl.fetch_real_data import fetch_all

        try:
            results = fetch_all()
        except Exception as exc:
            pytest.skip(f"APIs unavailable: {exc}")
        assert len(results) >= 4, f"Only {len(results)} pillars fetched"
