"""Integration tests for the ETL load module (src/etl/load.py).

Uses tmp_path fixtures with file-backed SQLite databases so that
DDL executescript() calls work correctly.  No network access required.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from config.settings import DDL_DIR
from src.etl.load import (
    _PILLAR_CONFIGS,
    _get_source_key,
    _insert_or_replace,
    _load_pillar,
    _resolve_source_key,
    _source_key_cache,
    _to_float,
    close_connection,
    initialise_database,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conn(tmp_path: Path) -> sqlite3.Connection:
    """Create a file-backed connection and initialise schema + seeds."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    initialise_database(conn)
    return conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitialiseDatabase:
    """initialise_database must create dimension and fact tables."""

    def test_creates_expected_tables(self, tmp_path):
        conn = _make_conn(tmp_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = sorted(row[0] for row in cursor.fetchall())
        # sqlite_sequence is an internal table created by AUTOINCREMENT
        tables = [t for t in tables if not t.startswith("sqlite_")]
        expected = [
            "dim_date",
            "dim_source",
            "fact_credit",
            "fact_eu_benchmark",
            "fact_gdp",
            "fact_inflation",
            "fact_interest_rates",
            "fact_public_debt",
            "fact_unemployment",
        ]
        assert tables == expected
        close_connection(conn)

    def test_dim_source_seeded(self, tmp_path):
        conn = _make_conn(tmp_path)
        cursor = conn.execute("SELECT COUNT(*) FROM dim_source")
        assert cursor.fetchone()[0] == 5
        close_connection(conn)

    def test_dim_date_seeded(self, tmp_path):
        conn = _make_conn(tmp_path)
        cursor = conn.execute("SELECT COUNT(*) FROM dim_date")
        count = cursor.fetchone()[0]
        # 192 monthly + 64 quarterly = 256
        assert count == 256
        close_connection(conn)


class TestGetSourceKey:
    """_get_source_key returns the correct integer key from dim_source."""

    def test_known_source(self, tmp_path):
        _source_key_cache.clear()
        conn = _make_conn(tmp_path)
        key = _get_source_key(conn, "INE")
        assert isinstance(key, int)
        assert key >= 1
        close_connection(conn)

    def test_unknown_source_returns_none(self, tmp_path):
        _source_key_cache.clear()
        conn = _make_conn(tmp_path)
        assert _get_source_key(conn, "DOES_NOT_EXIST") is None
        close_connection(conn)

    def test_cache_populated(self, tmp_path):
        _source_key_cache.clear()
        conn = _make_conn(tmp_path)
        _get_source_key(conn, "Eurostat")
        assert "Eurostat" in _source_key_cache
        close_connection(conn)


class TestResolveSourceKey:
    """_resolve_source_key looks up the first primary_source for a pillar."""

    def test_gdp_resolves(self, tmp_path):
        _source_key_cache.clear()
        conn = _make_conn(tmp_path)
        key = _resolve_source_key(conn, "gdp")
        assert isinstance(key, int)
        close_connection(conn)

    def test_credit_resolves(self, tmp_path):
        _source_key_cache.clear()
        conn = _make_conn(tmp_path)
        key = _resolve_source_key(conn, "credit")
        assert isinstance(key, int)
        close_connection(conn)


class TestToFloat:
    """_to_float converts values safely."""

    def test_normal_float(self):
        assert _to_float(3.14) == 3.14

    def test_nan_returns_none(self):
        assert _to_float(float("nan")) is None

    def test_none_returns_none(self):
        assert _to_float(None) is None

    def test_string_number(self):
        assert _to_float("42") == 42.0

    def test_bad_string_returns_none(self):
        assert _to_float("abc") is None


class TestInsertOrReplace:
    """_insert_or_replace inserts rows into a fact table."""

    def test_basic_insert(self, tmp_path):
        _source_key_cache.clear()
        conn = _make_conn(tmp_path)
        source_key = _get_source_key(conn, "INE")
        rows = [("2020-Q1", 50000.0, 48000.0, 1.5, 0.3, 16000.0, source_key)]
        columns = [
            "date_key",
            "nominal_gdp",
            "real_gdp",
            "gdp_growth_yoy",
            "gdp_growth_qoq",
            "gdp_per_capita",
            "source_key",
        ]
        count = _insert_or_replace(conn, "fact_gdp", columns, rows, "gdp")
        assert count == 1

        cursor = conn.execute("SELECT nominal_gdp FROM fact_gdp WHERE date_key='2020-Q1'")
        assert cursor.fetchone()[0] == 50000.0
        close_connection(conn)

    def test_empty_rows_returns_zero(self, tmp_path):
        conn = _make_conn(tmp_path)
        count = _insert_or_replace(conn, "fact_gdp", ["date_key"], [], "gdp")
        assert count == 0
        close_connection(conn)


class TestLoadPillar:
    """_load_pillar loads a DataFrame into the correct fact table."""

    def test_load_gdp_dataframe(self, tmp_path):
        _source_key_cache.clear()
        conn = _make_conn(tmp_path)
        df = pd.DataFrame(
            {
                "date_key": ["2020-Q1", "2020-Q2"],
                "nominal_gdp": [50000.0, 52000.0],
                "real_gdp": [48000.0, 49000.0],
                "gdp_growth_yoy": [1.5, 2.0],
                "gdp_growth_qoq": [0.3, 0.5],
                "gdp_per_capita": [16000.0, 16500.0],
            }
        )
        cfg = _PILLAR_CONFIGS["gdp"]
        loaded = _load_pillar(
            conn,
            df,
            pillar_key="gdp",
            table_name=cfg["table_name"],
            value_columns=cfg["value_columns"],
        )
        assert loaded == 2

        cursor = conn.execute("SELECT COUNT(*) FROM fact_gdp")
        assert cursor.fetchone()[0] == 2
        close_connection(conn)

    def test_load_missing_column_raises_error(self, tmp_path):
        _source_key_cache.clear()
        conn = _make_conn(tmp_path)
        df = pd.DataFrame({"date_key": ["2020-Q1"], "wrong_col": [1.0]})
        cfg = _PILLAR_CONFIGS["gdp"]
        with pytest.raises(ValueError, match="Missing required columns"):
            _load_pillar(
                conn,
                df,
                pillar_key="gdp",
                table_name=cfg["table_name"],
                value_columns=cfg["value_columns"],
            )
        close_connection(conn)


class TestLoadAll:
    """load_all orchestrates loading of multiple pillars."""

    def test_load_all_small_dataset(self, tmp_path, monkeypatch):
        """Patch DATABASE_PATH so load_all creates its db in tmp_path."""
        import config.settings as settings
        import src.etl.load as load_mod

        db_path = tmp_path / "loadall.db"
        monkeypatch.setattr(settings, "DATABASE_PATH", db_path)
        monkeypatch.setattr(settings, "DATABASE_DIR", tmp_path)
        monkeypatch.setattr(load_mod, "DATABASE_PATH", db_path)
        monkeypatch.setattr(load_mod, "DATABASE_DIR", tmp_path)
        _source_key_cache.clear()

        processed = {
            "inflation": pd.DataFrame(
                {
                    "date_key": ["2020-01", "2020-02"],
                    "hicp": [1.5, 1.6],
                    "cpi_estimated": [1.4, 1.5],
                    "core_inflation": [1.0, 1.1],
                }
            ),
        }
        from src.etl.load import load_all

        counts = load_all(processed, initialise=True)
        assert "inflation" in counts
        assert counts["inflation"] == 2
