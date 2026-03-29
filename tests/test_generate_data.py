"""Tests for the synthetic data generation module (src/etl/generate_data.py).

Validates row counts, column presence, value ranges, and date_key format
for each of the six data pillars.  No network or database access required.
"""

import re

import numpy as np
import pandas as pd
import pytest

from config.settings import END_YEAR, START_YEAR
from src.etl.generate_data import (
    generate_credit,
    generate_gdp,
    generate_inflation,
    generate_interest_rates,
    generate_public_debt,
    generate_unemployment,
)

# ---------------------------------------------------------------------------
# Expected shapes
# ---------------------------------------------------------------------------


_N_YEARS = END_YEAR - START_YEAR + 1
QUARTERLY_ROWS = _N_YEARS * 4
MONTHLY_ROWS = _N_YEARS * 12


# ---------------------------------------------------------------------------
# GDP
# ---------------------------------------------------------------------------


class TestGenerateGDP:

    @pytest.fixture(scope="class")
    def df(self):
        return generate_gdp()

    def test_row_count(self, df):
        assert len(df) == QUARTERLY_ROWS

    def test_expected_columns(self, df):
        for col in [
            "date",
            "year",
            "quarter",
            "nominal_gdp_eur_millions",
            "real_gdp_eur_millions",
            "gdp_growth_rate_yoy",
            "gdp_growth_rate_qoq",
            "gdp_per_capita_eur",
        ]:
            assert col in df.columns, f"Missing column: {col}"

    def test_no_nan_in_primary(self, df):
        assert df["nominal_gdp_eur_millions"].notna().all()
        assert df["real_gdp_eur_millions"].notna().all()

    def test_plausible_nominal_gdp(self, df):
        vals = df["nominal_gdp_eur_millions"]
        assert vals.min() > 30_000, "Quarterly nominal GDP too low"
        assert vals.max() < 100_000, "Quarterly nominal GDP too high"

    def test_year_range(self, df):
        assert df["year"].min() == 2010
        assert df["year"].max() == END_YEAR


# ---------------------------------------------------------------------------
# Unemployment
# ---------------------------------------------------------------------------


class TestGenerateUnemployment:

    @pytest.fixture(scope="class")
    def df(self):
        return generate_unemployment()

    def test_row_count(self, df):
        assert len(df) == MONTHLY_ROWS

    def test_expected_columns(self, df):
        for col in [
            "unemployment_rate",
            "youth_unemployment_rate",
            "long_term_unemployment_rate",
            "labour_force_participation_rate",
        ]:
            assert col in df.columns

    def test_no_nan_in_primary(self, df):
        assert df["unemployment_rate"].notna().all()

    def test_plausible_unemployment(self, df):
        vals = df["unemployment_rate"]
        assert vals.min() >= 3.0
        assert vals.max() <= 20.0

    def test_youth_higher_than_general(self, df):
        assert df["youth_unemployment_rate"].mean() > df["unemployment_rate"].mean()


# ---------------------------------------------------------------------------
# Interest Rates
# ---------------------------------------------------------------------------


class TestGenerateInterestRates:

    @pytest.fixture(scope="class")
    def df(self):
        return generate_interest_rates()

    def test_row_count(self, df):
        assert len(df) == MONTHLY_ROWS

    def test_expected_columns(self, df):
        for col in [
            "ecb_main_refinancing_rate",
            "euribor_3m",
            "euribor_6m",
            "euribor_12m",
            "portugal_10y_bond_yield",
        ]:
            assert col in df.columns

    def test_no_nan_in_ecb_rate(self, df):
        assert df["ecb_main_refinancing_rate"].notna().all()

    def test_ecb_rate_range(self, df):
        vals = df["ecb_main_refinancing_rate"]
        assert vals.min() >= -0.2
        assert vals.max() <= 5.0

    def test_bond_yield_range(self, df):
        vals = df["portugal_10y_bond_yield"]
        assert vals.min() >= 0.0
        assert vals.max() <= 15.0


# ---------------------------------------------------------------------------
# Inflation
# ---------------------------------------------------------------------------


class TestGenerateInflation:

    @pytest.fixture(scope="class")
    def df(self):
        return generate_inflation()

    def test_row_count(self, df):
        assert len(df) == MONTHLY_ROWS

    def test_expected_columns(self, df):
        for col in ["hicp_annual_rate", "cpi_annual_rate", "core_inflation_rate"]:
            assert col in df.columns

    def test_no_nan_in_hicp(self, df):
        assert df["hicp_annual_rate"].notna().all()

    def test_hicp_range(self, df):
        vals = df["hicp_annual_rate"]
        assert vals.min() > -3.0
        assert vals.max() < 12.0


# ---------------------------------------------------------------------------
# Credit
# ---------------------------------------------------------------------------


class TestGenerateCredit:

    @pytest.fixture(scope="class")
    def df(self):
        return generate_credit()

    def test_row_count(self, df):
        assert len(df) == MONTHLY_ROWS

    def test_expected_columns(self, df):
        for col in [
            "total_credit_eur_millions",
            "npl_ratio",
            "nfc_credit_eur_millions",
            "household_credit_eur_millions",
        ]:
            assert col in df.columns

    def test_no_nan_in_total_credit(self, df):
        assert df["total_credit_eur_millions"].notna().all()

    def test_npl_ratio_range(self, df):
        vals = df["npl_ratio"]
        assert vals.min() >= 1.5
        assert vals.max() <= 19.0


# ---------------------------------------------------------------------------
# Public Debt
# ---------------------------------------------------------------------------


class TestGeneratePublicDebt:

    @pytest.fixture(scope="class")
    def df(self):
        return generate_public_debt()

    def test_row_count(self, df):
        assert len(df) == QUARTERLY_ROWS

    def test_expected_columns(self, df):
        for col in [
            "total_debt_eur_millions",
            "debt_to_gdp_ratio",
            "budget_balance_pct_gdp",
            "external_debt_share",
        ]:
            assert col in df.columns

    def test_no_nan_in_debt(self, df):
        assert df["total_debt_eur_millions"].notna().all()

    def test_debt_to_gdp_range(self, df):
        vals = df["debt_to_gdp_ratio"]
        assert vals.min() > 80
        assert vals.max() < 150

    def test_date_column_format(self, df):
        """Every date should be a valid pandas Timestamp."""
        dates = pd.to_datetime(df["date"])
        assert dates.notna().all()
