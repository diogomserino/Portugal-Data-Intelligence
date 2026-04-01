"""Data validation tests — verify database integrity and cross-pillar consistency."""

import sqlite3

import numpy as np
import pandas as pd
import pytest

from tests.conftest import (
    DATA_RANGES,
    EXPECTED_FACT_ROWS,
    EXPECTED_MONTHLY_ROWS,
    EXPECTED_QUARTERLY_ROWS,
)

# ============================================================================
# TEMPORAL COMPLETENESS
# ============================================================================


class TestTemporalCompleteness:
    """Verify every expected time period exists in the data."""

    def test_monthly_tables_cover_all_months(self, db_conn):
        """Monthly fact tables should have data for every month 2010-01 to 2025-12."""
        monthly_tables = [
            "fact_unemployment",
            "fact_credit",
            "fact_interest_rates",
            "fact_inflation",
        ]
        for table in monthly_tables:
            df = pd.read_sql(
                f"SELECT DISTINCT d.year, d.month "
                f"FROM {table} f JOIN dim_date d ON f.date_key = d.date_key "
                f"ORDER BY d.year, d.month",
                db_conn,
            )
            expected = set()
            for y in range(2010, 2026):
                for m in range(1, 13):
                    expected.add((y, m))
            actual = set(zip(df["year"], df["month"]))
            missing = sorted(expected - actual)
            assert len(missing) == 0, f"{table} missing {len(missing)} months: {missing[:5]}..."

    def test_quarterly_tables_cover_all_quarters(self, db_conn):
        """Quarterly fact tables should have data for every quarter 2010-Q1 to 2025-Q4."""
        for table in ["fact_gdp", "fact_public_debt"]:
            df = pd.read_sql(
                f"SELECT DISTINCT d.year, d.quarter "
                f"FROM {table} f JOIN dim_date d ON f.date_key = d.date_key "
                f"ORDER BY d.year, d.quarter",
                db_conn,
            )
            expected = set()
            for y in range(2010, 2026):
                for q in range(1, 5):
                    expected.add((y, q))
            actual = set(zip(df["year"], df["quarter"]))
            missing = sorted(expected - actual)
            assert len(missing) == 0, f"{table} missing {len(missing)} quarters: {missing}"

    def test_dim_date_has_no_monthly_gaps(self, db_conn):
        """dim_date should have continuous monthly entries 2010-01 to 2025-12."""
        df = pd.read_sql(
            "SELECT year, month FROM dim_date "
            "WHERE LENGTH(date_key) = 7 "  # YYYY-MM only, exclude YYYY-QN
            "ORDER BY year, month",
            db_conn,
        )
        actual = set(zip(df["year"], df["month"]))
        expected = {(y, m) for y in range(2010, 2026) for m in range(1, 13)}
        missing = sorted(expected - actual)
        assert len(missing) == 0, f"dim_date missing {len(missing)} months: {missing[:5]}"


# ============================================================================
# CROSS-PILLAR CONSISTENCY
# ============================================================================


