"""Tests for the data quality framework."""

import numpy as np
import pandas as pd
import pytest

from config.settings import END_YEAR, START_YEAR
from src.etl.data_quality import CheckResult, DataQualityChecker, DQReport

_N_YEARS = END_YEAR - START_YEAR + 1
_Q_ROWS = _N_YEARS * 4
_M_ROWS = _N_YEARS * 12


def _make_pillar_df(pillar: str) -> pd.DataFrame:
    """Create a minimal valid DataFrame for a given pillar."""
    if pillar == "gdp":
        keys = [f"{y}-Q{q}" for y in range(START_YEAR, END_YEAR + 1) for q in range(1, 5)]
        return pd.DataFrame(
            {
                "date_key": keys[:_Q_ROWS],
                "nominal_gdp": np.linspace(40000, 60000, _Q_ROWS),
                "real_gdp": np.linspace(38000, 55000, _Q_ROWS),
                "gdp_growth_yoy": np.random.uniform(-2, 5, _Q_ROWS),
                "gdp_growth_qoq": np.random.uniform(-2, 3, _Q_ROWS),
                "gdp_per_capita": np.linspace(15000, 25000, _Q_ROWS),
                "is_provisional": False,
                "source_key": 1,
            }
        )
    elif pillar == "unemployment":
        return pd.DataFrame(
            {
                "date_key": [
                    f"{y}-{m:02d}" for y in range(START_YEAR, END_YEAR + 1) for m in range(1, 13)
                ],
                "unemployment_rate": np.random.uniform(5, 15, _M_ROWS),
                "youth_unemployment_rate": np.random.uniform(15, 40, _M_ROWS),
                "long_term_unemployment_rate": np.random.uniform(2, 10, _M_ROWS),
                "labour_force_participation_rate": np.random.uniform(55, 75, _M_ROWS),
                "is_provisional": False,
                "source_key": 1,
            }
        )
    elif pillar == "credit":
        return pd.DataFrame(
            {
                "date_key": [
                    f"{y}-{m:02d}" for y in range(START_YEAR, END_YEAR + 1) for m in range(1, 13)
                ],
                "total_credit": np.random.uniform(200000, 300000, _M_ROWS),
                "credit_nfc": np.random.uniform(80000, 120000, _M_ROWS),
                "credit_households": np.random.uniform(80000, 120000, _M_ROWS),
                "npl_ratio": np.random.uniform(1, 10, _M_ROWS),
                "is_provisional": False,
                "source_key": 1,
            }
        )
    elif pillar == "interest_rates":
        return pd.DataFrame(
            {
                "date_key": [
                    f"{y}-{m:02d}" for y in range(START_YEAR, END_YEAR + 1) for m in range(1, 13)
                ],
                "ecb_main_refinancing_rate": np.random.uniform(0, 4, _M_ROWS),
                "euribor_3m": np.random.uniform(-0.5, 3, _M_ROWS),
                "euribor_6m": np.random.uniform(-0.3, 3.5, _M_ROWS),
                "euribor_12m": np.random.uniform(0, 4, _M_ROWS),
                "portugal_10y_bond_yield": np.random.uniform(0, 6, _M_ROWS),
                "is_provisional": False,
                "source_key": 1,
            }
        )
    elif pillar == "inflation":
        return pd.DataFrame(
            {
                "date_key": [
                    f"{y}-{m:02d}" for y in range(START_YEAR, END_YEAR + 1) for m in range(1, 13)
                ],
                "hicp": np.random.uniform(-1, 8, _M_ROWS),
                "cpi_estimated": np.random.uniform(-0.5, 7, _M_ROWS),
                "core_inflation": np.random.uniform(0, 5, _M_ROWS),
                "is_provisional": False,
                "source_key": 1,
            }
        )
    elif pillar == "public_debt":
        keys = [f"{y}-Q{q}" for y in range(START_YEAR, END_YEAR + 1) for q in range(1, 5)]
        return pd.DataFrame(
            {
                "date_key": keys[:_Q_ROWS],
                "total_debt": np.linspace(150000, 280000, _Q_ROWS),
                "debt_to_gdp_ratio": np.linspace(80, 130, _Q_ROWS),
                "budget_deficit": np.random.uniform(-8, 2, _Q_ROWS),
                "budget_deficit_annual": np.random.uniform(-8, 2, _Q_ROWS),
                "external_debt_share_estimated": np.random.uniform(40, 70, _Q_ROWS),
                "is_provisional": False,
                "source_key": 1,
            }
        )
    raise ValueError(f"Unknown pillar: {pillar}")


@pytest.fixture
def valid_data():
    """Create a full set of valid processed DataFrames."""
    pillars = ["gdp", "unemployment", "credit", "interest_rates", "inflation", "public_debt"]
    return {p: _make_pillar_df(p) for p in pillars}


class TestDQReport:
    def test_summary_counts(self):
        report = DQReport()
        report.checks.append(CheckResult("a", "pass", "ok"))
        report.checks.append(CheckResult("b", "warn", "warning"))
        report.checks.append(CheckResult("c", "fail", "bad"))
        assert report.passed == 1
        assert report.warnings == 1
        assert report.failures == 1
        assert report.has_critical_failure

    def test_to_dict(self):
        report = DQReport(run_id="test123")
        report.checks.append(CheckResult("x", "pass", "ok"))
        d = report.to_dict()
        assert d["run_id"] == "test123"
        assert d["summary"]["total"] == 1

    def test_save_creates_file(self, tmp_path):
        report = DQReport(run_id="save_test")
        report.checks.append(CheckResult("x", "pass", "ok"))
        path = report.save(directory=tmp_path)
        assert path.exists()
        assert "save_test" in path.name


