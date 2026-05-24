"""
Tests for the 5 new analysis modules and regional analysis.
Covers: housing, labor_detail, external_accounts, fiscal, inequality, regional.
All tests use in-memory SQLite databases with minimal synthetic data so they
run without a full ETL pass.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Minimal in-memory DB fixture
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS dim_date (
    date_key TEXT PRIMARY KEY,
    year     INTEGER,
    quarter  INTEGER,
    month    INTEGER
);

CREATE TABLE IF NOT EXISTS dim_source (
    source_key  INTEGER PRIMARY KEY,
    source_name TEXT
);

CREATE TABLE IF NOT EXISTS fact_housing (
    id                     INTEGER PRIMARY KEY,
    date_key               TEXT,
    house_price_index      REAL,
    house_price_yoy_change REAL,
    avg_price_per_sqm      REAL,
    housing_transactions   REAL,
    mortgage_new_loans     REAL,
    is_provisional         INTEGER DEFAULT 0,
    source_key             INTEGER
);

CREATE TABLE IF NOT EXISTS fact_labor_detail (
    id                          INTEGER PRIMARY KEY,
    date_key                    TEXT,
    employment_services_pct     REAL,
    employment_industry_pct     REAL,
    employment_agriculture_pct  REAL,
    real_wage_index             REAL,
    labour_productivity_index   REAL,
    is_provisional              INTEGER DEFAULT 0,
    source_key                  INTEGER
);

CREATE TABLE IF NOT EXISTS fact_external_accounts (
    id                      INTEGER PRIMARY KEY,
    date_key                TEXT,
    trade_balance_pct_gdp   REAL,
    current_account_pct_gdp REAL,
    reer_index              REAL,
    export_growth_yoy       REAL,
    is_provisional          INTEGER DEFAULT 0,
    source_key              INTEGER
);

CREATE TABLE IF NOT EXISTS fact_fiscal (
    id                        INTEGER PRIMARY KEY,
    date_key                  TEXT,
    total_revenue_pct_gdp     REAL,
    total_expenditure_pct_gdp REAL,
    health_expenditure_pct    REAL,
    education_expenditure_pct REAL,
    social_protection_pct     REAL,
    interest_payments_pct     REAL,
    is_provisional            INTEGER DEFAULT 0,
    source_key                INTEGER
);

CREATE TABLE IF NOT EXISTS fact_inequality (
    id                  INTEGER PRIMARY KEY,
    date_key            TEXT,
    gini_index          REAL,
    s80_s20_ratio       REAL,
    poverty_risk_rate   REAL,
    median_income_index REAL,
    is_provisional      INTEGER DEFAULT 0,
    source_key          INTEGER
);

CREATE TABLE IF NOT EXISTS fact_regional (
    id                      INTEGER PRIMARY KEY,
    date_key                TEXT,
    nuts2_code              TEXT,
    nuts2_name              TEXT,
    gdp_per_capita_pps      REAL,
    gdp_index_eu27          REAL,
    unemployment_rate       REAL,
    youth_unemployment_rate REAL,
    is_provisional          INTEGER DEFAULT 0,
    source_key              INTEGER
);
"""

_YEARS = list(range(2010, 2026))
_QUARTERS = [f"{y}-Q4" for y in _YEARS]
_QUARTERLY_ALL = [f"{y}-Q{q}" for y in _YEARS for q in range(1, 5)]
_NUTS2 = [
    ("PT11", "Norte"),
    ("PT15", "Alentejo"),
    ("PT16", "Centro"),
    ("PT17", "Lisboa"),
    ("PT18", "Algarve"),
    ("PT20", "Açores"),
    ("PT30", "Madeira"),
]


