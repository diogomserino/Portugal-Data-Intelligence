"""Integration tests for the ETL pipeline orchestrator (src/etl/pipeline.py).

These tests require the production database and raw data files to exist.
They are skipped automatically when those artefacts are not available
(e.g. in CI before the first full pipeline run).
"""

from pathlib import Path

import pytest

from config.settings import DATABASE_PATH, RAW_DATA_DIR
from tests.conftest import PRODUCTION_DB

# Skip the entire module if the production database or raw data is missing.
pytestmark = pytest.mark.skipif(
    not PRODUCTION_DB.exists(),
    reason="Production database not available — run 'python main.py' first",
)

EXPECTED_PILLARS = {
    "gdp",
    "unemployment",
    "credit",
    "interest_rates",
    "inflation",
    "public_debt",
}


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


class TestRunExtract:
    """run_extract returns raw DataFrames for all six pillars."""

    @pytest.fixture(scope="class")
    def raw_data(self):
        from src.etl.pipeline import run_extract

        return run_extract()

    def test_returns_dict(self, raw_data):
        assert isinstance(raw_data, dict)

    def test_six_pillars(self, raw_data):
        assert set(raw_data.keys()) == EXPECTED_PILLARS

    def test_dataframes_non_empty(self, raw_data):
        for key, df in raw_data.items():
            assert len(df) > 0, f"Pillar '{key}' DataFrame is empty"

    def test_gdp_has_date_column(self, raw_data):
        assert "date" in raw_data["gdp"].columns


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


class TestRunTransform:
    """run_transform produces processed DataFrames with date_key columns."""

    @pytest.fixture(scope="class")
    def processed_data(self):
        from src.etl.pipeline import run_extract, run_transform

        raw = run_extract()
        return run_transform(raw)

    def test_returns_dict(self, processed_data):
        assert isinstance(processed_data, dict)

    def test_six_pillars(self, processed_data):
        assert set(processed_data.keys()) == EXPECTED_PILLARS

    def test_date_key_present(self, processed_data):
        for key, df in processed_data.items():
            assert "date_key" in df.columns, f"'{key}' missing date_key"

    def test_gdp_columns(self, processed_data):
        expected = {
            "date_key",
            "nominal_gdp",
            "real_gdp",
            "gdp_growth_yoy",
            "gdp_growth_qoq",
            "gdp_per_capita",
        }
        assert expected.issubset(set(processed_data["gdp"].columns))

    def test_unemployment_columns(self, processed_data):
        expected = {
            "date_key",
            "unemployment_rate",
            "youth_unemployment_rate",
        }
        assert expected.issubset(set(processed_data["unemployment"].columns))

    def test_inflation_columns(self, processed_data):
        expected = {"date_key", "hicp", "cpi_estimated", "core_inflation"}
        assert expected.issubset(set(processed_data["inflation"].columns))

    def test_credit_columns(self, processed_data):
        expected = {"date_key", "total_credit", "npl_ratio"}
        assert expected.issubset(set(processed_data["credit"].columns))


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------


class TestDataQualityGate:
    """DataQualityChecker should pass on valid transformed data."""

    @pytest.fixture(scope="class")
    def dq_report(self):
        from src.etl.data_quality import DataQualityChecker
        from src.etl.pipeline import run_extract, run_transform

        raw = run_extract()
        processed = run_transform(raw)
        checker = DataQualityChecker(processed)
        return checker.run_all()

    def test_no_critical_failures(self, dq_report):
        assert (
            not dq_report.has_critical_failure
        ), f"DQ gate has {dq_report.failures} failure(s): " + ", ".join(
            c.name for c in dq_report.checks if c.status == "fail"
        )

    def test_all_pillars_checked(self, dq_report):
        checked = {c.pillar for c in dq_report.checks if c.pillar}
        assert EXPECTED_PILLARS.issubset(checked)

    def test_minimum_checks_ran(self, dq_report):
        assert len(dq_report.checks) >= 15


class TestRunLoadOnProductionDB:
    """Verify production database has expected structure after pipeline run."""

    def test_all_fact_tables_have_rows(self):
        import sqlite3

        conn = sqlite3.connect(str(DATABASE_PATH))
        try:
            for table, min_rows in [
                ("fact_gdp", 40),
                ("fact_unemployment", 100),
                ("fact_inflation", 100),
                ("fact_credit", 100),
                ("fact_interest_rates", 100),
                ("fact_public_debt", 40),
            ]:
                actual = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                assert actual >= min_rows, f"{table}: {actual} rows, expected >= {min_rows}"
        finally:
            conn.close()

    def test_is_provisional_column_in_all_fact_tables(self):
        import sqlite3

        conn = sqlite3.connect(str(DATABASE_PATH))
        try:
            for table in [
                "fact_gdp",
                "fact_unemployment",
                "fact_inflation",
                "fact_credit",
                "fact_interest_rates",
                "fact_public_debt",
            ]:
                cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
                assert "is_provisional" in cols, f"{table} missing is_provisional"
        finally:
            conn.close()

    def test_provisional_flag_has_both_values(self):
        """At least some rows should be provisional and some confirmed."""
        import sqlite3

        conn = sqlite3.connect(str(DATABASE_PATH))
        try:
            for table in ["fact_gdp", "fact_unemployment", "fact_inflation"]:
                n_prov = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE is_provisional = 1"
                ).fetchone()[0]
                n_conf = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE is_provisional = 0"
                ).fetchone()[0]
                assert n_prov > 0, f"{table}: no provisional rows"
                assert n_conf > 0, f"{table}: no confirmed rows"
        finally:
            conn.close()

    def test_cpi_estimated_column_exists(self):
        import sqlite3

        conn = sqlite3.connect(str(DATABASE_PATH))
        try:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(fact_inflation)").fetchall()]
            assert "cpi_estimated" in cols
            assert "cpi" not in cols, "Old 'cpi' column should not exist"
        finally:
            conn.close()

    def test_budget_deficit_annual_exists(self):
        import sqlite3

        conn = sqlite3.connect(str(DATABASE_PATH))
        try:
            cols = [
                row[1] for row in conn.execute("PRAGMA table_info(fact_public_debt)").fetchall()
            ]
            assert "budget_deficit_annual" in cols
            assert "external_debt_share_estimated" in cols
        finally:
            conn.close()


class TestPrintSummary:
    """The summary printer should not crash with valid data."""

    def test_summary_does_not_raise(self):
        from src.etl.pipeline import _print_summary

        _print_summary(
            raw_counts={"gdp": 64, "unemployment": 192},
            processed_counts={"gdp": 64, "unemployment": 192},
            loaded_counts={"gdp": 64, "unemployment": 192},
            elapsed=1.23,
        )