class TestSchemaCheck:
    def test_all_valid_schemas_pass(self, valid_data):
        checker = DataQualityChecker(valid_data)
        checker.check_schema()
        fails = [c for c in checker.report.checks if c.status == "fail"]
        assert len(fails) == 0

    def test_missing_column_detected(self, valid_data):
        valid_data["gdp"] = valid_data["gdp"].drop(columns=["nominal_gdp"])
        checker = DataQualityChecker(valid_data)
        checker.check_schema()
        fails = [c for c in checker.report.checks if c.status == "fail" and c.pillar == "gdp"]
        assert len(fails) == 1


class TestNotNullCheck:
    def test_valid_data_passes(self, valid_data):
        checker = DataQualityChecker(valid_data)
        checker.check_not_null()
        fails = [c for c in checker.report.checks if c.status == "fail"]
        assert len(fails) == 0

    def test_all_null_column_fails(self, valid_data):
        valid_data["gdp"]["nominal_gdp"] = None
        checker = DataQualityChecker(valid_data)
        checker.check_not_null()
        fails = [c for c in checker.report.checks if c.status == "fail"]
        assert len(fails) == 1


class TestRangeCheck:
    def test_valid_ranges_pass(self, valid_data):
        checker = DataQualityChecker(valid_data)
        checker.check_ranges()
        fails = [c for c in checker.report.checks if c.status == "fail"]
        assert len(fails) == 0

    def test_out_of_range_detected(self, valid_data):
        valid_data["unemployment"].loc[
            valid_data["unemployment"].index[0], "unemployment_rate"
        ] = 99.0
        checker = DataQualityChecker(valid_data)
        checker.check_ranges()
        warns = [
            c for c in checker.report.checks if c.status == "warn" and "unemployment_rate" in c.name
        ]
        assert len(warns) >= 1


class TestCompletenessCheck:
    def test_full_data_passes(self, valid_data):
        checker = DataQualityChecker(valid_data)
        checker.check_completeness()
        warns = [c for c in checker.report.checks if c.status == "warn"]
        assert len(warns) == 0

    def test_missing_rows_warned(self, valid_data):
        valid_data["gdp"] = valid_data["gdp"].iloc[:50]  # should be 64
        checker = DataQualityChecker(valid_data)
        checker.check_completeness()
        warns = [c for c in checker.report.checks if c.status == "warn" and c.pillar == "gdp"]
        assert len(warns) == 1


class TestConsistencyCheck:
    def test_valid_consistency_passes(self, valid_data):
        # Ensure credit components are less than total
        valid_data["credit"]["credit_nfc"] = valid_data["credit"]["total_credit"] * 0.4
        valid_data["credit"]["credit_households"] = valid_data["credit"]["total_credit"] * 0.4
        checker = DataQualityChecker(valid_data)
        checker.check_consistency()
        fails = [c for c in checker.report.checks if c.status == "fail"]
        assert len(fails) == 0


class TestFreshnessCheck:
    def test_fresh_data_passes(self, valid_data):
        checker = DataQualityChecker(valid_data)
        checker.check_freshness()
        passes = [c for c in checker.report.checks if c.status == "pass"]
        assert len(passes) >= 1


class TestInterColumnConsistency:
    """Tests for cross-column data consistency."""

    def test_gdp_growth_matches_real_gdp(self):
        """YoY/QoQ growth rates should be derivable from real_gdp."""
        from src.etl.transform import _gdp_post_hook

        keys = [f"{y}-Q{q}" for y in range(2010, 2015) for q in range(1, 5)]
        real_gdp = np.linspace(40000, 50000, len(keys))
        df = pd.DataFrame(
            {
                "date_key": keys,
                "real_gdp": real_gdp,
                "gdp_growth_yoy": 0.0,
                "gdp_growth_qoq": 0.0,
            }
        )
        result = _gdp_post_hook(df)
        # QoQ: should match pct_change
        expected_qoq = pd.Series(real_gdp).pct_change() * 100
        pd.testing.assert_series_equal(
            result["gdp_growth_qoq"].reset_index(drop=True),
            expected_qoq,
            check_names=False,
            atol=0.01,
        )
        # YoY: first 4 should be NaN
        assert result["gdp_growth_yoy"].iloc[:4].isna().all()
        # YoY for Q1 2011: should be (real_gdp[4] / real_gdp[0] - 1) * 100
        expected_yoy_4 = (real_gdp[4] / real_gdp[0] - 1) * 100
        assert abs(result["gdp_growth_yoy"].iloc[4] - expected_yoy_4) < 0.01

    def test_cpi_estimated_differs_from_hicp(self, valid_data):
        """cpi_estimated should not be identical to hicp."""
        infl = valid_data["inflation"]
        assert "cpi_estimated" in infl.columns
        diff = (infl["hicp"] - infl["cpi_estimated"]).abs()
        assert diff.max() > 0.01, "cpi_estimated should differ from hicp"

    def test_provisional_flag_column_exists(self, valid_data):
        """All pillars should have is_provisional column."""
        for pillar, df in valid_data.items():
            assert "is_provisional" in df.columns, f"is_provisional missing from {pillar}"

    def test_no_duplicate_quarters_in_debt(self, valid_data):
        """Public debt should not have duplicate date_key values."""
        debt = valid_data["public_debt"]
        assert debt["date_key"].is_unique, "Duplicate date_key in public_debt"


class TestRunAll:
    def test_run_all_produces_checks(self, valid_data):
        checker = DataQualityChecker(valid_data, run_id="test_run")
        report = checker.run_all()
        assert len(report.checks) >= 15
        assert report.run_id == "test_run"
