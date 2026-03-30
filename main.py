"""
Portugal Data Intelligence -- Main Entry Point
===============================================
Single command to run the complete pipeline from data generation
through to report delivery.

Usage:
    python main.py                    # Run everything
    python main.py --mode full        # Same as above
    python main.py --mode etl         # Data generation + ETL only
    python main.py --mode analysis    # Analysis + visualisations only
    python main.py --mode reports     # Reports + insights only
    python main.py --mode quick       # ETL + analysis (no reports)
    python main.py --list             # Show available modes
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Project root on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATABASE_PATH, REPORTS_DIR, ensure_directories
from src.utils.logger import get_logger, log_section

logger = get_logger("main")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "2.1.0"

BANNER = r"""
 ____            _                   _   ____        _
|  _ \ ___  _ __| |_ _   _  __ _  _| | |  _ \  __ _| |_ __ _
| |_) / _ \| '__| __| | | |/ _` |/ _` | | | | |/ _` | __/ _` |
|  __/ (_) | |  | |_| |_| | (_| | (_| | | |_| | (_| | || (_| |
|_|   \___/|_|   \__|\__,_|\__, |\__,_| |____/ \__,_|\__\__,_|
 ___       _       _ _ _   |___/
|_ _|_ __ | |_ ___| | (_) __ _  ___ _ __   ___ ___
 | || '_ \| __/ _ \ | | |/ _` |/ _ \ '_ \ / __/ _ \
 | || | | | ||  __/ | | | (_| |  __/ | | | (_|  __/
|___|_| |_|\__\___|_|_|_|\__, |\___|_| |_|\___\___|
                         |___/
"""


# ---------------------------------------------------------------------------
# Step result dataclass
# ---------------------------------------------------------------------------

class StepResult:
    """Holds the outcome of a single pipeline step."""

    __slots__ = ("step", "files", "errors")

    def __init__(self, step: str) -> None:
        self.step = step
        self.files: List[str] = []
        self.errors: List[str] = []

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def __repr__(self) -> str:
        status = "OK" if self.ok else f"ERRORS({len(self.errors)})"
        return f"StepResult({self.step!r}, {status}, files={len(self.files)})"


# ---------------------------------------------------------------------------
# Step runners
# ---------------------------------------------------------------------------

def _run_etl() -> StepResult:
    """Fetch real data from APIs and run the ETL pipeline."""
    result = StepResult("ETL")

    # Clean database for fresh load
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
        logger.info("Removed existing database for clean rebuild.")

    # 1. Fetch real data (with synthetic fallback)
    log_section(logger, "STEP 1 / ETL: Fetch Real Data from APIs")
    try:
        from src.etl.fetch_real_data import fetch_all
        fetch_all()
        logger.info("Real data fetch completed.")
    except (ImportError, OSError, ValueError) as exc:
        logger.error("Real data fetch failed: %s", exc)
        result.errors.append(f"Real data fetch failed: {exc}")

        logger.warning("Falling back to synthetic data generation...")
        try:
            from src.etl.generate_data import main as generate_data
            generate_data()
            logger.info("Synthetic data generation completed (fallback).")
        except Exception as exc2:
            logger.error("Synthetic fallback also failed: %s", exc2)
            result.errors.append(f"Synthetic fallback also failed: {exc2}")

    # 2. Run ETL pipeline (extract -> transform -> load)
    log_section(logger, "STEP 2 / ETL: Extract -> Transform -> Load")
    try:
        from src.etl.pipeline import run_pipeline
        run_pipeline(step="all")
        result.files.append(str(DATABASE_PATH))
        logger.info("ETL pipeline completed.")
    except Exception as exc:
        logger.error("ETL pipeline failed: %s", exc)
        result.errors.append(f"ETL pipeline failed: {exc}")

    # 3. Generate and load EU benchmark data
    log_section(logger, "STEP 2b / ETL: EU Benchmark Data")
    try:
        from src.etl.generate_eu_benchmark import run_pipeline as run_benchmark
        run_benchmark()
        logger.info("EU benchmark data loaded.")
    except Exception as exc:
        logger.warning("EU benchmark generation failed: %s", exc)
        result.errors.append(f"EU benchmark failed: {exc}")

    return result


def _run_analysis() -> StepResult:
    """Run statistical analysis and generate visualisations."""
    from src.analysis.statistical_analysis import run_all_analyses
    from src.analysis.correlation_analysis import generate_correlation_report
    from src.analysis.visualisations import generate_all_charts
    from src.analysis.benchmarking import plot_benchmark_comparison

    result = StepResult("Analysis")
    db_path = str(DATABASE_PATH)

    # 1. Statistical + correlation analysis
    log_section(logger, "STEP 3 / ANALYSIS: Statistical & Correlation Analysis")
    try:
        stat_results = run_all_analyses(db_path)
        logger.info("Statistical analysis completed for %d pillars.", len(stat_results))

        generate_correlation_report(db_path)
        logger.info("Correlation analysis completed.")
    except Exception as exc:
        logger.error("Statistical / correlation analysis failed: %s", exc)
        result.errors.append(f"Statistical / correlation analysis failed: {exc}")

    # 2. Generate all charts
    log_section(logger, "STEP 4 / ANALYSIS: Visualisation Generation")
    try:
        chart_paths = generate_all_charts(db_path=db_path)
        result.files.extend(chart_paths)
        logger.info("Generated %d chart(s).", len(chart_paths))
    except Exception as exc:
        logger.error("Chart generation failed: %s", exc)
        result.errors.append(f"Chart generation failed: {exc}")

    # 3. Generate benchmark charts
    try:
        benchmark_paths = plot_benchmark_comparison(db_path=db_path)
        result.files.extend([str(p) for p in benchmark_paths])
        logger.info("Generated %d benchmark chart(s).", len(benchmark_paths))
    except Exception as exc:
        logger.error("Benchmark chart generation failed: %s", exc)
        result.errors.append(f"Benchmark chart generation failed: {exc}")

    return result


def _run_reports() -> StepResult:
    """Generate AI insights and executive briefing."""
    from src.ai_insights.insight_engine import InsightEngine

    result = StepResult("Reports")

    # AI / rule-based insights
    log_section(logger, "STEP 5 / REPORTS: Insight Generation")
    try:
        engine = InsightEngine(db_path=str(DATABASE_PATH), use_ai=False)
        briefing = engine.generate_executive_briefing()
        logger.info("Executive briefing generated (rule-based mode).")

        # Persist the briefing JSON
        insights_dir = REPORTS_DIR / "insights"
        insights_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        briefing_path = insights_dir / f"executive_briefing_{timestamp}.json"
        briefing_path.write_text(
            json.dumps(briefing, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        result.files.append(str(briefing_path))
        logger.info("Briefing saved to: %s", briefing_path)
    except Exception as exc:
        logger.error("Insight generation failed: %s", exc)
        result.errors.append(f"Insight generation failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# Mode → step registry
# ---------------------------------------------------------------------------

_MODE_STEPS = {
    "full":     [_run_etl, _run_analysis, _run_reports],
    "etl":      [_run_etl],
    "analysis": [_run_analysis],
    "reports":  [_run_reports],
    "quick":    [_run_etl, _run_analysis],
}

_MODE_DESCRIPTIONS = {
    "full":     "Run the complete pipeline: ETL -> Analysis -> Reports",
    "etl":      "Fetch real data from APIs and run the ETL pipeline",
    "analysis": "Run statistical analysis and generate visualisations",
    "reports":  "Generate AI insights and executive briefing",
    "quick":    "ETL + Analysis (skip report generation)",
}


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(results: List[StepResult], elapsed: float) -> None:
    """Log a final summary table of generated artefacts and any errors."""
    logger.info("=" * 72)
    logger.info("  PIPELINE SUMMARY")
    logger.info("=" * 72)

    total_files = 0
    total_errors = 0

    for r in results:
        total_files += len(r.files)
        total_errors += len(r.errors)

        status = "OK" if r.ok else f"PARTIAL ({len(r.errors)} error(s))"
        logger.info("  [%s]  Status: %s", r.step, status)

        for f in r.files:
            logger.info("    -> %s", f)
        for e in r.errors:
            logger.warning("    !! %s", e)

    logger.info("-" * 72)
    logger.info("  Total artefacts generated : %d", total_files)
    logger.info("  Total errors              : %d", total_errors)
    logger.info("  Total execution time      : %.2f seconds", elapsed)
    logger.info("-" * 72)

    if total_errors == 0:
        logger.info("  Result: ALL STEPS COMPLETED SUCCESSFULLY")
    else:
        logger.warning("  Result: COMPLETED WITH %d ERROR(S)", total_errors)

    logger.info("=" * 72)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Portugal Data Intelligence - Main Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                   # Run the full pipeline\n"
            "  python main.py --mode etl        # Data generation + ETL only\n"
            "  python main.py --mode analysis   # Analysis + charts only\n"
            "  python main.py --mode reports    # AI insights + executive briefing\n"
            "  python main.py --mode quick      # ETL + analysis (no reports)\n"
            "  python main.py --list            # Show available modes\n"
        ),
    )
    parser.add_argument(
        "--mode",
        choices=list(_MODE_STEPS.keys()),
        default="full",
        help="Pipeline mode to execute (default: full).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        default=False,
        help="List all available pipeline modes and exit.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Orchestrate the Portugal Data Intelligence pipeline."""
    args = _parse_args()

    if args.list:
        print("\nAvailable pipeline modes:\n")
        for mode, desc in _MODE_DESCRIPTIONS.items():
            print(f"  --mode {mode:<10s}  {desc}")
        print()
        return 0

    # Banner
    logger.info(BANNER)
    logger.info("  Version %s", VERSION)
    logger.info("  Mode: %s", args.mode)
    logger.info("  Project root: %s", PROJECT_ROOT)
    logger.info("  Database: %s", DATABASE_PATH)

    ensure_directories()

    start_time = time.time()
    all_results: List[StepResult] = []

    log_section(logger, f"PIPELINE START  --  mode={args.mode}", char="=", width=72)

    try:
        for step_fn in _MODE_STEPS[args.mode]:
            all_results.append(step_fn())
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user.")
        _print_summary(all_results, time.time() - start_time)
        return 130

    elapsed = time.time() - start_time
    _print_summary(all_results, elapsed)

    log_section(logger, "PIPELINE COMPLETE", char="=", width=72)

    total_errors = sum(len(r.errors) for r in all_results)
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
