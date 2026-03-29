"""
Portugal Data Intelligence - AI Insight Engine
================================================
Generates executive-level narrative commentary for each macroeconomic
data pillar and cross-pillar relationships.

Operates in two modes:
  1. Rule-based (default) - produces professional insights using templates
     and statistical thresholds. No external API required.
  2. AI-powered - if OPENAI_API_KEY is set and ``use_ai=True``, delegates
     narrative generation to GPT-4 for richer prose.

Usage:
    from src.ai_insights.insight_engine import InsightEngine
    engine = InsightEngine(db_path="data/database/portugal_data_intelligence.db")
    briefing = engine.generate_executive_briefing()
"""

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from config.settings import (
        DATA_PILLARS,
        DATABASE_PATH,
        OPENAI_MAX_TOKENS,
        OPENAI_MODEL,
        OPENAI_TEMPERATURE,
        REPORT_AUTHOR,
        REPORT_DATE_FORMAT,
    )
except ImportError:
    from pathlib import Path

    _ROOT = Path(__file__).resolve().parent.parent.parent
    DATABASE_PATH = _ROOT / "data" / "database" / "portugal_data_intelligence.db"
    DATA_PILLARS = {}
    OPENAI_MODEL = "gpt-4"
    OPENAI_MAX_TOKENS = 2000
    OPENAI_TEMPERATURE = 0.3
    REPORT_AUTHOR = "Portugal Data Intelligence"
    REPORT_DATE_FORMAT = "%d %B %Y"

try:
    from src.utils.logger import get_logger, log_section
except ImportError:
    import logging

    def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:  # type: ignore[misc]
        return logging.getLogger(name)

    def log_section(logger: logging.Logger, title: str, char: str = "=", width: int = 60) -> None:  # type: ignore[misc]
        logger.info(f"{char * width}\n  {title}\n{char * width}")


from src.ai_insights import ai_narrator, cross_pillar_insights

# Delegate imports from extracted modules
from src.ai_insights.pillar_insights import PILLAR_DISPATCH, _insight_generic

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Crisis periods used in commentary (from central config)
# ---------------------------------------------------------------------------
try:
    from config.settings import CRISIS_PERIODS
except ImportError:
    CRISIS_PERIODS = {
        "sovereign_debt_crisis": {"years": (2011, 2014), "label": "Sovereign Debt Crisis"},
        "covid_pandemic": {"years": (2020, 2021), "label": "COVID-19 Pandemic"},
        "energy_crisis": {"years": (2022, 2023), "label": "Energy and Inflation Crisis"},
    }

# ---------------------------------------------------------------------------
# Pillar display names and DB queries
# ---------------------------------------------------------------------------
PILLAR_QUERIES = {
    "gdp": {
        "query": """
            SELECT d.year, d.quarter, g.*
            FROM fact_gdp g
            JOIN dim_date d ON g.date_key = d.date_key
            ORDER BY d.year, d.quarter
        """,
        "display_name": "Gross Domestic Product",
        "granularity": "quarterly",
    },
    "unemployment": {
        "query": """
            SELECT d.year, d.month, u.*
            FROM fact_unemployment u
            JOIN dim_date d ON u.date_key = d.date_key
            ORDER BY d.year, d.month
        """,
        "display_name": "Unemployment",
        "granularity": "monthly",
    },
    "credit": {
        "query": """
            SELECT d.year, d.month, c.*
            FROM fact_credit c
            JOIN dim_date d ON c.date_key = d.date_key
            ORDER BY d.year, d.month
        """,
        "display_name": "Credit to the Economy",
        "granularity": "monthly",
    },
    "interest_rates": {
        "query": """
            SELECT d.year, d.month, ir.*
            FROM fact_interest_rates ir
            JOIN dim_date d ON ir.date_key = d.date_key
            ORDER BY d.year, d.month
        """,
        "display_name": "Interest Rates",
        "granularity": "monthly",
    },
    "inflation": {
        "query": """
            SELECT d.year, d.month, inf.*
            FROM fact_inflation inf
            JOIN dim_date d ON inf.date_key = d.date_key
            ORDER BY d.year, d.month
        """,
        "display_name": "Inflation",
        "granularity": "monthly",
    },
    "public_debt": {
        "query": """
            SELECT d.year, d.quarter, pd.*
            FROM fact_public_debt pd
            JOIN dim_date d ON pd.date_key = d.date_key
            ORDER BY d.year, d.quarter
        """,
        "display_name": "Public Debt",
        "granularity": "quarterly",
    },
}

