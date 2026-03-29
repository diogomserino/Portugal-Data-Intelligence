"""
Portugal Data Intelligence - Analysis Orchestrator
====================================================
Main entry point for running the complete analysis suite.
Supports CLI arguments for pillar selection and output format.

Usage:
    python -m src.analysis.run_analysis
    python -m src.analysis.run_analysis --pillar gdp
    python -m src.analysis.run_analysis --output json
    python -m src.analysis.run_analysis --pillar unemployment --output json
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import DATA_PILLARS, DATABASE_PATH, REPORTS_DIR
from src.analysis.correlation_analysis import generate_correlation_report
from src.analysis.statistical_analysis import (
    PILLAR_FUNCTIONS,
    run_all_analyses,
    run_single_analysis,
)
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _format_executive_summary(stat_results: dict, corr_results: Optional[dict] = None) -> str:
    """
    Format an executive summary string from analysis results.

    Parameters
    ----------
    stat_results : dict
        Statistical analysis results keyed by pillar.
    corr_results : dict, optional
        Correlation analysis results.

    Returns
    -------
    str
        Formatted executive summary text.
    """
    lines = []
    width = 72
    lines.append("=" * width)
    lines.append("  PORTUGAL DATA INTELLIGENCE - EXECUTIVE SUMMARY")
    lines.append(f"  Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}")
    lines.append("=" * width)
    lines.append("")

    # Statistical summaries per pillar
    lines.append("-" * width)
    lines.append("  STATISTICAL ANALYSIS BY PILLAR")
    lines.append("-" * width)
    lines.append("")

    for pillar, result in stat_results.items():
        pillar_label = DATA_PILLARS.get(pillar, {}).get("name", pillar.replace("_", " ").title())
        lines.append(f"  [{pillar_label}]")
        summary = result.get("summary", "No summary available.")
        lines.append(f"    {summary}")

        # Key statistics highlights
        statistics = result.get("statistics", {})
        for stat_key, stat_val in statistics.items():
            if isinstance(stat_val, dict) and "mean" in stat_val:
                lines.append(
                    f"    - {stat_key}: mean={stat_val['mean']}, "
                    f"std={stat_val.get('std', 'N/A')}, "
                    f"range=[{stat_val.get('min', 'N/A')}, {stat_val.get('max', 'N/A')}]"
                )

        # Notable findings
        notable = result.get("notable_findings", [])
        if notable:
            lines.append("    Notable periods:")
            for finding in notable:
                lines.append(
                    f"      - {finding.get('period', 'Unknown')} ({finding.get('years', '')}): "
                    f"mean={finding.get('mean', 'N/A')}"
                )
        lines.append("")

    # Correlation summaries
    if corr_results:
        lines.append("-" * width)
        lines.append("  CROSS-PILLAR CORRELATION ANALYSIS")
        lines.append("-" * width)
        lines.append("")

        for analysis_key in ["phillips_curve", "interest_rate_transmission", "debt_gdp_dynamics"]:
            analysis = corr_results.get(analysis_key, {})
            label = analysis_key.replace("_", " ").title()
            lines.append(f"  [{label}]")
            lines.append(f"    {analysis.get('summary', 'No summary available.')}")

            # Show correlation details with sample size
            corr_detail = analysis.get("correlation", {})
            if corr_detail and corr_detail.get("r") is not None:
                r_val = corr_detail.get("r")
                p_val = corr_detail.get("p_value")
                n_val = corr_detail.get("n", "N/A")
                method = corr_detail.get("method", "")
                method_note = f" ({method})" if method else ""
                lines.append(f"    Correlation{method_note}: r={r_val}, p={p_val}, n={n_val}")

            # Show sub-period results if available
            period_data = analysis.get("periods", [])
            if period_data:
                lines.append("    Sub-periods:")
                for prd in period_data:
                    prd_r = prd.get("correlation", "N/A")
                    prd_p = prd.get("p_value", "N/A")
                    prd_n = prd.get("sample_size", "N/A")
                    lines.append(
                        f"      - {prd.get('period', '?')} ({prd.get('years', '')}): "
                        f"r={prd_r}, p={prd_p}, n={prd_n}"
                    )

            lines.append("")

        # Data quality notes
        quality_notes = corr_results.get("data_quality_notes", [])
        if quality_notes:
            lines.append("-" * width)
            lines.append("  DATA QUALITY NOTES")
            lines.append("-" * width)
            lines.append("")
            for note in quality_notes:
                lines.append(f"    * {note}")
            lines.append("")

    lines.append("=" * width)
    lines.append("  END OF EXECUTIVE SUMMARY")
    lines.append("=" * width)

    return "\n".join(lines)


def _save_results_to_json(results: dict, filename: str) -> Path:
    """
    Save analysis results to a JSON file in the reports directory.

    Parameters
    ----------
    results : dict
        Analysis results to serialise.
    filename : str
        Output filename (without directory).

    Returns
    -------
    Path
        Path to the saved file.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / filename

    # Convert any non-serialisable values
    def _make_serialisable(obj):
        if isinstance(obj, dict):
            return {k: _make_serialisable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_make_serialisable(item) for item in obj]
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            return str(obj)

    serialisable = _make_serialisable(results)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serialisable, f, indent=2, ensure_ascii=False)

    logger.info(f"Results saved to: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def main():
    """
    Run the complete analysis suite.

    Steps:
        1. Parse CLI arguments.
        2. Run statistical analysis (all pillars or a specific one).
        3. Run correlation analysis (unless a single pillar is specified).
        4. Save results to JSON in reports/ directory.
        5. Print executive summary to console.
        6. Log total execution time.
    """
    parser = argparse.ArgumentParser(
        description="Portugal Data Intelligence - Analysis Suite",
    )
    parser.add_argument(
        "--pillar",
        type=str,
        choices=list(PILLAR_FUNCTIONS.keys()),
        default=None,
        help="Run analysis for a specific pillar only (e.g. gdp, unemployment).",
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["json", "console"],
        default="json",
        help="Output format: 'json' saves to reports/ directory, 'console' prints to stdout.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to the SQLite database (defaults to settings.DATABASE_PATH).",
    )
    args = parser.parse_args()

    db_path = args.db_path or str(DATABASE_PATH)
    start_time = time.time()

    log_section(logger, "PORTUGAL DATA INTELLIGENCE - ANALYSIS SUITE")
    logger.info(f"Database: {db_path}")
    logger.info(f"Pillar filter: {args.pillar or 'all'}")
    logger.info(f"Output format: {args.output}")

    # ----- Step 1: Statistical analysis -----
    if args.pillar:
        logger.info(f"Running statistical analysis for pillar: {args.pillar}")
        try:
            stat_results = {args.pillar: run_single_analysis(args.pillar, db_path)}
        except Exception as exc:
            logger.error(f"Statistical analysis failed for {args.pillar}: {exc}")
            stat_results = {
                args.pillar: {"summary": f"Failed: {exc}", "statistics": {}, "notable_findings": []}
            }
    else:
        logger.info("Running statistical analysis for all pillars...")
        stat_results = run_all_analyses(db_path)

    # ----- Step 2: Correlation analysis (only when running all pillars) -----
    corr_results = None
    if args.pillar is None:
        logger.info("Running correlation analysis...")
        try:
            corr_results = generate_correlation_report(db_path)
        except Exception as exc:
            logger.error(f"Correlation analysis failed: {exc}")
            corr_results = {"error": str(exc)}

    # ----- Step 3: Compile results -----
    combined_results = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "database": db_path,
            "pillar_filter": args.pillar,
        },
        "statistical_analysis": stat_results,
    }
    if corr_results is not None:
        combined_results["correlation_analysis"] = corr_results

    # ----- Step 4: Output results -----
    if args.output == "json":
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pillar_suffix = f"_{args.pillar}" if args.pillar else ""
        filename = f"analysis_results{pillar_suffix}_{timestamp}.json"
        output_path = _save_results_to_json(combined_results, filename)
        logger.info(f"JSON report saved to: {output_path}")

    # Always print executive summary to console
    summary_text = _format_executive_summary(stat_results, corr_results)
    print(summary_text)

    # ----- Step 5: Timing -----
    elapsed = time.time() - start_time
    logger.info(f"Total execution time: {elapsed:.2f} seconds.")
    print(f"\nAnalysis completed in {elapsed:.2f} seconds.")


if __name__ == "__main__":
    main()