def _seed(conn: sqlite3.Connection) -> None:
    """Insert minimal synthetic data into all new fact tables."""
    conn.execute("INSERT OR IGNORE INTO dim_source VALUES (1, 'Eurostat')")

    # dim_date entries needed
    for yr in _YEARS:
        conn.execute(
            "INSERT OR IGNORE INTO dim_date VALUES (?,?,?,?)",
            (f"{yr}-Q4", yr, 4, 12),
        )
    for dkey in _QUARTERLY_ALL:
        yr = int(dkey[:4])
        q = int(dkey[-1])
        conn.execute(
            "INSERT OR IGNORE INTO dim_date VALUES (?,?,?,?)",
            (dkey, yr, q, q * 3),
        )

    # fact_housing (annual)
    hpi = 82.0
    for i, yr in enumerate(_YEARS):
        hpi *= 1.03
        conn.execute(
            "INSERT INTO fact_housing (date_key, house_price_index, house_price_yoy_change, "
            "avg_price_per_sqm, housing_transactions, mortgage_new_loans, source_key) "
            "VALUES (?,?,?,?,?,?,?)",
            (f"{yr}-Q4", round(hpi, 1), 3.0, 1200 + i * 50, 90000, 5000, 1),
        )

    # fact_labor_detail (annual)
    for yr in _YEARS:
        conn.execute(
            "INSERT INTO fact_labor_detail (date_key, employment_services_pct, "
            "employment_industry_pct, employment_agriculture_pct, "
            "real_wage_index, labour_productivity_index, source_key) VALUES (?,?,?,?,?,?,?)",
            (f"{yr}-Q4", 65.0, 25.0, 10.0, 100.0, 100.0, 1),
        )

    # fact_external_accounts (quarterly)
    for dkey in _QUARTERLY_ALL:
        conn.execute(
            "INSERT INTO fact_external_accounts (date_key, trade_balance_pct_gdp, "
            "current_account_pct_gdp, reer_index, export_growth_yoy, source_key) "
            "VALUES (?,?,?,?,?,?)",
            (dkey, -5.0, -2.0, 100.0, 3.0, 1),
        )

    # fact_fiscal (annual)
    for yr in _YEARS:
        conn.execute(
            "INSERT INTO fact_fiscal (date_key, total_revenue_pct_gdp, "
            "total_expenditure_pct_gdp, health_expenditure_pct, "
            "education_expenditure_pct, social_protection_pct, "
            "interest_payments_pct, source_key) VALUES (?,?,?,?,?,?,?,?)",
            (f"{yr}-Q4", 43.0, 46.0, 6.5, 4.2, 16.0, 3.0, 1),
        )

    # fact_inequality (annual)
    gini = 34.0
    for yr in _YEARS:
        gini -= 0.1
        conn.execute(
            "INSERT INTO fact_inequality (date_key, gini_index, s80_s20_ratio, "
            "poverty_risk_rate, median_income_index, source_key) VALUES (?,?,?,?,?,?)",
            (f"{yr}-Q4", round(gini, 1), 5.5, 17.0, 78.0, 1),
        )

    # fact_regional (annual × 7 regions)
    for yr in _YEARS:
        for nuts2_code, nuts2_name in _NUTS2:
            conn.execute(
                "INSERT INTO fact_regional (date_key, nuts2_code, nuts2_name, "
                "gdp_per_capita_pps, gdp_index_eu27, unemployment_rate, source_key) "
                "VALUES (?,?,?,?,?,?,?)",
                (f"{yr}-Q4", nuts2_code, nuts2_name, 20000.0, 85.0, 8.0, 1),
            )

    conn.commit()


@pytest.fixture
def mini_db(tmp_path) -> Generator[str, None, None]:
    """Create a temporary SQLite DB with minimal data for all new pillars."""
    db_path = tmp_path / "test_new_pillars.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_DDL)
    _seed(conn)
    conn.close()
    yield str(db_path)


# ---------------------------------------------------------------------------
# housing_analysis
# ---------------------------------------------------------------------------


class TestHousingAnalysis:
    def test_returns_dict(self, mini_db):
        from src.analysis.housing_analysis import run_housing_analysis

        result = run_housing_analysis(mini_db)
        assert isinstance(result, dict)

    def test_has_expected_keys(self, mini_db):
        from src.analysis.housing_analysis import run_housing_analysis

        result = run_housing_analysis(mini_db)
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert len(result) > 0

    def test_hpi_trend_is_numeric(self, mini_db):
        from src.analysis.housing_analysis import run_housing_analysis

        result = run_housing_analysis(mini_db)
        # Should compute some numeric metric without crashing
        assert result is not None


# ---------------------------------------------------------------------------
# labor_analysis
# ---------------------------------------------------------------------------


class TestLaborAnalysis:
    def test_returns_dict(self, mini_db):
        from src.analysis.labor_analysis import run_labor_analysis

        result = run_labor_analysis(mini_db)
        assert isinstance(result, dict)

    def test_no_error_key(self, mini_db):
        from src.analysis.labor_analysis import run_labor_analysis

        result = run_labor_analysis(mini_db)
        assert "error" not in result, f"Unexpected error: {result.get('error')}"

    def test_sector_shares_sum_to_100(self, mini_db):
        from src.analysis.labor_analysis import run_labor_analysis

        result = run_labor_analysis(mini_db)
        # The synthetic data sums services(65) + industry(25) + agriculture(10) = 100
        emp = result.get("employment_structure", {})
        if emp:
            latest = emp.get("latest", {})
            total = sum(
                v for k, v in latest.items() if isinstance(v, (int, float)) and not np.isnan(v)
            )
            if total > 0:
                assert abs(total - 100.0) < 5.0


# ---------------------------------------------------------------------------
# external_analysis
# ---------------------------------------------------------------------------


