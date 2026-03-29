"""Unit and integration tests for the ETL pipeline."""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.conftest import (
    DATA_RANGES,
    EXPECTED_DIM_DATE_ROWS,
    EXPECTED_FACT_ROWS,
    EXPECTED_MONTHLY_ROWS,
    EXPECTED_QUARTERLY_ROWS,
    EXPECTED_SOURCES,
)


class TestExtract:
    """Tests for the extract module."""

    def test_raw_files_exist(self):
        """Verify all expected raw CSV files exist after data generation."""
        from config.settings import RAW_DATA_DIR

        expected = [
            "raw_gdp.csv",
            "raw_unemployment.csv",
            "raw_credit.csv",
            "raw_interest_rates.csv",
            "raw_inflation.csv",
            "raw_public_debt.csv",
        ]
        for f in expected:
            assert (RAW_DATA_DIR / f).exists(), f"Missing raw file: {f}"

    def test_extract_all_returns_six_pillars(self, raw_data):
        """extract_all() should return exactly 6 DataFrames."""
        assert len(raw_data) == 6
        assert set(raw_data.keys()) == {
            "gdp",
            "unemployment",
            "credit",
            "interest_rates",
            "inflation",
            "public_debt",
        }

    def test_extract_gdp_row_count(self, raw_data):
        """GDP should have 64 quarterly rows (16 years x 4 quarters)."""
        assert len(raw_data["gdp"]) == EXPECTED_QUARTERLY_ROWS

    def test_extract_unemployment_row_count(self, raw_data):
        """Unemployment should have 192 monthly rows (16 years x 12 months)."""
        assert len(raw_data["unemployment"]) == EXPECTED_MONTHLY_ROWS

    def test_extract_dataframes_not_empty(self, raw_data):
        """All extracted DataFrames should have rows and columns."""
        for pillar, df in raw_data.items():
            assert not df.empty, f"{pillar} DataFrame is empty"
            assert len(df.columns) >= 2, f"{pillar} has fewer than 2 columns"


class TestTransform:
    """Tests for the transform module."""

    def test_transform_gdp_creates_date_key(self, transformed_data):
        """GDP transform should create date_key in YYYY-QN format."""
        df = transformed_data["gdp"]
        assert "date_key" in df.columns
        assert df["date_key"].iloc[0].startswith("20")
        assert "-Q" in df["date_key"].iloc[0]

    def test_transform_unemployment_creates_date_key(self, transformed_data):
        """Unemployment transform should create date_key in YYYY-MM format."""
        df = transformed_data["unemployment"]
        assert "date_key" in df.columns
        assert len(df["date_key"].iloc[0]) == 7  # YYYY-MM

    def test_transform_renames_gdp_columns(self, transformed_data):
        """GDP transform should produce the correct schema columns."""
        expected_cols = {
            "date_key",
            "nominal_gdp",
            "real_gdp",
            "gdp_growth_yoy",
            "gdp_growth_qoq",
            "gdp_per_capita",
            "is_provisional",
        }
        assert expected_cols == set(transformed_data["gdp"].columns)

    def test_transform_clips_unemployment_range(self):
        """Unemployment values should be clipped to valid range."""
        from src.etl.transform import _clip_and_warn

        df = pd.DataFrame({"rate": [-5.0, 50.0, 105.0]})
        result = _clip_and_warn(df, "rate", 0, 100, "test")
        assert result["rate"].min() >= 0
        assert result["rate"].max() <= 100

    def test_transform_preserves_or_interpolates_row_count(self, raw_data, transformed_data):
        """Transform should preserve rows or expand via interpolation (credit, public_debt)."""
        interpolated_pillars = {"credit", "public_debt"}
        for pillar in raw_data:
            raw_count = len(raw_data[pillar])
            trans_count = len(transformed_data[pillar])
            if pillar in interpolated_pillars:
                assert (
                    trans_count >= raw_count
                ), f"{pillar}: transformed ({trans_count}) < raw ({raw_count})"
            else:
                assert (
                    trans_count == raw_count
                ), f"{pillar}: row count changed from {raw_count} to {trans_count}"

    def test_no_null_date_keys(self, transformed_data):
        """All transformed DataFrames should have non-null date_key."""
        for pillar, df in transformed_data.items():
            assert df["date_key"].notna().all(), f"{pillar} has null date_key values"

    def test_no_duplicate_date_keys(self, transformed_data):
        """Transformed DataFrames should not have duplicate date_keys."""
        for pillar, df in transformed_data.items():
            dupes = df["date_key"].duplicated().sum()
            assert dupes == 0, f"{pillar} has {dupes} duplicate date_keys"


