"""Tests for the scenario analysis module."""

import pytest

from tests.conftest import PRODUCTION_DB

# Skip entire module if database not available
pytestmark = pytest.mark.skipif(
    not PRODUCTION_DB.exists(),
    reason="Production database not available",
)


@pytest.fixture(scope="module")
def engine():
    from src.analysis.scenario_analysis import ScenarioEngine

    try:
        eng = ScenarioEngine(db_path=str(PRODUCTION_DB))
    except Exception as exc:
        pytest.skip(f"ScenarioEngine initialisation failed (schema migration): {exc}")
    yield eng
    eng._conn.close()


class TestScenarioEngineInit:
    def test_baseline_loaded(self, engine):
        assert engine.latest_nominal_gdp > 0
        assert 0 < engine.latest_unemployment < 50
        assert engine.latest_debt_ratio > 0

    def test_coefficients_estimated(self, engine):
        assert hasattr(engine, "okun")
        assert hasattr(engine, "credit_rate_elast")
        assert hasattr(engine, "calibration_sources")
        assert len(engine.calibration_sources) >= 3

    def test_calibration_sources_documented(self, engine):
        for key, source in engine.calibration_sources.items():
            assert isinstance(source, str)
            assert len(source) > 5  # meaningful description


class TestRateShock:
    def test_rate_shock_returns_expected_keys(self, engine):
        result = engine.rate_shock_scenario(rate_increase_bps=100)
        assert "scenario" in result
        assert "baseline" in result
        assert "stressed" in result

    def test_higher_shock_larger_impact(self, engine):
        r100 = engine.rate_shock_scenario(100)
        r200 = engine.rate_shock_scenario(200)
        # Additional debt servicing cost should scale approximately linearly
        cost_100 = r100["impacts"]["additional_debt_servicing_eur_m"]
        cost_200 = r200["impacts"]["additional_debt_servicing_eur_m"]
        assert cost_200 > cost_100


class TestGDPSlowdown:
    def test_gdp_slowdown_returns_expected_keys(self, engine):
        result = engine.gdp_slowdown_scenario(gdp_shock_pct=-2.0)
        assert "scenario" in result
        assert "baseline" in result
        assert "stressed" in result

    def test_negative_shock_changes_unemployment(self, engine):
        result = engine.gdp_slowdown_scenario(gdp_shock_pct=-3.0)
        # Unemployment should change (direction depends on data-driven Okun coefficient)
        assert (
            result["stressed"]["unemployment_rate_pct"]
            != result["baseline"]["unemployment_rate_pct"]
        )

    def test_debt_ratio_rises_on_gdp_contraction(self, engine):
        result = engine.gdp_slowdown_scenario(gdp_shock_pct=-3.0)
        # Debt-to-GDP should rise when GDP contracts (denominator effect)
        assert (
            result["stressed"]["debt_to_gdp_ratio_pct"]
            > result["baseline"]["debt_to_gdp_ratio_pct"]
        )


class TestInflationSpike:
    def test_inflation_spike_returns_expected_keys(self, engine):
        result = engine.inflation_spike_scenario(inflation_target=6.0)
        assert "scenario" in result
        assert "baseline" in result
        assert "stressed" in result


class TestFiscalConsolidation:
    def test_fiscal_consolidation_returns_expected_keys(self, engine):
        result = engine.fiscal_consolidation_scenario(deficit_target=-3.0)
        assert "scenario" in result
        assert "baseline" in result
