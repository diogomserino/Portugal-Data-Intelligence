"""
Portugal Data Intelligence - ETL Pipeline Orchestrator
========================================================
Runs the full Extract -> Transform -> Load pipeline, or individual
steps, for all six data pillars.

Usage:
    python -m src.etl.pipeline
    python -m src.etl.pipeline --step extract
    python -m src.etl.pipeline --step transform
    python -m src.etl.pipeline --step load
"""

import argparse
import sys
import time
from typing import Dict, Optional

import pandas as pd

from config.settings import DATA_PILLARS, DQ_FAIL_ON_ERROR, PROCESSED_DATA_DIR, RAW_DATA_DIR
from src.etl.data_quality import DataQualityChecker
from src.etl.extract import extract_all
from src.etl.generate_eu_benchmark import generate_benchmark_data, load_to_database, save_to_csv
from src.etl.lineage import PipelineTracker, file_checksum
from src.etl.load import load_all
from src.etl.transform import transform_all
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)


# ============================================================================
# Step runners
# ============================================================================


def run_extract() -> Dict[str, pd.DataFrame]:
    """Execute the extraction step."""
    return extract_all()


def run_transform(
    raw_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> Dict[str, pd.DataFrame]:
    """Execute the transformation step.

    If *raw_data* is ``None``, runs extraction first (standalone mode).
    """
    if raw_data is None:
        logger.info("No raw data provided — running extraction first")
        raw_data = extract_all()
    return transform_all(raw_data)


def run_load(
    processed_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> Dict[str, int]:
    """Execute the load step.

    If *processed_data* is ``None``, reads from ``data/processed/`` CSVs
    (standalone mode).
    """
    if processed_data is None:
        logger.info("No processed data provided — loading from CSVs")
        processed_data = {}
        for pillar_key in DATA_PILLARS:
            csv_path = PROCESSED_DATA_DIR / f"{pillar_key}.csv"
            if csv_path.exists():
                processed_data[pillar_key] = pd.read_csv(csv_path)
                logger.info(
                    "  Loaded %s from %s (%s rows)",
                    pillar_key,
                    csv_path,
                    f"{len(processed_data[pillar_key]):,}",
                )
            else:
                logger.warning("  Processed file not found: %s", csv_path)

    return load_all(processed_data)


# ============================================================================
# Summary
# ============================================================================


def _print_summary(
    raw_counts: Dict[str, int],
    processed_counts: Dict[str, int],
    loaded_counts: Dict[str, int],
    elapsed: float,
) -> None:
    """Log a formatted summary table of the pipeline run."""
    log_section(logger, "PIPELINE SUMMARY")

    header = f"{'Pillar':<20} {'Extracted':>10} {'Transformed':>12} {'Loaded':>10}"
    separator = "-" * len(header)
    logger.info(header)
    logger.info(separator)

    all_pillars = sorted(set(raw_counts) | set(processed_counts) | set(loaded_counts))
    for pillar in all_pillars:
        label = DATA_PILLARS.get(pillar, {}).get("name", pillar)
        logger.info(
            "%-20s %10s %12s %10s",
            label,
            f"{raw_counts.get(pillar, 0):,}",
            f"{processed_counts.get(pillar, 0):,}",
            f"{loaded_counts.get(pillar, 0):,}",
        )

    logger.info(separator)
    logger.info(
        "%-20s %10s %12s %10s",
        "TOTAL",
        f"{sum(raw_counts.values()):,}",
        f"{sum(processed_counts.values()):,}",
        f"{sum(loaded_counts.values()):,}",
    )
    logger.info(separator)
    logger.info("Total execution time: %.2f seconds", elapsed)


# ============================================================================
# Pipeline orchestrator
# ============================================================================


def _record_extract_lineage(
    tracker: PipelineTracker,
    raw_data: Dict[str, pd.DataFrame],
) -> None:
    """Record lineage for the extract stage, including file checksums."""
    _RAW_FILES = {
        "gdp": "raw_gdp.csv",
        "unemployment": "raw_unemployment.csv",
        "credit": "raw_credit.csv",
        "interest_rates": "raw_interest_rates.csv",
        "inflation": "raw_inflation.csv",
        "public_debt": "raw_public_debt.csv",
    }
    for pillar, df in raw_data.items():
        raw_path = RAW_DATA_DIR / _RAW_FILES.get(pillar, f"raw_{pillar}.csv")
        cs = file_checksum(raw_path) if raw_path.exists() else None
        tracker.record(
            pillar=pillar,
            stage="extract",
            rows_in=0,
            rows_out=len(df),
            null_count=int(df.isnull().sum().sum()),
            checksum=cs,
        )


def _record_transform_lineage(
    tracker: PipelineTracker,
    raw_data: Optional[Dict[str, pd.DataFrame]],
    processed: Dict[str, pd.DataFrame],
) -> None:
    """Record lineage for the transform stage."""
    for pillar, df in processed.items():
        rows_in = len(raw_data[pillar]) if raw_data and pillar in raw_data else 0
        tracker.record(
            pillar=pillar,
            stage="transform",
            rows_in=rows_in,
            rows_out=len(df),
            null_count=int(df.isnull().sum().sum()),
        )


def _record_load_lineage(
    tracker: PipelineTracker,
    processed: Optional[Dict[str, pd.DataFrame]],
    load_counts: Dict[str, int],
) -> None:
    """Record lineage for the load stage."""
    for pillar, count in load_counts.items():
        rows_in = len(processed[pillar]) if processed and pillar in processed else 0
        tracker.record(
            pillar=pillar,
            stage="load",
            rows_in=rows_in,
            rows_out=count,
        )


def run_pipeline(step: str = "all") -> None:
    """Run the ETL pipeline — full or a single step.

    Parameters
    ----------
    step : str
        One of ``'extract'``, ``'transform'``, ``'load'``, or ``'all'``.
    """
    log_section(logger, "PORTUGAL DATA INTELLIGENCE - ETL PIPELINE", char="=", width=70)
    logger.info("Step requested: %s", step)

    start = time.time()

    raw_counts: Dict[str, int] = {}
    proc_counts: Dict[str, int] = {}
    load_counts: Dict[str, int] = {}

    with PipelineTracker(mode=step) as tracker:
        try:
            raw_data: Optional[Dict[str, pd.DataFrame]] = None
            processed: Optional[Dict[str, pd.DataFrame]] = None

            if step in ("extract", "all"):
                raw_data = run_extract()
                raw_counts = {k: len(v) for k, v in raw_data.items()}
                _record_extract_lineage(tracker, raw_data)

            if step in ("transform", "all"):
                processed = run_transform(raw_data)
                proc_counts = {k: len(v) for k, v in processed.items()}
                _record_transform_lineage(tracker, raw_data, processed)

                # --- Data Quality Gate ---
                dq_checker = DataQualityChecker(processed, run_id=tracker.run_id)
                dq_report = dq_checker.run_all()
                dq_report.save()
                if dq_report.has_critical_failure and DQ_FAIL_ON_ERROR:
                    raise RuntimeError(
                        f"Data quality gate failed: {dq_report.failures} critical failure(s). "
                        "Set DQ_FAIL_ON_ERROR=false to bypass."
                    )

            if step in ("load", "all"):
                load_counts = run_load(processed)
                _record_load_lineage(tracker, processed, load_counts)

                # --- EU Benchmark Data ---
                from config.settings import DATABASE_PATH

                logger.info("Generating EU benchmark data...")
                bench_df = generate_benchmark_data()
                save_to_csv(bench_df)
                bench_rows = load_to_database(bench_df, DATABASE_PATH)
                load_counts["eu_benchmark"] = bench_rows

            _print_summary(raw_counts, proc_counts, load_counts, time.time() - start)
            logger.info("Pipeline completed successfully")

        except Exception as exc:
            logger.error("Pipeline failed after %.2fs: %s", time.time() - start, exc)
            raise


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Portugal Data Intelligence - ETL Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m src.etl.pipeline              # Run full pipeline\n"
            "  python -m src.etl.pipeline --step extract\n"
            "  python -m src.etl.pipeline --step transform\n"
            "  python -m src.etl.pipeline --step load\n"
        ),
    )
    parser.add_argument(
        "--step",
        choices=["extract", "transform", "load", "all"],
        default="all",
        help="Pipeline step to execute (default: all)",
    )
    args = parser.parse_args()
    try:
        run_pipeline(step=args.step)
    except Exception:
        sys.exit(1)
