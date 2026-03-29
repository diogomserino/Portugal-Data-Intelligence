"""Shared pytest fixtures for Portugal Data Intelligence tests."""

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on the Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATABASE_PATH, PROCESSED_DATA_DIR, RAW_DATA_DIR

# Module-level constant for use in skipif decorators (where fixtures cannot be used).
PRODUCTION_DB = DATABASE_PATH


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def production_db_path():
    """Path to the production database (read-only access for tests)."""
    if not DATABASE_PATH.exists():
        pytest.skip("Production database not found — run 'python main.py' first")
    return DATABASE_PATH


@pytest.fixture(scope="session")
def db_conn(production_db_path):
    """Session-scoped read-only connection to the production database."""
    conn = sqlite3.connect(str(production_db_path))
    conn.execute("PRAGMA query_only = ON")
    yield conn
    conn.close()


@pytest.fixture()
def isolated_db(tmp_path):
    """Function-scoped isolated test database with schema but no data.

    Returns a tuple (db_path, connection).  The database is destroyed
    after the test.
    """
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    # Apply schema from DDL files
    ddl_dir = PROJECT_ROOT / "sql" / "ddl"
    for ddl_file in sorted(ddl_dir.glob("*.sql")):
        conn.executescript(ddl_file.read_text(encoding="utf-8"))
    conn.commit()

    yield str(db_path), conn
    conn.close()


# ---------------------------------------------------------------------------
# Data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def raw_data():
    """Session-scoped raw DataFrames from extract_all()."""
    from src.etl.extract import extract_all

    data = extract_all()
    if not data:
        pytest.skip("No raw data available — run data generation first")
    return data


@pytest.fixture(scope="session")
def transformed_data(raw_data):
    """Session-scoped transformed DataFrames from transform_all()."""
    from src.etl.transform import transform_all

    return transform_all(raw_data)


# ---------------------------------------------------------------------------
# Expected counts (documented constants, not magic numbers)
# ---------------------------------------------------------------------------

from config.settings import END_YEAR, START_YEAR

EXPECTED_YEARS = END_YEAR - START_YEAR + 1
# Monthly: 16 years × 12 months = 192
EXPECTED_MONTHLY_ROWS = EXPECTED_YEARS * 12
# Quarterly: 16 years × 4 quarters = 64
EXPECTED_QUARTERLY_ROWS = EXPECTED_YEARS * 4
# dim_date: monthly + quarterly entries = 192 + 64 = 256
EXPECTED_DIM_DATE_ROWS = EXPECTED_MONTHLY_ROWS + EXPECTED_QUARTERLY_ROWS
# dim_source: INE, Banco de Portugal, PORDATA, Eurostat, ECB
EXPECTED_SOURCES = 5

# Fact table expected row counts
EXPECTED_FACT_ROWS = {
    "fact_gdp": EXPECTED_QUARTERLY_ROWS,
    "fact_unemployment": EXPECTED_MONTHLY_ROWS,
    "fact_credit": EXPECTED_MONTHLY_ROWS,
    "fact_interest_rates": EXPECTED_MONTHLY_ROWS,
    "fact_inflation": EXPECTED_MONTHLY_ROWS,
    "fact_public_debt": EXPECTED_QUARTERLY_ROWS,
}

# EU Benchmark: 7 countries × 5 indicators × 16 years = 560
EXPECTED_BENCHMARK_COUNTRIES = 7
EXPECTED_BENCHMARK_INDICATORS = 5
EXPECTED_BENCHMARK_ROWS = (
    EXPECTED_BENCHMARK_COUNTRIES * EXPECTED_BENCHMARK_INDICATORS * EXPECTED_YEARS
)

# Plausible data ranges (based on Portuguese macroeconomic history 2010-2025)
# Sources: INE, Eurostat, ECB, Banco de Portugal
DATA_RANGES = {
    "unemployment_rate": (0, 20),  # PT peak ~17.5% in 2013
    "youth_unemployment_rate": (0, 45),  # PT peak ~42% in 2013
    "gdp_growth_yoy": (-20, 25),  # Real GDP growth: COVID dip Q2 2020, bounce Q2 2021
    "hicp": (-2, 12),  # PT range: deflation to energy spike
    "debt_to_gdp_ratio": (50, 160),  # PT range ~130% peak
    "ecb_main_refinancing_rate": (-1, 5),  # ECB negative era to 2023 hikes
    "portugal_10y_bond_yield": (-1, 18),  # Troika peak ~17%
    "npl_ratio": (0, 20),  # PT peak ~17% in 2016
}
