"""Unit tests for transform module — pure functions, no database required."""

import numpy as np
import pandas as pd
import pytest

from src.etl.transform import (
    _PILLAR_CONFIGS,
    _clip_and_warn,
    _derive_date_key_monthly,
    _derive_date_key_quarterly,
    _transform_pillar,
)

# ============================================================================
# _clip_and_warn
# ============================================================================


class TestClipAndWarn:
    """Tests for the _clip_and_warn helper."""

    def test_clips_below_lower_bound(self):
        df = pd.DataFrame({"x": [-10.0, 5.0, 20.0]})
        result = _clip_and_warn(df, "x", lower=0, upper=None, pillar="test")
        assert result["x"].min() == 0.0

    def test_clips_above_upper_bound(self):
        df = pd.DataFrame({"x": [5.0, 50.0, 200.0]})
        result = _clip_and_warn(df, "x", lower=None, upper=100, pillar="test")
        assert result["x"].max() == 100.0

    def test_clips_both_bounds(self):
        df = pd.DataFrame({"x": [-5.0, 50.0, 150.0]})
        result = _clip_and_warn(df, "x", lower=0, upper=100, pillar="test")
        assert result["x"].min() >= 0
        assert result["x"].max() <= 100

    def test_no_clip_when_in_range(self):
        df = pd.DataFrame({"x": [10.0, 50.0, 90.0]})
        result = _clip_and_warn(df, "x", lower=0, upper=100, pillar="test")
        pd.testing.assert_frame_equal(result, df)

    def test_missing_column_returns_unchanged(self):
        df = pd.DataFrame({"y": [1.0, 2.0]})
        result = _clip_and_warn(df, "nonexistent", lower=0, upper=10, pillar="test")
        pd.testing.assert_frame_equal(result, df)

    def test_handles_nan_values(self):
        df = pd.DataFrame({"x": [np.nan, 5.0, np.nan, 50.0]})
        result = _clip_and_warn(df, "x", lower=0, upper=100, pillar="test")
        assert result["x"].isna().sum() == 2
        assert result["x"].dropna().min() >= 0

    def test_handles_empty_dataframe(self):
        df = pd.DataFrame({"x": pd.Series([], dtype=float)})
        result = _clip_and_warn(df, "x", lower=0, upper=100, pillar="test")
        assert len(result) == 0

    def test_handles_all_nan(self):
        df = pd.DataFrame({"x": [np.nan, np.nan, np.nan]})
        result = _clip_and_warn(df, "x", lower=0, upper=10, pillar="test")
        assert result["x"].isna().all()

    def test_lower_equals_upper(self):
        df = pd.DataFrame({"x": [1.0, 5.0, 10.0]})
        result = _clip_and_warn(df, "x", lower=5, upper=5, pillar="test")
        assert (result["x"] == 5.0).all()

    def test_preserves_other_columns(self):
        df = pd.DataFrame({"x": [-5.0, 50.0], "y": ["a", "b"]})
        result = _clip_and_warn(df, "x", lower=0, upper=100, pillar="test")
        assert list(result["y"]) == ["a", "b"]


# ============================================================================
# _derive_date_key_monthly
# ============================================================================


class TestDeriveDateKeyMonthly:
    """Tests for monthly date_key derivation."""

    def test_creates_yyyy_mm_format(self):
        df = pd.DataFrame({"date": ["2023-01-15", "2023-12-31"]})
        result = _derive_date_key_monthly(df)
        assert result["date_key"].iloc[0] == "2023-01"
        assert result["date_key"].iloc[1] == "2023-12"

    def test_handles_iso_date_format(self):
        df = pd.DataFrame({"date": ["2023-06-15", "2024-01-01"]})
        result = _derive_date_key_monthly(df)
        assert result["date_key"].iloc[0] == "2023-06"
        assert result["date_key"].iloc[1] == "2024-01"

    def test_no_date_column_returns_unchanged(self):
        df = pd.DataFrame({"year": [2023], "month": [6]})
        result = _derive_date_key_monthly(df)
        assert "date_key" not in result.columns

    def test_preserves_original_date_column(self):
        df = pd.DataFrame({"date": ["2023-01-15"]})
        result = _derive_date_key_monthly(df)
        assert "date" in result.columns


# ============================================================================
# _derive_date_key_quarterly
# ============================================================================