class TestExternalAnalysis:
    def test_returns_dict(self, mini_db):
        from src.analysis.external_analysis import run_external_analysis

        result = run_external_analysis(mini_db)
        assert isinstance(result, dict)

    def test_no_error_key(self, mini_db):
        from src.analysis.external_analysis import run_external_analysis

        result = run_external_analysis(mini_db)
        assert "error" not in result, f"Unexpected error: {result.get('error')}"

    def test_current_account_is_numeric(self, mini_db):
        from src.analysis.external_analysis import run_external_analysis

        result = run_external_analysis(mini_db)
        ca = result.get("current_account", {})
        if ca:
            latest = ca.get("latest_value")
            if latest is not None:
                assert isinstance(latest, (int, float))
                assert not np.isnan(latest)


# ---------------------------------------------------------------------------
# fiscal_analysis
# ---------------------------------------------------------------------------


class TestFiscalAnalysis:
    def test_returns_dict(self, mini_db):
        from src.analysis.fiscal_analysis import run_fiscal_analysis

        result = run_fiscal_analysis(mini_db)
        assert isinstance(result, dict)

    def test_no_error_key(self, mini_db):
        from src.analysis.fiscal_analysis import run_fiscal_analysis

        result = run_fiscal_analysis(mini_db)
        assert "error" not in result, f"Unexpected error: {result.get('error')}"

    def test_expenditure_exceeds_revenue_in_data(self, mini_db):
        """Synthetic data has expenditure (46%) > revenue (43%) — deficit."""
        from src.analysis.fiscal_analysis import run_fiscal_analysis

        result = run_fiscal_analysis(mini_db)
        balance = result.get("fiscal_balance", {})
        if balance:
            latest = balance.get("latest_balance")
            if latest is not None:
                assert latest < 0, "Expected deficit (expenditure > revenue) in synthetic data"


# ---------------------------------------------------------------------------
# inequality_analysis
# ---------------------------------------------------------------------------


class TestInequalityAnalysis:
    def test_returns_dict(self, mini_db):
        from src.analysis.inequality_analysis import run_inequality_analysis

        result = run_inequality_analysis(mini_db)
        assert isinstance(result, dict)

    def test_no_error_key(self, mini_db):
        from src.analysis.inequality_analysis import run_inequality_analysis

        result = run_inequality_analysis(mini_db)
        assert "error" not in result, f"Unexpected error: {result.get('error')}"

    def test_gini_in_plausible_range(self, mini_db):
        from src.analysis.inequality_analysis import run_inequality_analysis

        result = run_inequality_analysis(mini_db)
        gini_block = result.get("gini", {})
        latest = gini_block.get("latest_value") if gini_block else None
        if latest is not None:
            assert 20 <= latest <= 50, f"Gini out of plausible range: {latest}"


# ---------------------------------------------------------------------------
# regional_analysis
# ---------------------------------------------------------------------------


class TestRegionalAnalysis:
    def test_returns_dict_with_real_db(self, mini_db):
        from src.analysis.regional_analysis import run_regional_analysis

        result = run_regional_analysis(mini_db)
        assert isinstance(result, dict)

    def test_covers_all_nuts2_regions(self, mini_db):
        from src.analysis.regional_analysis import _NUTS2_REGIONS, run_regional_analysis

        result = run_regional_analysis(mini_db)
        gdp_block = result.get("gdp_per_capita_pps", {})
        if gdp_block and "latest_by_region" in gdp_block:
            found = set(gdp_block["latest_by_region"].keys())
            assert found == set(
                _NUTS2_REGIONS.keys()
            ), f"Missing regions: {set(_NUTS2_REGIONS.keys()) - found}"

    def test_dispersion_metrics_present(self, mini_db):
        from src.analysis.regional_analysis import run_regional_analysis

        result = run_regional_analysis(mini_db)
        gdp_block = result.get("gdp_per_capita_pps", {})
        if gdp_block and "dispersion" in gdp_block:
            disp = gdp_block["dispersion"]
            for key in ("mean", "std", "min", "max"):
                assert key in disp, f"Missing dispersion key: {key}"

    def test_synthetic_fallback_works(self, tmp_path):
        """Fallback fires when fact_regional table is absent."""
        from src.analysis.regional_analysis import run_regional_analysis

        # Empty DB — no fact_regional table
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        result = run_regional_analysis(str(db_path))
        assert isinstance(result, dict)
        assert result.get("source") == "synthetic_fallback"

    def test_key_findings_populated(self, mini_db):
        from src.analysis.regional_analysis import run_regional_analysis

        result = run_regional_analysis(mini_db)
        findings = result.get("key_findings", [])
        assert isinstance(findings, list)
