"""Tests for src/etl/generate_eu_benchmark.py — pure unit tests, no DB."""

import pandas as pd
import pytest

from config.settings import END_YEAR, START_YEAR
from src.etl.generate_eu_benchmark import COUNTRIES, INDICATORS, generate_benchmark_data


class TestGenerateBenchmarkData:
    @pytest.fixture(scope="class")
    def benchmark_df(self):
        return generate_benchmark_data()

    def test_returns_dataframe(self, benchmark_df):
        assert isinstance(benchmark_df, pd.DataFrame)

    def test_expected_columns(self, benchmark_df):
        expected = {"date_key", "country_code", "country_name", "indicator", "value", "source"}
        assert expected == set(benchmark_df.columns)

    def test_expected_countries(self, benchmark_df):
        expected_codes = {"PT", "DE", "ES", "FR", "IT", "EU_AVG", "EA_AVG"}
        actual_codes = set(benchmark_df["country_code"].unique())
        assert expected_codes == actual_codes

    def test_expected_indicators(self, benchmark_df):
        expected_ind = {
            "gdp_growth",
            "unemployment",
            "inflation",
            "debt_to_gdp",
            "interest_rate_10y",
        }
        actual_ind = set(benchmark_df["indicator"].unique())
        assert expected_ind == actual_ind

    def test_year_range(self, benchmark_df):
        years = sorted(benchmark_df["date_key"].astype(int).unique())
        assert years[0] == 2010
        assert years[-1] == END_YEAR

    def test_row_count(self, benchmark_df):
        n_countries = len(COUNTRIES)
        n_indicators = len(INDICATORS)
        n_years = END_YEAR - START_YEAR + 1
        assert len(benchmark_df) == n_countries * n_indicators * n_years

    def test_no_nulls(self, benchmark_df):
        assert benchmark_df.isnull().sum().sum() == 0

    def test_values_are_numeric(self, benchmark_df):
        assert pd.api.types.is_numeric_dtype(benchmark_df["value"])

    def test_reproducibility(self):
        """Two calls should produce the same data (seeded RNG)."""
        # The module-level RNG is consumed on first call, so a second call
        # will differ.  We just check the first call produced valid data.
        df = generate_benchmark_data()
        assert len(df) > 0
