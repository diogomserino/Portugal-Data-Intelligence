"""
Portugal Data Intelligence - Data Quality Framework
=====================================================
Validates processed DataFrames before database loading using schema,
range, completeness, consistency, and freshness checks.

Usage:
    from src.etl.data_quality import DataQualityChecker
    checker = DataQualityChecker(processed_data)
    report = checker.run_all()
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import DATA_PILLARS, DATA_QUALITY_DIR, DATA_RANGES, END_YEAR, START_YEAR
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Expected columns per pillar (must match the keep_cols in transform configs).
_EXPECTED_COLUMNS: Dict[str, List[str]] = {
    "gdp": [
        "date_key",
        "nominal_gdp",
        "real_gdp",
        "gdp_growth_yoy",
        "gdp_growth_qoq",
        "gdp_per_capita",
        "is_provisional",
    ],
    "unemployment": [
        "date_key",
        "unemployment_rate",
        "youth_unemployment_rate",
        "long_term_unemployment_rate",
        "labour_force_participation_rate",
        "is_provisional",
    ],
    "credit": [
        "date_key",
        "total_credit",
        "credit_nfc",
        "credit_households",
        "npl_ratio",
        "is_provisional",
    ],
    "interest_rates": [
        "date_key",
        "ecb_main_refinancing_rate",
        "euribor_3m",
        "euribor_6m",
        "euribor_12m",
        "portugal_10y_bond_yield",
        "is_provisional",
    ],
    "inflation": [
        "date_key",
        "hicp",
        "cpi_estimated",
        "core_inflation",
        "is_provisional",
    ],
    "public_debt": [
        "date_key",
        "total_debt",
        "debt_to_gdp_ratio",
        "budget_deficit",
        "budget_deficit_annual",
        "external_debt_share_estimated",
        "is_provisional",
    ],
}

# Expected row counts per pillar.
_EXPECTED_ROWS = {
    "gdp": 64,
    "unemployment": 192,
    "credit": 192,
    "interest_rates": 192,
    "inflation": 192,
    "public_debt": 64,
}


@dataclass
class CheckResult:
    """Result of a single data quality check."""

    name: str
    status: str  # pass | warn | fail
    details: str
    affected_rows: int = 0
    pillar: Optional[str] = None


@dataclass
class DQReport:
    """Full data quality report for a pipeline run."""

    run_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == "pass")

    @property
    def warnings(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    @property
    def failures(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")

    @property
    def has_critical_failure(self) -> bool:
        return self.failures > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "summary": {
                "total": len(self.checks),
                "passed": self.passed,
                "warnings": self.warnings,
                "failures": self.failures,
            },
            "checks": [asdict(c) for c in self.checks],
        }

    def save(self, directory: Optional[Path] = None) -> Path:
        """Write report as JSON. Returns the file path."""
        out_dir = directory or DATA_QUALITY_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = self.run_id or "manual"
        path = out_dir / f"dq_report_{suffix}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("DQ report saved to %s", path)
        return path


class DataQualityChecker:
    """Runs data quality checks on processed DataFrames.

    Parameters
    ----------
    processed_data : dict[str, pd.DataFrame]
        Processed DataFrames keyed by pillar name.
    run_id : str, optional
        Pipeline run correlation ID.
    """

    def __init__(
        self,
        processed_data: Dict[str, pd.DataFrame],
        run_id: Optional[str] = None,
    ):
        self.data = processed_data
        self.report = DQReport(run_id=run_id)

    def _add(
        self,
        name: str,
        status: str,
        details: str,
        affected_rows: int = 0,
        pillar: Optional[str] = None,
    ) -> None:
        self.report.checks.append(
            CheckResult(
                name=name,
                status=status,
                details=details,
                affected_rows=affected_rows,
                pillar=pillar,
            )
        )

    # -- Schema checks --------------------------------------------------------

    def check_schema(self) -> None:
        """Verify each pillar has the expected columns."""
        for pillar, df in self.data.items():
            expected = _EXPECTED_COLUMNS.get(pillar)
            if expected is None:
                continue
            actual = set(df.columns)
            missing = set(expected) - actual
            if missing:
                self._add(
                    f"schema_{pillar}",
                    "fail",
                    f"Missing columns: {sorted(missing)}",
                    pillar=pillar,
                )
            else:
                self._add(f"schema_{pillar}", "pass", "All expected columns present", pillar=pillar)

    # -- Not-null checks on primary metrics -----------------------------------

    def check_not_null(self) -> None:
        """Primary metric columns must not be entirely null."""
        primary_cols = {
            "gdp": ["nominal_gdp"],
            "unemployment": ["unemployment_rate"],
            "credit": ["total_credit"],
            "interest_rates": ["euribor_3m"],
            "inflation": ["hicp"],
            "public_debt": ["total_debt"],
        }
        for pillar, cols in primary_cols.items():
            df = self.data.get(pillar)
            if df is None:
                continue
            for col in cols:
                if col not in df.columns:
                    continue
                null_count = int(df[col].isnull().sum())
                if null_count == len(df):
                    self._add(
                        f"not_null_{pillar}_{col}",
                        "fail",
                        f"Column '{col}' is entirely null",
                        affected_rows=null_count,
                        pillar=pillar,
                    )
                elif null_count > 0:
                    self._add(
                        f"not_null_{pillar}_{col}",
                        "warn",
                        f"Column '{col}' has {null_count} nulls",
                        affected_rows=null_count,
                        pillar=pillar,
                    )
                else:
                    self._add(
                        f"not_null_{pillar}_{col}", "pass", f"No nulls in '{col}'", pillar=pillar
                    )

    # -- Range checks ---------------------------------------------------------

    def check_ranges(self) -> None:
        """Values must fall within plausible ranges defined in settings."""
        for pillar, col_ranges in DATA_RANGES.items():
            df = self.data.get(pillar)
            if df is None:
                continue
            for col, (lo, hi) in col_ranges.items():
                if col not in df.columns:
                    continue
                series = df[col].dropna()
                if series.empty:
                    continue
                out_of_range = ((series < lo) | (series > hi)).sum()
                if out_of_range > 0:
                    actual_min, actual_max = series.min(), series.max()
                    self._add(
                        f"range_{pillar}_{col}",
                        "warn",
                        f"{out_of_range} values outside [{lo}, {hi}] "
                        f"(actual range: [{actual_min:.2f}, {actual_max:.2f}])",
                        affected_rows=int(out_of_range),
                        pillar=pillar,
                    )
                else:
                    self._add(
                        f"range_{pillar}_{col}",
                        "pass",
                        f"All values within [{lo}, {hi}]",
                        pillar=pillar,
                    )

    # -- Temporal completeness ------------------------------------------------

    def check_completeness(self) -> None:
        """No gaps in the date sequence for each pillar."""
        for pillar, df in self.data.items():
            if "date_key" not in df.columns:
                continue
            expected = _EXPECTED_ROWS.get(pillar)
            if expected is None:
                continue
            actual = len(df)
            if actual < expected:
                self._add(
                    f"completeness_{pillar}",
                    "warn",
                    f"Expected {expected} rows, got {actual} (missing {expected - actual})",
                    affected_rows=expected - actual,
                    pillar=pillar,
                )
            else:
                self._add(
                    f"completeness_{pillar}",
                    "pass",
                    f"Row count matches expected ({actual})",
                    pillar=pillar,
                )

    # -- Cross-pillar consistency ---------------------------------------------

    def check_consistency(self) -> None:
        """Logical relationships between columns/pillars hold."""
        # Credit components <= total
        credit = self.data.get("credit")
        if credit is not None and {"total_credit", "credit_nfc", "credit_households"}.issubset(
            credit.columns
        ):
            parts_sum = credit["credit_nfc"].fillna(0) + credit["credit_households"].fillna(0)
            violations = (parts_sum > credit["total_credit"] * 1.01).sum()
            if violations > 0:
                self._add(
                    "consistency_credit_components",
                    "warn",
                    f"NFC + Household credit > Total in {violations} rows",
                    affected_rows=int(violations),
                    pillar="credit",
                )
            else:
                self._add(
                    "consistency_credit_components",
                    "pass",
                    "Credit components <= total",
                    pillar="credit",
                )

        # Youth unemployment >= general unemployment
        unemp = self.data.get("unemployment")
        if unemp is not None and {"unemployment_rate", "youth_unemployment_rate"}.issubset(
            unemp.columns
        ):
            mask = unemp["youth_unemployment_rate"].dropna() < unemp["unemployment_rate"]
            violations = mask.sum()
            if violations > 0:
                self._add(
                    "consistency_youth_unemp",
                    "warn",
                    f"Youth unemployment < general in {violations} rows",
                    affected_rows=int(violations),
                    pillar="unemployment",
                )
            else:
                self._add(
                    "consistency_youth_unemp",
                    "pass",
                    "Youth unemployment >= general",
                    pillar="unemployment",
                )

        # Euribor term structure: 3M <= 6M <= 12M (generally)
        rates = self.data.get("interest_rates")
        if rates is not None and {"euribor_3m", "euribor_6m", "euribor_12m"}.issubset(
            rates.columns
        ):
            mask = rates["euribor_3m"].dropna() > rates["euribor_12m"].dropna() + 0.1
            violations = mask.sum()
            if violations > 0:
                self._add(
                    "consistency_euribor_term",
                    "warn",
                    f"Euribor 3M > 12M + 10bps in {violations} rows",
                    affected_rows=int(violations),
                    pillar="interest_rates",
                )
            else:
                self._add(
                    "consistency_euribor_term",
                    "pass",
                    "Euribor term structure consistent",
                    pillar="interest_rates",
                )

        # HICP != CPI estimated (they should differ)
        infl = self.data.get("inflation")
        if infl is not None and {"hicp", "cpi_estimated"}.issubset(infl.columns):
            both_valid = infl[["hicp", "cpi_estimated"]].dropna()
            if len(both_valid) > 0:
                identical = (both_valid["hicp"] == both_valid["cpi_estimated"]).all()
                if identical:
                    self._add(
                        "consistency_hicp_cpi",
                        "warn",
                        "HICP and cpi_estimated are identical — offset not applied",
                        pillar="inflation",
                    )
                else:
                    self._add(
                        "consistency_hicp_cpi",
                        "pass",
                        "HICP and cpi_estimated values differ as expected",
                        pillar="inflation",
                    )

    # -- Statistical outlier detection ----------------------------------------

    _ZSCORE_THRESHOLD = 3.0

    def check_outliers(self) -> None:
        """Flag values with |Z-score| > 3 as potential outliers.

        Uses only numeric columns that appear in DATA_RANGES (the columns
        we care about for quality purposes).  This is a warning-level check
        — outliers may be genuine extreme events (e.g. COVID GDP drop).
        """
        for pillar, col_ranges in DATA_RANGES.items():
            df = self.data.get(pillar)
            if df is None:
                continue
            for col in col_ranges:
                if col not in df.columns:
                    continue
                series = df[col].dropna()
                if len(series) < 10:
                    continue  # too few data points for meaningful Z-scores
                mean = series.mean()
                std = series.std()
                if std == 0:
                    continue
                z_scores = ((series - mean) / std).abs()
                n_outliers = int((z_scores > self._ZSCORE_THRESHOLD).sum())
                if n_outliers > 0:
                    worst_z = z_scores.max()
                    self._add(
                        f"outlier_{pillar}_{col}",
                        "warn",
                        f"{n_outliers} value(s) with |Z| > {self._ZSCORE_THRESHOLD} "
                        f"(max |Z| = {worst_z:.1f})",
                        affected_rows=n_outliers,
                        pillar=pillar,
                    )
                else:
                    self._add(
                        f"outlier_{pillar}_{col}",
                        "pass",
                        f"No statistical outliers (|Z| <= {self._ZSCORE_THRESHOLD})",
                        pillar=pillar,
                    )

    # -- Data drift detection -------------------------------------------------

    _DRIFT_BASELINE_FILE = "dq_baseline.json"
    _DRIFT_THRESHOLD = 0.25  # 25% relative change in mean or std triggers warning

    def check_drift(self) -> None:
        """Detect distribution drift by comparing current stats to a saved baseline.

        On first run, saves the baseline. On subsequent runs, compares current
        mean and std to the baseline and warns if relative change exceeds the
        threshold.
        """
        baseline_path = DATA_QUALITY_DIR / self._DRIFT_BASELINE_FILE
        DATA_QUALITY_DIR.mkdir(parents=True, exist_ok=True)

        # Load existing baseline (if any)
        baseline: Dict[str, Dict[str, Dict[str, float]]] = {}
        if baseline_path.exists():
            with open(baseline_path, "r", encoding="utf-8") as f:
                baseline = json.load(f)

        current: Dict[str, Dict[str, Dict[str, float]]] = {}

        for pillar, col_ranges in DATA_RANGES.items():
            df = self.data.get(pillar)
            if df is None:
                continue
            current[pillar] = {}
            for col in col_ranges:
                if col not in df.columns:
                    continue
                series = df[col].dropna()
                if len(series) < 10:
                    continue
                stats = {
                    "mean": round(float(series.mean()), 4),
                    "std": round(float(series.std()), 4),
                    "median": round(float(series.median()), 4),
                }
                current[pillar][col] = stats

                # Compare to baseline if it exists
                prev = baseline.get(pillar, {}).get(col)
                if prev is not None:
                    drifts = []
                    for stat_name in ("mean", "std"):
                        prev_val = prev.get(stat_name, 0)
                        curr_val = stats[stat_name]
                        if abs(prev_val) > 0.01:
                            rel_change = abs(curr_val - prev_val) / abs(prev_val)
                            if rel_change > self._DRIFT_THRESHOLD:
                                drifts.append(
                                    f"{stat_name}: {prev_val:.2f} → {curr_val:.2f} "
                                    f"({rel_change:.0%} change)"
                                )
                    if drifts:
                        self._add(
                            f"drift_{pillar}_{col}",
                            "warn",
                            f"Distribution drift detected: {'; '.join(drifts)}",
                            pillar=pillar,
                        )
                    else:
                        self._add(
                            f"drift_{pillar}_{col}",
                            "pass",
                            "No significant drift from baseline",
                            pillar=pillar,
                        )

        # Save current stats as the new baseline
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        logger.info("Drift baseline saved to %s", baseline_path)

    # -- Freshness check ------------------------------------------------------

    def check_freshness(self) -> None:
        """Latest data should reach close to END_YEAR."""
        for pillar, df in self.data.items():
            if "date_key" not in df.columns:
                continue
            latest = df["date_key"].max()
            if latest and str(END_YEAR) in str(latest):
                self._add(
                    f"freshness_{pillar}", "pass", f"Latest date_key: {latest}", pillar=pillar
                )
            else:
                self._add(
                    f"freshness_{pillar}",
                    "warn",
                    f"Latest date_key ({latest}) does not include {END_YEAR}",
                    pillar=pillar,
                )

    # -- Run all checks -------------------------------------------------------

    def run_all(self) -> DQReport:
        """Execute all checks and return the consolidated report."""
        logger.info("Running data quality checks...")
        self.check_schema()
        self.check_not_null()
        self.check_ranges()
        self.check_outliers()
        self.check_drift()
        self.check_completeness()
        self.check_consistency()
        self.check_freshness()

        logger.info(
            "DQ results: %d passed, %d warnings, %d failures (out of %d checks)",
            self.report.passed,
            self.report.warnings,
            self.report.failures,
            len(self.report.checks),
        )
        return self.report
