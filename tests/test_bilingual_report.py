"""Tests for the bilingual (English / Portuguese) report and insight engine."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATABASE_PATH
from src.reporting.i18n import COLUMN_LABELS, PILLAR_TITLES, STRINGS, SUPPORTED_LANGS


class TestI18nTables:
    """The translation tables must stay key-aligned across languages."""

    def test_strings_keys_match(self):
        assert set(STRINGS["en"]) == set(STRINGS["pt"]), "STRINGS keys diverge between en/pt"

    def test_column_labels_keys_match(self):
        assert set(COLUMN_LABELS["en"]) == set(COLUMN_LABELS["pt"])

    def test_pillar_titles_keys_match(self):
        assert set(PILLAR_TITLES["en"]) == set(PILLAR_TITLES["pt"])

    def test_supported_langs(self):
        assert "en" in SUPPORTED_LANGS and "pt" in SUPPORTED_LANGS


class TestPortugueseBriefing:
    """The insight engine should produce a complete Portuguese briefing."""

    def test_pt_briefing_structure(self):
        from src.ai_insights.insight_engine import InsightEngine

        engine = InsightEngine(str(DATABASE_PATH), use_ai=False, lang="pt")
        briefing = engine.generate_executive_briefing()

        assert briefing["lang"] == "pt"
        assert briefing["title"] == STRINGS["pt"]["default_briefing_title"]
        assert len(briefing["pillar_insights"]) == 6
        # Overall assessment should read as Portuguese, not English.
        assert "avaliação macroeconómica" in briefing["overall_assessment"].lower()

    def test_pt_pillars_carry_risk_class_token(self):
        from src.ai_insights.insight_engine import InsightEngine

        engine = InsightEngine(str(DATABASE_PATH), use_ai=False, lang="pt")
        briefing = engine.generate_executive_briefing()

        valid = {"low", "moderate", "elevated", "high"}
        for ins in briefing["pillar_insights"]:
            assert ins.get("risk_class") in valid, f"{ins['pillar']} bad risk_class"
            # Portuguese prose must not contain the English risk keywords.
            assert "RISK" not in ins.get("risk_assessment", "").upper()
        for entry in briefing["risk_matrix"]:
            assert entry.get("risk_class") in valid

    def test_en_and_pt_pick_same_risk_class(self):
        """Same data → same risk colour regardless of language."""
        from src.ai_insights.insight_engine import InsightEngine

        en = {
            i["pillar"]: i["risk_class"]
            for i in InsightEngine(str(DATABASE_PATH), lang="en").generate_executive_briefing()[
                "pillar_insights"
            ]
        }
        pt = {
            i["pillar"]: i["risk_class"]
            for i in InsightEngine(str(DATABASE_PATH), lang="pt").generate_executive_briefing()[
                "pillar_insights"
            ]
        }
        assert en == pt


class TestReportLocalisation:
    """Render helpers should emit the requested language and not leak the other."""

    def test_methodology_localised(self):
        from dashboard.generate_report import render_methodology

        en = render_methodology("en")
        pt = render_methodology("pt")
        assert "Methodology &amp; Data Sources" in en
        assert "Metodologia &amp; Fontes de Dados" in pt
        assert "Metodologia" not in en
        assert "Methodology" not in pt

    def test_kpi_dashboard_localised(self):
        from dashboard.generate_report import render_kpi_dashboard

        pt = render_kpi_dashboard({}, "pt")
        assert "Indicadores-Chave" in pt
        assert "Key Indicators" not in pt

    def test_lang_switch_has_both_languages(self):
        from dashboard.generate_report import render_lang_switch

        en = render_lang_switch("en")
        assert 'href="index.html"' in en
        assert 'href="index.pt.html"' in en
        assert 'id="lang-other"' in en  # the non-current link is tagged for redirect
        assert 'class="active"' in en

    def test_pillar_section_uses_risk_class_token(self):
        """A PT insight with an explicit risk_class drives the callout colour."""
        from dashboard.generate_report import render_pillar_section

        insight = {
            "pillar": "gdp",
            "headline": "Teste",
            "executive_summary": "Resumo.",
            "key_findings": ["Conclusão um."],
            "risk_assessment": "RISCO ELEVADO. Texto em português.",
            "risk_class": "elevated",
            "outlook": "Perspetivas.",
        }
        html = render_pillar_section(insight, "gdp_evolution.png", "gdp", "PIB", {}, "pt")
        assert 'class="risk-callout elevated"' in html
        assert "Avaliação de Risco:" in html
        assert "Principais Conclusões" in html
