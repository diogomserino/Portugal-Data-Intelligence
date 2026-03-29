"""Unit tests for the AI insight engine."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATABASE_PATH


class TestInsightEngine:
    """Tests for InsightEngine class."""

    def test_engine_initialises_rule_based(self):
        """Engine should default to rule-based mode."""
        from src.ai_insights.insight_engine import InsightEngine

        engine = InsightEngine(str(DATABASE_PATH), use_ai=False)
        assert engine is not None

    def test_generate_all_pillar_insights(self):
        """Should generate insights for all 6 pillars."""
        from src.ai_insights.insight_engine import InsightEngine

        engine = InsightEngine(str(DATABASE_PATH), use_ai=False)
        for pillar in [
            "gdp",
            "unemployment",
            "credit",
            "interest_rates",
            "inflation",
            "public_debt",
        ]:
            insight = engine.generate_pillar_insight(pillar)
            assert "headline" in insight, f"{pillar} missing headline"
            assert "executive_summary" in insight, f"{pillar} missing executive_summary"
            assert "key_findings" in insight, f"{pillar} missing key_findings"
            assert "recommendations" in insight, f"{pillar} missing recommendations"
            assert len(insight["key_findings"]) >= 3, f"{pillar} has too few findings"
            assert len(insight["recommendations"]) >= 2, f"{pillar} has too few recommendations"

    def test_executive_briefing_structure(self):
        """Executive briefing should have all required sections."""
        from src.ai_insights.insight_engine import InsightEngine

        engine = InsightEngine(str(DATABASE_PATH), use_ai=False)
        briefing = engine.generate_executive_briefing()
        assert "title" in briefing
        assert "overall_assessment" in briefing
        assert "pillar_insights" in briefing
        assert "strategic_recommendations" in briefing
        assert "risk_matrix" in briefing
        assert len(briefing["pillar_insights"]) == 6

    def test_insights_contain_real_data(self):
        """Insights should reference actual data values, not templates."""
        from src.ai_insights.insight_engine import InsightEngine

        engine = InsightEngine(str(DATABASE_PATH), use_ai=False)
        gdp = engine.generate_pillar_insight("gdp")
        # Summary should contain actual numbers (not just template placeholders)
        summary = gdp["executive_summary"]
        assert any(c.isdigit() for c in summary), "Executive summary contains no numbers"

    def test_risk_matrix_has_all_pillars(self):
        """Risk matrix should assess all 6 pillars."""
        from src.ai_insights.insight_engine import InsightEngine

        engine = InsightEngine(str(DATABASE_PATH), use_ai=False)
        briefing = engine.generate_executive_briefing()
        risk_pillars = [r["pillar"] for r in briefing["risk_matrix"]]
        assert len(risk_pillars) == 6