class TestCrossPillarConsistency:
    """Verify relationships between different fact tables are coherent."""

    def test_hicp_differs_from_cpi_estimated(self, db_conn):
        """HICP and cpi_estimated should NOT be identical."""
        df = pd.read_sql("SELECT hicp, cpi_estimated FROM fact_inflation", db_conn)
        max_diff = (df["hicp"] - df["cpi_estimated"]).abs().max()
        assert (
            max_diff > 0.01
        ), f"HICP and cpi_estimated are identical (max diff={max_diff:.6f}) — offset not applied"

    def test_credit_components_less_than_total(self, db_conn):
        """NFC + household credit should not exceed total credit."""
        df = pd.read_sql(
            "SELECT total_credit, credit_nfc, credit_households FROM fact_credit",
            db_conn,
        )
        df["sum_parts"] = df["credit_nfc"] + df["credit_households"]
        exceeds = df[df["sum_parts"] > df["total_credit"] * 1.001]  # 0.1% tolerance
        assert len(exceeds) == 0, f"{len(exceeds)} rows where NFC + households > total credit"

    def test_euribor_term_structure_ordering(self, db_conn):
        """3M Euribor should generally not exceed 12M (normal curve).

        Allow up to 30% of months to be inverted (rate hiking cycles).
        """
        df = pd.read_sql(
            "SELECT euribor_3m, euribor_12m FROM fact_interest_rates "
            "WHERE euribor_3m IS NOT NULL AND euribor_12m IS NOT NULL",
            db_conn,
        )
        inverted = (df["euribor_3m"] > df["euribor_12m"]).sum()
        pct = inverted / len(df) * 100
        assert pct < 30, f"Euribor curve inverted {pct:.0f}% of months (max 30%)"

    def test_youth_unemployment_exceeds_general(self, db_conn):
        """Youth unemployment rate should always be >= general rate."""
        df = pd.read_sql(
            "SELECT unemployment_rate, youth_unemployment_rate "
            "FROM fact_unemployment "
            "WHERE youth_unemployment_rate IS NOT NULL",
            db_conn,
        )
        violations = df[df["youth_unemployment_rate"] < df["unemployment_rate"]]
        assert (
            len(violations) == 0
        ), f"{len(violations)} months where youth unemployment < general unemployment"

    def test_budget_deficit_in_plausible_range(self, db_conn):
        """Budget deficit should be within [-25%, +10%] of GDP (quarterly values can be extreme)."""
        df = pd.read_sql(
            "SELECT budget_deficit FROM fact_public_debt " "WHERE budget_deficit IS NOT NULL",
            db_conn,
        )
        out_of_range = df[(df["budget_deficit"] < -25) | (df["budget_deficit"] > 10)]
        assert (
            len(out_of_range) == 0
        ), f"{len(out_of_range)} quarters with budget deficit outside [-25%, +10%]"

    def test_npl_ratio_in_plausible_range(self, db_conn):
        """NPL ratio should be between 0% and 20%."""
        lo, hi = DATA_RANGES["npl_ratio"]
        df = pd.read_sql(
            f"SELECT npl_ratio FROM fact_credit "
            f"WHERE npl_ratio IS NOT NULL "
            f"AND (npl_ratio < {lo} OR npl_ratio > {hi})",
            db_conn,
        )
        assert len(df) == 0, f"{len(df)} NPL values outside [{lo}, {hi}]%"

    def test_external_debt_share_estimated_populated(self, db_conn):
        """external_debt_share_estimated should not be 100% null."""
        nulls = db_conn.execute(
            "SELECT COUNT(*) FROM fact_public_debt WHERE external_debt_share_estimated IS NULL"
        ).fetchone()[0]
        total = db_conn.execute("SELECT COUNT(*) FROM fact_public_debt").fetchone()[0]
        assert nulls < total, "external_debt_share_estimated is 100% null"


# ============================================================================
# MONOTONICITY & TREND SANITY
# ============================================================================