class TestDeriveDateKeyQuarterly:
    """Tests for quarterly date_key derivation."""

    def test_creates_yyyy_qn_from_year_quarter(self):
        df = pd.DataFrame({"year": [2023, 2024], "quarter": [1, 4]})
        result = _derive_date_key_quarterly(df)
        assert result["date_key"].iloc[0] == "2023-Q1"
        assert result["date_key"].iloc[1] == "2024-Q4"

    def test_creates_from_date_column_fallback(self):
        df = pd.DataFrame({"date": ["2023-03-31", "2023-09-30"]})
        result = _derive_date_key_quarterly(df)
        assert result["date_key"].iloc[0] == "2023-Q1"
        assert result["date_key"].iloc[1] == "2023-Q3"

    def test_no_date_or_quarter_columns(self):
        df = pd.DataFrame({"value": [100]})
        result = _derive_date_key_quarterly(df)
        assert "date_key" not in result.columns


# ============================================================================
# _transform_pillar (generic transformer)
# ============================================================================


class TestTransformPillar:
    """Tests for the generic pillar transformer."""

    @pytest.fixture
    def minimal_gdp_raw(self):
        """Minimal raw GDP DataFrame for testing."""
        return pd.DataFrame(
            {
                "year": [2023, 2023, 2024, 2024],
                "quarter": [1, 2, 3, 4],
                "nominal_gdp_eur_millions": [50000.0, 52000.0, 53000.0, 55000.0],
                "real_gdp_eur_millions": [45000.0, 46000.0, 46500.0, 47000.0],
                "nominal_gdp_growth_rate_yoy": [2.5, 3.0, 2.8, 3.2],
                "nominal_gdp_growth_rate_qoq": [0.5, 0.8, 0.6, 0.9],
                "gdp_per_capita_eur": [19000.0, 19500.0, 20000.0, 20500.0],
            }
        )

    def test_renames_columns(self, minimal_gdp_raw):
        result = _transform_pillar("gdp", minimal_gdp_raw, _PILLAR_CONFIGS["gdp"])
        assert "nominal_gdp" in result.columns
        assert "nominal_gdp_eur_millions" not in result.columns

    def test_creates_date_key(self, minimal_gdp_raw):
        result = _transform_pillar("gdp", minimal_gdp_raw, _PILLAR_CONFIGS["gdp"])
        assert "date_key" in result.columns
        assert result["date_key"].iloc[0] == "2023-Q1"

    def test_keeps_only_specified_columns(self, minimal_gdp_raw):
        config = _PILLAR_CONFIGS["gdp"]
        result = _transform_pillar("gdp", minimal_gdp_raw, config)
        expected_cols = set(config["keep_cols"]) | {"is_provisional"}
        assert set(result.columns) == expected_cols

    def test_clips_negative_gdp(self):
        df = pd.DataFrame(
            {
                "year": [2023],
                "quarter": [1],
                "nominal_gdp_eur_millions": [-5000.0],
                "real_gdp_eur_millions": [45000.0],
                "nominal_gdp_growth_rate_yoy": [2.0],
                "nominal_gdp_growth_rate_qoq": [0.5],
                "gdp_per_capita_eur": [-100.0],
            }
        )
        result = _transform_pillar("gdp", df, _PILLAR_CONFIGS["gdp"])
        assert result["nominal_gdp"].iloc[0] >= 0
        assert result["gdp_per_capita"].iloc[0] >= 0

    def test_does_not_modify_input(self, minimal_gdp_raw):
        original = minimal_gdp_raw.copy()
        _transform_pillar("gdp", minimal_gdp_raw, _PILLAR_CONFIGS["gdp"])
        pd.testing.assert_frame_equal(minimal_gdp_raw, original)

    def test_raises_on_missing_date_key(self):
        df = pd.DataFrame({"value": [100.0]})
        config = {
            "rename": {},
            "date_key": "monthly",
            "clip_rules": [],
            "round_dp": 2,
            "keep_cols": ["date_key", "value"],
        }
        with pytest.raises(ValueError, match="Could not derive date_key"):
            _transform_pillar("test", df, config)

    def test_all_pillar_configs_are_valid(self):
        """Every pillar config should have required keys."""
        required_keys = {"rename", "date_key", "clip_rules", "round_dp", "keep_cols"}
        for pillar, config in _PILLAR_CONFIGS.items():
            missing = required_keys - set(config.keys())
            assert not missing, f"{pillar} config missing keys: {missing}"
            assert config["date_key"] in (
                "monthly",
                "quarterly",
            ), f"{pillar} has invalid date_key type: {config['date_key']}"
