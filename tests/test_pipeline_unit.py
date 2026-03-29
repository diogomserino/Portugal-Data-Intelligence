"""Unit tests for helper functions in src/etl/pipeline.py."""

import pandas as pd
import pytest

from src.etl.lineage import PipelineTracker
from src.etl.pipeline import (
    _print_summary,
    _record_extract_lineage,
    _record_load_lineage,
    _record_transform_lineage,
)


@pytest.fixture()
def tracker(tmp_path):
    """PipelineTracker backed by a temporary database."""
    db_path = tmp_path / "lineage_test.db"
    t = PipelineTracker(mode="test", db_path=db_path)
    # Enter context so run_id is set
    t.__enter__()
    yield t
    t.__exit__(None, None, None)


@pytest.fixture()
def sample_dfs():
    """Small DataFrames simulating raw/processed data."""
    return {
        "gdp": pd.DataFrame({"date_key": ["2020-Q1"], "value": [100.0]}),
        "unemployment": pd.DataFrame({"date_key": ["2020-01"], "rate": [6.5]}),
    }


# ── _print_summary ────────────────────────────────────────────────────


class TestPrintSummary:
    def test_smoke(self):
        """Should run without raising."""
        _print_summary(
            raw_counts={"gdp": 64, "unemployment": 192},
            processed_counts={"gdp": 64, "unemployment": 192},
            loaded_counts={"gdp": 64, "unemployment": 192},
            elapsed=1.23,
        )

    def test_empty_counts(self):
        _print_summary({}, {}, {}, 0.0)


# ── _record_extract_lineage ──────────────────────────────────────────


class TestRecordExtractLineage:
    def test_records_added(self, tracker, sample_dfs):
        before = len(tracker.records)
        _record_extract_lineage(tracker, sample_dfs)
        assert len(tracker.records) == before + len(sample_dfs)

    def test_stage_is_extract(self, tracker, sample_dfs):
        _record_extract_lineage(tracker, sample_dfs)
        for rec in tracker.records:
            assert rec.stage == "extract"


# ── _record_transform_lineage ───────────────────────────────────────


class TestRecordTransformLineage:
    def test_records_added(self, tracker, sample_dfs):
        before = len(tracker.records)
        _record_transform_lineage(tracker, sample_dfs, sample_dfs)
        after = len(tracker.records)
        assert after - before == len(sample_dfs)

    def test_stage_is_transform(self, tracker, sample_dfs):
        _record_transform_lineage(tracker, sample_dfs, sample_dfs)
        transform_recs = [r for r in tracker.records if r.stage == "transform"]
        assert len(transform_recs) >= len(sample_dfs)


# ── _record_load_lineage ────────────────────────────────────────────


class TestRecordLoadLineage:
    def test_records_added(self, tracker, sample_dfs):
        load_counts = {k: len(v) for k, v in sample_dfs.items()}
        before = len(tracker.records)
        _record_load_lineage(tracker, sample_dfs, load_counts)
        assert len(tracker.records) == before + len(load_counts)

    def test_stage_is_load(self, tracker, sample_dfs):
        load_counts = {k: len(v) for k, v in sample_dfs.items()}
        _record_load_lineage(tracker, sample_dfs, load_counts)
        load_recs = [r for r in tracker.records if r.stage == "load"]
        assert len(load_recs) >= len(load_counts)

    def test_rows_out_matches_count(self, tracker, sample_dfs):
        load_counts = {"gdp": 64, "unemployment": 192}
        _record_load_lineage(tracker, sample_dfs, load_counts)
        load_recs = [r for r in tracker.records if r.stage == "load"]
        for rec in load_recs:
            assert rec.rows_out == load_counts[rec.pillar]