class TestTrendSanity:
    """Verify basic economic trends are directionally correct."""

    def test_nominal_gdp_grows_over_period(self, db_conn):
        """Nominal GDP in 2025 should exceed nominal GDP in 2010."""
        first = db_conn.execute(
            "SELECT AVG(nominal_gdp) FROM fact_gdp f "
            "JOIN dim_date d ON f.date_key = d.date_key WHERE d.year = 2010"
        ).fetchone()[0]
        last = db_conn.execute(
            "SELECT AVG(nominal_gdp) FROM fact_gdp f "
            "JOIN dim_date d ON f.date_key = d.date_key WHERE d.year = 2025"
        ).fetchone()[0]
        assert last > first, f"Nominal GDP did not grow: 2010={first}, 2025={last}"

    def test_debt_ratio_decreased_from_peak(self, db_conn):
        """Debt/GDP should be lower in 2025 than the peak (~2013-2014)."""
        peak = db_conn.execute("SELECT MAX(debt_to_gdp_ratio) FROM fact_public_debt").fetchone()[0]
        latest = db_conn.execute(
            "SELECT debt_to_gdp_ratio FROM fact_public_debt f "
            "JOIN dim_date d ON f.date_key = d.date_key "
            "ORDER BY d.year DESC, d.quarter DESC LIMIT 1"
        ).fetchone()[0]
        assert latest < peak, f"Debt/GDP not below peak: latest={latest}, peak={peak}"

    def test_npl_declined_from_peak(self, db_conn):
        """NPL ratio should be lower in 2025 than the peak."""
        peak = db_conn.execute(
            "SELECT MAX(npl_ratio) FROM fact_credit WHERE npl_ratio IS NOT NULL"
        ).fetchone()[0]
        latest = db_conn.execute(
            "SELECT npl_ratio FROM fact_credit f "
            "JOIN dim_date d ON f.date_key = d.date_key "
            "WHERE npl_ratio IS NOT NULL "
            "ORDER BY d.year DESC, d.month DESC LIMIT 1"
        ).fetchone()[0]
        assert latest < peak, f"NPL not below peak: latest={latest}, peak={peak}"

    def test_unemployment_below_peak(self, db_conn):
        """Unemployment in 2025 should be below the 2013 peak."""
        peak = db_conn.execute("SELECT MAX(unemployment_rate) FROM fact_unemployment").fetchone()[0]
        latest = db_conn.execute(
            "SELECT unemployment_rate FROM fact_unemployment f "
            "JOIN dim_date d ON f.date_key = d.date_key "
            "ORDER BY d.year DESC, d.month DESC LIMIT 1"
        ).fetchone()[0]
        assert (
            latest < peak * 0.5
        ), f"Unemployment not substantially below peak: latest={latest}, peak={peak}"


# ============================================================================
# BENCHMARK DATA
# ============================================================================


class TestBenchmarkData:
    """Verify EU benchmark table integrity."""

    def test_benchmark_table_has_data(self, db_conn):
        count = db_conn.execute("SELECT COUNT(*) FROM fact_eu_benchmark").fetchone()[0]
        assert count > 0, "fact_eu_benchmark is empty"

    def test_benchmark_has_all_countries(self, db_conn):
        countries = db_conn.execute(
            "SELECT DISTINCT country_code FROM fact_eu_benchmark ORDER BY country_code"
        ).fetchall()
        codes = {r[0] for r in countries}
        expected = {"PT", "DE", "ES", "FR", "IT", "EU_AVG", "EA_AVG"}
        assert codes == expected, f"Missing countries: {expected - codes}"

    def test_benchmark_has_all_indicators(self, db_conn):
        indicators = db_conn.execute(
            "SELECT DISTINCT indicator FROM fact_eu_benchmark ORDER BY indicator"
        ).fetchall()
        names = {r[0] for r in indicators}
        expected = {"gdp_growth", "unemployment", "inflation", "debt_to_gdp", "interest_rate_10y"}
        assert names == expected, f"Missing indicators: {expected - names}"

    def test_benchmark_has_all_years(self, db_conn):
        years = db_conn.execute(
            "SELECT DISTINCT date_key FROM fact_eu_benchmark ORDER BY date_key"
        ).fetchall()
        year_set = {int(r[0]) for r in years}
        expected = set(range(2010, 2026))
        assert year_set == expected, f"Missing years: {expected - year_set}"

    def test_benchmark_no_null_values(self, db_conn):
        nulls = db_conn.execute(
            "SELECT COUNT(*) FROM fact_eu_benchmark WHERE value IS NULL"
        ).fetchone()[0]
        assert nulls == 0, f"{nulls} null values in benchmark data"
