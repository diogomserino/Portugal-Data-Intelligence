"""
Portugal Data Intelligence - Insight Generation Script
=======================================================
Main script to generate macroeconomic insights and save them as structured
JSON reports.  Supports both rule-based (default) and AI-powered modes.

Usage:
    # Rule-based (no API key needed):
    python -m src.ai_insights.generate_insights

    # AI-powered (requires OPENAI_API_KEY):
    python -m src.ai_insights.generate_insights --use-ai

    # Single pillar:
    python -m src.ai_insights.generate_insights --pillar gdp

    # Combined:
    python -m src.ai_insights.generate_insights --use-ai --pillar unemployment
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from config.settings import DATA_PILLARS, DATABASE_PATH, REPORTS_DIR
except ImportError:
    _ROOT = Path(__file__).resolve().parent.parent.parent
    DATABASE_PATH = _ROOT / "data" / "database" / "portugal_data_intelligence.db"
    REPORTS_DIR = _ROOT / "reports"
    DATA_PILLARS = {
        "gdp": {},
        "unemployment": {},
        "credit": {},
        "interest_rates": {},
        "inflation": {},
        "public_debt": {},
    }

try:
    from src.utils.logger import get_logger, log_section
except ImportError:
    import logging
    from typing import Optional as _Optional

    def get_logger(name: str, level: _Optional[int] = None) -> logging.Logger:  # type: ignore[misc]
        return logging.getLogger(name)

    def log_section(logger: logging.Logger, title: str, char: str = "=", width: int = 60) -> None:  # type: ignore[misc]
        logger.info(f"{char * width}\n  {title}\n{char * width}")


from src.ai_insights.insight_engine import InsightEngine

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
INSIGHTS_DIR = REPORTS_DIR / "insights"

# ---------------------------------------------------------------------------
# Console formatting helpers
# ---------------------------------------------------------------------------
DIVIDER = "=" * 78
THIN_DIVIDER = "-" * 78


def _print_header(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def _print_section(title: str):
    print(f"\n{THIN_DIVIDER}")
    print(f"  {title}")
    print(THIN_DIVIDER)


def _wrap_text(text: str, width: int = 76, indent: int = 2) -> str:
    """Simple word-wrap for console output."""
    import textwrap

    return textwrap.fill(
        text, width=width, initial_indent=" " * indent, subsequent_indent=" " * indent
    )


def _print_pillar_insight(insight: dict):
    """Print a formatted pillar insight to the console."""
    pillar_name = insight.get("pillar", "unknown").replace("_", " ").upper()
    _print_section(f"PILLAR: {pillar_name}")

    print(f"\n  HEADLINE: {insight.get('headline', 'N/A')}")

    print("\n  EXECUTIVE SUMMARY:")
    for paragraph in insight.get("executive_summary", "").split("\n\n"):
        if paragraph.strip():
            print(_wrap_text(paragraph.strip(), indent=4))
            print()

    findings = insight.get("key_findings", [])
    if findings:
        print("  KEY FINDINGS:")
        for i, f in enumerate(findings, 1):
            print(f"    {i}. {f}")

    print(f"\n  RISK ASSESSMENT:")
    print(_wrap_text(insight.get("risk_assessment", "N/A"), indent=4))

    recs = insight.get("recommendations", [])
    if recs:
        print("\n  RECOMMENDATIONS:")
        for i, r in enumerate(recs, 1):
            print(f"    {i}. {r}")

    print(f"\n  OUTLOOK:")
    print(_wrap_text(insight.get("outlook", "N/A"), indent=4))


def _print_cross_pillar(cross: dict):
    """Print cross-pillar insights to the console."""
    _print_section("CROSS-PILLAR ANALYSIS")

    relationships = cross.get("relationships", [])
    for rel in relationships:
        print(
            f"\n  >> {rel.get('name', 'Unknown')} (strength: {rel.get('relationship_strength', 'N/A')})"
        )
        print(_wrap_text(rel.get("narrative", ""), indent=5))

    narrative = cross.get("macro_narrative", "")
    if narrative:
        print("\n  MACRO NARRATIVE:")
        for paragraph in narrative.split("\n\n"):
            if paragraph.strip():
                print(_wrap_text(paragraph.strip(), indent=4))
                print()


def _print_executive_briefing(briefing: dict):
    """Print the full executive briefing to the console."""
    _print_header(briefing.get("title", "Executive Briefing"))
    print(f"  Date: {briefing.get('date', 'N/A')}")
    print(f"  Mode: {briefing.get('mode', 'rule_based')}")
    print(f"  Author: {briefing.get('author', 'N/A')}")

    _print_section("OVERALL ASSESSMENT")
    for paragraph in briefing.get("overall_assessment", "").split("\n\n"):
        if paragraph.strip():
            print(_wrap_text(paragraph.strip(), indent=4))
            print()

    for insight in briefing.get("pillar_insights", []):
        _print_pillar_insight(insight)

    cross = briefing.get("cross_pillar_insights", {})
    if cross:
        _print_cross_pillar(cross)

    strategic = briefing.get("strategic_recommendations", [])
    if strategic:
        _print_section("STRATEGIC RECOMMENDATIONS")
        for i, rec in enumerate(strategic, 1):
            print(f"    {i}. {rec}")

    risk_matrix = briefing.get("risk_matrix", [])
    if risk_matrix:
        _print_section("RISK MATRIX")
        print(f"    {'Pillar':<20} {'Risk Level':<15}")
        print(f"    {'------':<20} {'----------':<15}")
        for entry in risk_matrix:
            pillar_label = entry.get("pillar", "").replace("_", " ").title()
            level = entry.get("risk_level", "N/A")
            print(f"    {pillar_label:<20} {level:<15}")

    print(f"\n  Generation time: {briefing.get('generation_time_seconds', 'N/A')}s")
    print(DIVIDER)


# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------


def _save_json(data: dict, filename: str) -> Path:
    """Save data as a JSON file in the insights directory."""
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = INSIGHTS_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    """Generate all insights and save to reports/insights/."""
    parser = argparse.ArgumentParser(
        description="Portugal Data Intelligence - Insight Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m src.ai_insights.generate_insights\n"
            "  python -m src.ai_insights.generate_insights --use-ai\n"
            "  python -m src.ai_insights.generate_insights --pillar gdp\n"
            "  python -m src.ai_insights.generate_insights --pillar unemployment --use-ai\n"
        ),
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        default=False,
        help="Enable OpenAI GPT-4 for narrative generation (requires OPENAI_API_KEY).",
    )
    parser.add_argument(
        "--pillar",
        type=str,
        default=None,
        choices=list(DATA_PILLARS.keys()),
        help="Generate insight for a single pillar only.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Override the database path.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress console output (still saves JSON).",
    )

    args = parser.parse_args()

    log_section(logger, "PORTUGAL DATA INTELLIGENCE - INSIGHT GENERATION")
    start_time = time.time()

    db_path = args.db_path or str(DATABASE_PATH)
    engine = InsightEngine(db_path=db_path, use_ai=args.use_ai)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.pillar:
        # Single pillar mode
        logger.info(f"Generating insight for pillar: {args.pillar}")
        insight = engine.generate_pillar_insight(args.pillar)

        filename = f"insight_{args.pillar}_{timestamp}.json"
        filepath = _save_json(insight, filename)
        logger.info(f"Insight saved to: {filepath}")

        if not args.quiet:
            _print_header(f"INSIGHT: {args.pillar.upper()}")
            _print_pillar_insight(insight)
            print(f"\n  Saved to: {filepath}")
            print(DIVIDER)
    else:
        # Full executive briefing
        logger.info("Generating full executive briefing...")
        briefing = engine.generate_executive_briefing()

        filename = f"executive_briefing_{timestamp}.json"
        filepath = _save_json(briefing, filename)
        logger.info(f"Executive briefing saved to: {filepath}")

        if not args.quiet:
            _print_executive_briefing(briefing)
            print(f"\n  Saved to: {filepath}")
            print(DIVIDER)

    elapsed = time.time() - start_time
    logger.info(f"Insight generation completed in {elapsed:.1f}s.")

    if not args.quiet:
        print(f"\n  Total execution time: {elapsed:.1f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