class TestLoad:
    """Tests for the database load module."""

    def test_database_exists(self, production_db_path):
        """Database file should exist after pipeline run."""
        assert production_db_path.exists()

    def test_dim_date_has_correct_count(self, db_conn):
        """dim_date should have 192 monthly + 64 quarterly = 256 rows."""
        count = db_conn.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]
        assert (
            count == EXPECTED_DIM_DATE_ROWS
        ), f"dim_date: expected {EXPECTED_DIM_DATE_ROWS}, got {count}"

    def test_dim_source_has_five_sources(self, db_conn):
        """dim_source should have 5 institutional data sources."""
        count = db_conn.execute("SELECT COUNT(*) FROM dim_source").fetchone()[0]
        assert count == EXPECTED_SOURCES

    def test_fact_tables_have_data(self, db_conn):
        """All 6 fact tables should have expected row counts."""
        for table, expected in EXPECTED_FACT_ROWS.items():
            count = db_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == expected, f"{table}: expected {expected}, got {count}"

    def test_foreign_keys_valid_date(self, db_conn):
        """All fact table date_keys should exist in dim_date."""
        tables = list(EXPECTED_FACT_ROWS.keys())
        for table in tables:
            orphans = db_conn.execute(
                f"SELECT COUNT(*) FROM {table} f "
                f"LEFT JOIN dim_date d ON f.date_key = d.date_key "
                f"WHERE d.date_key IS NULL"
            ).fetchone()[0]
            assert orphans == 0, f"{table} has {orphans} orphan date_keys"

    def test_foreign_keys_valid_source(self, db_conn):
        """All fact table source_keys should exist in dim_source."""
        tables = list(EXPECTED_FACT_ROWS.keys())
        for table in tables:
            orphans = db_conn.execute(
                f"SELECT COUNT(*) FROM {table} f "
                f"LEFT JOIN dim_source s ON f.source_key = s.source_key "
                f"WHERE f.source_key IS NOT NULL AND s.source_key IS NULL"
            ).fetchone()[0]
            assert orphans == 0, f"{table} has {orphans} orphan source_keys"

    def test_no_duplicate_records(self, db_conn):
        """Fact tables should not have duplicate (date_key, source_key) pairs."""
        tables = list(EXPECTED_FACT_ROWS.keys())
        for table in tables:
            dupes = db_conn.execute(
                f"SELECT date_key, source_key, COUNT(*) as cnt "
                f"FROM {table} GROUP BY date_key, source_key HAVING cnt > 1"
            ).fetchall()
            assert (
                len(dupes) == 0
            ), f"{table} has {len(dupes)} duplicate (date_key, source_key) pairs"


class TestDataQuality:
    """Tests for data quality and plausible value ranges."""

    def test_unemployment_rate_in_range(self, db_conn):
        """Unemployment rate should be within plausible bounds (0-20%)."""
        lo, hi = DATA_RANGES["unemployment_rate"]
        rows = db_conn.execute(
            f"SELECT COUNT(*) FROM fact_unemployment "
            f"WHERE unemployment_rate < {lo} OR unemployment_rate > {hi}"
        ).fetchone()[0]
        assert rows == 0, f"{rows} unemployment values outside [{lo}, {hi}]%"

    def test_gdp_growth_in_range(self, db_conn):
        """GDP YoY growth should be within plausible bounds."""
        lo, hi = DATA_RANGES["gdp_growth_yoy"]
        rows = db_conn.execute(
            f"SELECT COUNT(*) FROM fact_gdp "
            f"WHERE gdp_growth_yoy IS NOT NULL "
            f"AND (gdp_growth_yoy < {lo} OR gdp_growth_yoy > {hi})"
        ).fetchone()[0]
        assert rows == 0, f"{rows} GDP growth values outside [{lo}, {hi}]%"

    def test_inflation_in_range(self, db_conn):
        """HICP should be within plausible bounds."""
        lo, hi = DATA_RANGES["hicp"]
        rows = db_conn.execute(
            f"SELECT COUNT(*) FROM fact_inflation " f"WHERE hicp < {lo} OR hicp > {hi}"
        ).fetchone()[0]
        assert rows == 0, f"{rows} HICP values outside [{lo}, {hi}]%"

    def test_debt_ratio_in_range(self, db_conn):
        """Debt-to-GDP ratio should be within plausible bounds."""
        lo, hi = DATA_RANGES["debt_to_gdp_ratio"]
        rows = db_conn.execute(
            f"SELECT COUNT(*) FROM fact_public_debt "
            f"WHERE debt_to_gdp_ratio IS NOT NULL "
            f"AND (debt_to_gdp_ratio < {lo} OR debt_to_gdp_ratio > {hi})"
        ).fetchone()[0]
        assert rows == 0, f"{rows} debt-to-GDP values outside [{lo}, {hi}]%"

    def test_interest_rates_in_range(self, db_conn):
        """ECB rate and bond yield should be within plausible bounds."""
        for col, (lo, hi) in [
            ("ecb_main_refinancing_rate", DATA_RANGES["ecb_main_refinancing_rate"]),
            ("portugal_10y_bond_yield", DATA_RANGES["portugal_10y_bond_yield"]),
        ]:
            rows = db_conn.execute(
                f"SELECT COUNT(*) FROM fact_interest_rates "
                f"WHERE {col} IS NOT NULL AND ({col} < {lo} OR {col} > {hi})"
            ).fetchone()[0]
            assert rows == 0, f"{rows} {col} values outside [{lo}, {hi}]%"

    def test_no_null_primary_metrics(self, db_conn):
        """Primary metrics should not be null."""
        checks = [
            ("fact_gdp", "nominal_gdp"),
            ("fact_unemployment", "unemployment_rate"),
            ("fact_credit", "total_credit"),
            ("fact_inflation", "hicp"),
            ("fact_public_debt", "total_debt"),
        ]
        for table, col in checks:
            nulls = db_conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL").fetchone()[
                0
            ]
            assert nulls == 0, f"{table}.{col} has {nulls} null values"

    def test_date_keys_cover_full_range(self, db_conn):
        """All years from 2010 to 2025 should be present in dim_date."""
        years = db_conn.execute("SELECT DISTINCT year FROM dim_date ORDER BY year").fetchall()
        year_set = {r[0] for r in years}
        expected = set(range(2010, 2026))
        assert year_set == expected, f"Missing years: {expected - year_set}"