# ---------------------------------------------------------------------------
# Insight Engine
# ---------------------------------------------------------------------------


class InsightEngine:
    """
    Main insight generation engine.

    Connects to the project SQLite database, pulls statistical data for each
    macroeconomic pillar, and produces executive-quality narrative commentary.
    """

    def __init__(self, db_path: Optional[str] = None, use_ai: bool = False):
        """
        Initialise the engine.

        Parameters
        ----------
        db_path : str, optional
            Path to the SQLite database.  Defaults to the project database.
        use_ai : bool
            If True **and** OPENAI_API_KEY is set, use GPT-4 for narratives.
        """
        self.db_path = str(db_path or DATABASE_PATH)
        self.use_ai = use_ai and bool(os.environ.get("OPENAI_API_KEY"))
        self._openai_client = None

        if use_ai and not os.environ.get("OPENAI_API_KEY"):
            logger.warning(
                "use_ai=True but OPENAI_API_KEY is not set. "
                "Falling back to rule-based insight generation."
            )

        if self.use_ai:
            try:
                import openai  # noqa: F401

                self._openai_client = openai.OpenAI()
                logger.info("OpenAI client initialised. AI-powered mode enabled.")
            except ImportError:
                logger.warning("openai package not installed. Falling back to rule-based mode.")
                self.use_ai = False

        mode = "AI-powered (GPT-4)" if self.use_ai else "rule-based"
        logger.info(f"InsightEngine initialised in {mode} mode.")

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _fetch_pillar_data(self, pillar: str) -> pd.DataFrame:
        """Fetch raw data for a pillar and return a DataFrame."""
        cfg = PILLAR_QUERIES.get(pillar)
        if cfg is None:
            raise ValueError(f"Unknown pillar: '{pillar}'. Valid: {list(PILLAR_QUERIES.keys())}")
        conn = self._get_connection()
        try:
            df = pd.read_sql(cfg["query"], conn)
        finally:
            conn.close()
        return df

    @staticmethod
    def _numeric_cols(df: pd.DataFrame) -> List[str]:
        """Return numeric columns excluding key/dimension columns."""
        exclude = {"date_key", "year", "quarter", "month", "source_key", "is_provisional", "id"}
        return [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude]

    @staticmethod
    def _safe(value, fmt: str = ".1f") -> str:
        """Format a numeric value safely, returning 'N/A' on failure."""
        if value is None:
            return "N/A"
        try:
            return f"{float(value):{fmt}}"
        except (TypeError, ValueError):
            return str(value)

    # ------------------------------------------------------------------
    # Data summarisation helpers (used by both modes)
    # ------------------------------------------------------------------

    def _summarise_pillar(self, pillar: str) -> Dict[str, Any]:
        """
        Build a structured data summary for a given pillar.

        Returns a dict with keys such as 'latest_value', 'mean', 'trend',
        'growth', 'peak', 'trough', 'crisis_impacts', etc.
        """
        df = self._fetch_pillar_data(pillar)
        if df.empty:
            return {"status": "no_data"}

        num_cols = self._numeric_cols(df)
        if not num_cols:
            return {"status": "no_numeric_columns"}

        time_col = "year"
        sub_col = (
            "quarter" if "quarter" in df.columns else "month" if "month" in df.columns else None
        )

        # Pick primary value column with heuristic
        primary_col = self._pick_primary_col(pillar, num_cols)

        # Annual aggregation
        annual = df.groupby("year")[primary_col].mean().reset_index()
        annual["growth_pct"] = annual[primary_col].pct_change() * 100

        latest_year = int(annual["year"].max())
        earliest_year = int(annual["year"].min())
        latest_matches = annual.loc[annual["year"] == latest_year, primary_col]
        earliest_matches = annual.loc[annual["year"] == earliest_year, primary_col]
        if latest_matches.empty or earliest_matches.empty:
            return {"status": "insufficient_data"}
        latest_val = float(latest_matches.values[0])
        earliest_val = float(earliest_matches.values[0])

        peak_row = annual.loc[annual[primary_col].idxmax()]
        trough_row = annual.loc[annual[primary_col].idxmin()]

        # Trend classification
        half = len(annual) // 2
        first_half_mean = float(annual[primary_col].iloc[:half].mean())
        second_half_mean = float(annual[primary_col].iloc[half:].mean())
        pct_shift = (
            (second_half_mean - first_half_mean) / abs(first_half_mean) * 100
            if first_half_mean != 0
            else 0.0
        )

        if pct_shift > 5:
            trend = "increasing"
        elif pct_shift < -5:
            trend = "decreasing"
        else:
            trend = "stable"

        # Recent momentum (last 3 years average growth)
        recent_growth = annual["growth_pct"].dropna().tail(3)
        recent_avg_growth = float(recent_growth.mean()) if len(recent_growth) > 0 else None

        # Long-run average growth
        all_growth = annual["growth_pct"].dropna()
        longrun_avg_growth = float(all_growth.mean()) if len(all_growth) > 0 else None

        # Latest year-on-year growth
        growth_valid = annual["growth_pct"].dropna()
        latest_growth = float(growth_valid.iloc[-1]) if len(growth_valid) > 0 else None

        # Crisis period impacts
        crisis_impacts = {}
        for crisis_key, crisis_info in CRISIS_PERIODS.items():
            start_y, end_y = crisis_info["years"]
            mask = (annual["year"] >= start_y) & (annual["year"] <= end_y)
            subset = annual.loc[mask]
            if not subset.empty:
                crisis_impacts[crisis_key] = {
                    "label": crisis_info["label"],
                    "mean_value": float(subset[primary_col].mean()),
                    "mean_growth": (
                        float(subset["growth_pct"].mean())
                        if subset["growth_pct"].notna().any()
                        else None
                    ),
                    "min_value": float(subset[primary_col].min()),
                    "max_value": float(subset[primary_col].max()),
                }

        # Volatility
        volatility = float(annual[primary_col].std()) if len(annual) > 1 else None

        # Additional column summaries
        secondary_summaries = {}
        for c in num_cols:
            if c != primary_col:
                series = df[c].dropna()
                if len(series) > 0:
                    secondary_summaries[c] = {
                        "mean": float(series.mean()),
                        "latest": float(series.iloc[-1]),
                        "min": float(series.min()),
                        "max": float(series.max()),
                    }

        return {
            "status": "ok",
            "pillar": pillar,
            "primary_col": primary_col,
            "all_columns": num_cols,
            "earliest_year": earliest_year,
            "latest_year": latest_year,
            "latest_value": latest_val,
            "earliest_value": earliest_val,
            "overall_change_pct": (
                (latest_val - earliest_val) / abs(earliest_val) * 100 if earliest_val != 0 else 0.0
            ),
            "mean": float(annual[primary_col].mean()),
            "median": float(annual[primary_col].median()),
            "std": volatility,
            "peak_value": float(peak_row[primary_col]),
            "peak_year": int(peak_row["year"]),
            "trough_value": float(trough_row[primary_col]),
            "trough_year": int(trough_row["year"]),
            "trend": trend,
            "pct_shift_halves": pct_shift,
            "latest_growth": latest_growth,
            "recent_avg_growth": recent_avg_growth,
            "longrun_avg_growth": longrun_avg_growth,
            "crisis_impacts": crisis_impacts,
            "secondary": secondary_summaries,
            "n_observations": len(df),
            "annual_data": annual.to_dict(orient="records"),
        }

    def _pick_primary_col(self, pillar: str, num_cols: List[str]) -> str:
        """Heuristically select the primary numeric column for a pillar."""
        priorities = {
            "gdp": ["real_gdp", "gdp_real", "nominal_gdp", "gdp_nominal", "gdp", "value"],
            "unemployment": ["unemployment_rate", "rate", "total_rate"],
            "credit": ["total_credit", "credit_total", "credit", "total"],
            "interest_rates": [
                "ecb_rate",
                "main_refinancing_rate",
                "key_rate",
                "euribor",
                "sovereign_yield",
            ],
            "inflation": ["hicp", "cpi_estimated", "inflation_rate", "headline", "inflation"],
            "public_debt": ["debt_to_gdp", "debt_gdp_ratio", "ratio", "total_debt", "debt"],
        }
        for candidate in priorities.get(pillar, []):
            if candidate in num_cols:
                return candidate
            for c in num_cols:
                if candidate in c.lower():
                    return c
        return num_cols[0]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_pillar_insight(self, pillar: str) -> dict:
        """
        Generate insight for a single pillar.

        Returns
        -------
        dict
            Keys: pillar, headline, executive_summary, key_findings,
            risk_assessment, recommendations, outlook.
        """
        log_section(logger, f"GENERATING INSIGHT: {pillar.upper()}")
        data = self._summarise_pillar(pillar)

        if data.get("status") != "ok":
            return self._empty_insight(pillar, reason=data.get("status", "unknown"))

        if self.use_ai:
            try:
                return self._generate_ai_insight(pillar, data)
            except Exception as exc:
                logger.error(f"AI generation failed for {pillar}: {exc}. Falling back to rules.")

        return self._generate_rule_based_insight(pillar, data)

    def generate_cross_pillar_insights(self) -> dict:
        """
        Generate insights about relationships between pillars.

        Returns
        -------
        dict
            Keys: relationships (list[dict]), macro_narrative (str).
        """
        log_section(logger, "GENERATING CROSS-PILLAR INSIGHTS")
        summaries = {}
        for pillar in PILLAR_QUERIES:
            try:
                summaries[pillar] = self._summarise_pillar(pillar)
            except Exception as exc:
                logger.warning(f"Could not summarise {pillar}: {exc}")

        if self.use_ai:
            try:
                return self._generate_ai_cross_pillar(summaries)
            except Exception as exc:
                logger.error(f"AI cross-pillar failed: {exc}. Falling back.")

        return self._generate_rule_based_cross_pillar(summaries)

    def generate_executive_briefing(self) -> dict:
        """
        Generate complete executive briefing covering all pillars.

        Returns
        -------
        dict
            Full briefing with pillar insights, cross-pillar analysis,
            strategic recommendations, and risk matrix.
        """
        log_section(logger, "EXECUTIVE BRIEFING GENERATION")
        start_time = datetime.now()

        pillar_insights = []
        for pillar in PILLAR_QUERIES:
            try:
                insight = self.generate_pillar_insight(pillar)
                pillar_insights.append(insight)
            except Exception as exc:
                logger.error(f"Failed to generate insight for {pillar}: {exc}")
                pillar_insights.append(self._empty_insight(pillar, str(exc)))

        cross_pillar = self.generate_cross_pillar_insights()

        # Build risk matrix from individual pillar assessments
        risk_matrix = []
        for ins in pillar_insights:
            risk_level = self._extract_risk_level(ins.get("risk_assessment", ""))
            risk_matrix.append(
                {
                    "pillar": ins.get("pillar", "unknown"),
                    "risk_level": risk_level,
                    "description": ins.get("risk_assessment", "Assessment unavailable."),
                }
            )

        # Strategic recommendations - synthesise from pillar recommendations
        all_recs = []
        for ins in pillar_insights:
            all_recs.extend(ins.get("recommendations", []))
        strategic_recs = self._synthesise_strategic_recommendations(all_recs, pillar_insights)

        # Overall assessment
        overall = self._build_overall_assessment(pillar_insights, cross_pillar)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Executive briefing generated in {elapsed:.1f}s.")

        return {
            "title": "Portugal Macroeconomic Intelligence Briefing",
            "date": datetime.now().strftime(REPORT_DATE_FORMAT),
            "generated_at": datetime.now().isoformat(),
            "mode": "ai" if self.use_ai else "rule_based",
            "author": REPORT_AUTHOR,
            "overall_assessment": overall,
            "pillar_insights": pillar_insights,
            "cross_pillar_insights": cross_pillar,
            "strategic_recommendations": strategic_recs,
            "risk_matrix": risk_matrix,
            "generation_time_seconds": round(elapsed, 2),
        }

    # ------------------------------------------------------------------
    # Rule-based insight generation (delegates to pillar_insights module)
    # ------------------------------------------------------------------

    def _generate_rule_based_insight(self, pillar: str, data: dict) -> dict:
        """Produce a complete insight dict using templates and data thresholds."""
        fn = PILLAR_DISPATCH.get(pillar, _insight_generic)
        return fn(data)

    # ------------------------------------------------------------------
    # Cross-pillar rule-based insights (delegates to cross_pillar_insights)
    # ------------------------------------------------------------------

    def _generate_rule_based_cross_pillar(self, summaries: Dict[str, dict]) -> dict:
        """Produce cross-pillar narrative using economic relationships."""
        return cross_pillar_insights.generate_rule_based_cross_pillar(summaries, self.db_path)

    # ------------------------------------------------------------------
    # AI-powered insight generation (delegates to ai_narrator module)
    # ------------------------------------------------------------------

    def _generate_ai_insight(self, pillar: str, data: dict) -> dict:
        """Generate insight using OpenAI GPT-4."""
        return ai_narrator.generate_ai_insight(self._openai_client, pillar, data)

    def _generate_ai_cross_pillar(self, summaries: Dict[str, dict]) -> dict:
        """Generate cross-pillar insights using OpenAI GPT-4."""
        return ai_narrator.generate_ai_cross_pillar(self._openai_client, summaries)

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def _empty_insight(self, pillar: str, reason: str = "no_data") -> dict:
        return {
            "pillar": pillar,
            "headline": f"Data unavailable for {pillar.replace('_', ' ').title()}",
            "executive_summary": f"Insufficient data to generate insights for the {pillar.replace('_', ' ')} pillar. Reason: {reason}.",
            "key_findings": [],
            "risk_assessment": "UNKNOWN. Data unavailable for risk assessment.",
            "recommendations": ["Investigate data availability and quality for this pillar."],
            "outlook": "Cannot project outlook without adequate data.",
        }

    @staticmethod
    def _extract_risk_level(risk_text: str) -> str:
        """Extract the risk level keyword from a risk assessment string."""
        text_upper = risk_text.upper()
        for level in [
            "HIGH RISK",
            "ELEVATED RISK",
            "MODERATE RISK",
            "LOW RISK",
            "LOW-TO-MODERATE",
            "UNKNOWN",
        ]:
            if level in text_upper:
                return level.replace(" RISK", "").strip()
        return "UNASSESSED"

    def _synthesise_strategic_recommendations(self, all_recs: list, pillar_insights: list) -> list:
        """Consolidate pillar-level recommendations into strategic themes."""
        strategic = [
            (
                "Sustain fiscal discipline and maintain a declining public debt trajectory, "
                "targeting compliance with EU fiscal governance benchmarks while preserving "
                "space for growth-enhancing public investment."
            ),
            (
                "Accelerate structural reform implementation, particularly in labour market "
                "flexibility, digital transformation, and green transition, to raise potential "
                "output growth and enhance economic resilience."
            ),
            (
                "Strengthen the financial sector's capacity to support economic growth through "
                "improved credit transmission, NPL resolution, and diversification of "
                "corporate financing channels."
            ),
            (
                "Invest in human capital and innovation ecosystems to address skills mismatches, "
                "support higher-value-added sectors, and facilitate Portugal's convergence "
                "toward EU income and productivity levels."
            ),
            (
                "Develop comprehensive risk monitoring and scenario planning capabilities "
                "across macroeconomic pillars to enable proactive policy response to "
                "external shocks and structural shifts."
            ),
        ]
        return strategic[:5]

    def _build_overall_assessment(self, pillar_insights: list, cross_pillar: dict) -> str:
        """Compose the overall assessment paragraph for the executive briefing."""
        risk_levels = [
            self._extract_risk_level(ins.get("risk_assessment", "")) for ins in pillar_insights
        ]
        high_count = sum(1 for r in risk_levels if r == "HIGH")
        elevated_count = sum(1 for r in risk_levels if r == "ELEVATED")

        if high_count >= 2:
            tone = (
                "The overall macroeconomic assessment for Portugal is CONCERNING. "
                f"Multiple pillars ({high_count}) exhibit high-risk conditions, indicating "
                "systemic vulnerabilities that require urgent and coordinated policy action."
            )
        elif high_count >= 1 or elevated_count >= 2:
            tone = (
                "The overall macroeconomic assessment for Portugal is CAUTIOUS. "
                "While some indicators show positive trends, elevated risk conditions "
                "in key areas warrant heightened vigilance and proactive policy engagement."
            )
        elif elevated_count >= 1:
            tone = (
                "The overall macroeconomic assessment for Portugal is BALANCED WITH CAVEATS. "
                "The economy demonstrates fundamental stability, but specific areas of "
                "elevated risk require continued monitoring and targeted intervention."
            )
        else:
            tone = (
                "The overall macroeconomic assessment for Portugal is CAUTIOUSLY OPTIMISTIC. "
                "Key indicators are broadly within acceptable ranges, though maintaining "
                "this trajectory requires sustained policy commitment and structural reform."
            )

        pillars_with_insights = [ins for ins in pillar_insights if ins.get("headline")]
        headlines = "; ".join(
            f"{ins['pillar'].replace('_', ' ').title()}: {ins['headline']}"
            for ins in pillars_with_insights[:3]
        )

        return (
            f"{tone}\n\n"
            f"Key headline findings across pillars: {headlines}.\n\n"
            f"The cross-pillar analysis reveals important interdependencies that "
            f"amplify both upside opportunities and downside risks. Policymakers should "
            f"adopt an integrated view of macroeconomic management, recognising that "
            f"actions in one domain invariably affect outcomes in others."
        )
