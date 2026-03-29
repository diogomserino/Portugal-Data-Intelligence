"""Tests for benchmarking plot functions."""

from pathlib import Path

import pytest

from tests.conftest import PRODUCTION_DB

pytestmark = pytest.mark.skipif(
    not PRODUCTION_DB.exists(),
    reason="Production database not available",
)


class TestBenchmarkPlots:
    def test_plot_benchmark_comparison_generates_files(self, tmp_path):
        from src.analysis.benchmarking import plot_benchmark_comparison

        paths = plot_benchmark_comparison(
            db_path=str(PRODUCTION_DB),
            output_dir=str(tmp_path),
        )
        assert isinstance(paths, list)
        assert len(paths) >= 1
        for p in paths:
            assert p.exists()
            assert p.stat().st_size > 1000
