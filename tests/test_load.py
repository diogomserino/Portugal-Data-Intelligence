"""Tests for the ETL load module."""

import sqlite3

import numpy as np
import pandas as pd
import pytest

from src.etl.load import _SAFE_PRAGMAS, _to_float, close_connection


class TestSafePragmas:
    def test_common_pragmas_in_whitelist(self):
        assert "journal_mode" in _SAFE_PRAGMAS
        assert "foreign_keys" in _SAFE_PRAGMAS
        assert "cache_size" in _SAFE_PRAGMAS
        assert "synchronous" in _SAFE_PRAGMAS

    def test_dangerous_pragmas_not_in_whitelist(self):
        assert "key" not in _SAFE_PRAGMAS
        assert "cipher" not in _SAFE_PRAGMAS


class TestToFloat:
    def test_normal_float(self):
        assert _to_float(3.14) == 3.14

    def test_integer(self):
        assert _to_float(42) == 42.0

    def test_string_number(self):
        assert _to_float("3.14") == 3.14

    def test_none_returns_none(self):
        assert _to_float(None) is None

    def test_nan_returns_none(self):
        assert _to_float(float("nan")) is None

    def test_numpy_nan_returns_none(self):
        assert _to_float(np.nan) is None

    def test_invalid_string_returns_none(self):
        assert _to_float("not_a_number") is None

    def test_numpy_float(self):
        val = np.float64(2.5)
        assert _to_float(val) == 2.5


class TestCloseConnection:
    def test_close_valid_connection(self, tmp_path):
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        close_connection(conn)
        # Should not raise

    def test_close_already_closed(self, tmp_path):
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.close()
        # Should handle gracefully (logs error but doesn't raise)
        close_connection(conn)
