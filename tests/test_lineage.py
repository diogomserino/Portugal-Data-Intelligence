"""Tests for the pipeline lineage and batch tracking module."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.etl.lineage import PipelineTracker, file_checksum, get_run_id


class TestFileChecksum:
    """Tests for the file_checksum utility."""

    def test_checksum_of_known_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        cs = file_checksum(f)
        assert cs is not None
        assert len(cs) == 64  # SHA-256 hex digest

    def test_checksum_nonexistent_file(self, tmp_path):
        assert file_checksum(tmp_path / "nope.txt") is None

    def test_same_content_same_checksum(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("identical", encoding="utf-8")
        f2.write_text("identical", encoding="utf-8")
        assert file_checksum(f1) == file_checksum(f2)

    def test_different_content_different_checksum(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("alpha", encoding="utf-8")
        f2.write_text("beta", encoding="utf-8")
        assert file_checksum(f1) != file_checksum(f2)


class TestPipelineTracker:
    """Tests for the PipelineTracker context manager."""

    def test_run_id_set_during_context(self, tmp_path):
        db = tmp_path / "test.db"
        with PipelineTracker(mode="test", db_path=db) as tracker:
            assert get_run_id() == tracker.run_id
        # After exiting, run_id should be reset
        assert get_run_id() is None

    def test_records_persisted_to_database(self, tmp_path):
        db = tmp_path / "test.db"
        with PipelineTracker(mode="test", db_path=db) as tracker:
            tracker.record("gdp", "extract", rows_in=0, rows_out=64, checksum="abc123")
            tracker.record("gdp", "transform", rows_in=64, rows_out=64)
            tracker.record("gdp", "load", rows_in=64, rows_out=64)

        conn = sqlite3.connect(str(db))
        runs = conn.execute("SELECT * FROM pipeline_runs").fetchall()
        assert len(runs) == 1
        assert runs[0][3] == "completed"  # status

        lineage = conn.execute(
            "SELECT * FROM data_lineage WHERE run_id = ?", (tracker.run_id,)
        ).fetchall()
        assert len(lineage) == 3
        conn.close()

    def test_failed_run_status(self, tmp_path):
        db = tmp_path / "test.db"
        with pytest.raises(ValueError):
            with PipelineTracker(mode="test", db_path=db) as tracker:
                tracker.record("gdp", "extract", rows_out=10)
                raise ValueError("simulated failure")

        conn = sqlite3.connect(str(db))
        status = conn.execute("SELECT status FROM pipeline_runs").fetchone()[0]
        assert status == "failed"
        conn.close()

    def test_run_id_is_unique(self, tmp_path):
        db = tmp_path / "test.db"
        ids = []
        for _ in range(3):
            with PipelineTracker(mode="test", db_path=db) as tracker:
                ids.append(tracker.run_id)
        assert len(set(ids)) == 3

    def test_empty_records(self, tmp_path):
        db = tmp_path / "test.db"
        with PipelineTracker(mode="test", db_path=db):
            pass  # no records
        conn = sqlite3.connect(str(db))
        lineage = conn.execute("SELECT COUNT(*) FROM data_lineage").fetchone()[0]
        assert lineage == 0
        conn.close()
