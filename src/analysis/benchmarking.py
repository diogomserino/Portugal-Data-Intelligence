"""
Portugal Data Intelligence - EU Benchmarking Module
=====================================================
Compares Portugal's macroeconomic performance against key EU peers
and European averages.

Analyses include:
    - Indicator-level comparison (ranking, gap to EU average, trend)
    - Convergence/divergence analysis across all indicators
    - Peer comparison tables
    - Ranking history over time
    - Comprehensive benchmark reports
    - Visualisations (radar chart, small multiples)

Usage:
    from src.analysis.benchmarking import EUBenchmark, plot_benchmark_comparison
    bench = EUBenchmark(db_path="data/database/portugal_data_intelligence.db")
    report = bench.generate_benchmark_report()
    plot_benchmark_comparison(db_path="data/database/portugal_data_intelligence.db")

Author: Portugal Data Intelligence
"""

import sqlite3
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATABASE_PATH, POWERBI_DIR, ensure_directories
from src.reporting.shared_styles import (
    CHART_BACKGROUND,
    CHART_DPI,
    CHART_FONT_SIZES,
    CHART_GRID_ALPHA,
    COUNTRY_COLORS,
)
from src.utils.logger import get_logger, log_section

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = get_logger("benchmarking")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INDICATORS = [
    "gdp_growth",
    "unemployment",
    "inflation",
    "debt_to_gdp",
    "interest_rate_10y",
]

INDICATOR_LABELS = {
    "gdp_growth": "GDP Growth (% YoY)",
    "unemployment": "Unemployment Rate (%)",
    "inflation": "Inflation HICP (%)",
    "debt_to_gdp": "Debt-to-GDP (%)",
    "interest_rate_10y": "10Y Bond Yield (%)",
}

# Indicators where lower is better (used for ranking)
LOWER_IS_BETTER = {"unemployment", "inflation", "debt_to_gdp", "interest_rate_10y"}

PEER_COUNTRIES = ["PT", "DE", "ES", "FR", "IT"]
ALL_ENTITIES = ["PT", "DE", "ES", "FR", "IT", "EU_AVG", "EA_AVG"]


# =============================================================================
# EUBenchmark class
# =============================================================================


class EUBenchmark:
    """EU benchmarking analysis for Portugal's macroeconomic indicators."""

    def __init__(self, db_path: str) -> None:
        """Load Portugal and EU benchmark data from the database.

        Parameters
        ----------
        db_path : str
            Path to the SQLite database file.
        """
        self.db_path = db_path
        self._load_data()

    def _load_data(self) -> None:
        """Load benchmark data from the database into a DataFrame."""
        logger.info(f"Loading benchmark data from {self.db_path}")
        conn = sqlite3.connect(str(self.db_path))
        try:
            self.data = pd.read_sql_query(
                "SELECT date_key, country_code, country_name, indicator, value "
                "FROM fact_eu_benchmark ORDER BY date_key, country_code, indicator",
                conn,
            )
        finally:
            conn.close()

        self.data["year"] = self.data["date_key"].astype(int)
        self.latest_year = int(self.data["year"].max())
        logger.info(f"Loaded {len(self.data):,} records, latest year: {self.latest_year}")

    def compare_indicator(self, indicator: str) -> dict:
        """Compare Portugal against all peers for a given indicator.

        Parameters
        ----------
        indicator : str
            One of the benchmark indicators (e.g. 'gdp_growth').

        Returns
        -------
        dict
            Comparison result containing ranking, Portugal vs EU average
            difference, trend direction, and convergence rate.
        """
        logger.info(f"Comparing indicator: {indicator}")
        df = self.data[self.data["indicator"] == indicator].copy()

        # Latest year ranking (peers only, excluding averages)
        latest = df[
            (df["year"] == self.latest_year) & (df["country_code"].isin(PEER_COUNTRIES))
        ].copy()

        ascending = indicator in LOWER_IS_BETTER
        latest = latest.sort_values("value", ascending=ascending)
        latest["rank"] = range(1, len(latest) + 1)

        ranking = [
            {
                "country": row["country_code"],
                "value": row["value"],
                "rank": row["rank"],
            }
            for _, row in latest.iterrows()
        ]

        # Portugal vs EU average
        pt_latest = df[(df["year"] == self.latest_year) & (df["country_code"] == "PT")][
            "value"
        ].values
        eu_latest = df[(df["year"] == self.latest_year) & (df["country_code"] == "EU_AVG")][
            "value"
        ].values

        pt_val = float(pt_latest[0]) if len(pt_latest) > 0 else np.nan
        eu_val = float(eu_latest[0]) if len(eu_latest) > 0 else np.nan
        gap = round(pt_val - eu_val, 2)

        # Portugal rank
        pt_rank_row = [r for r in ranking if r["country"] == "PT"]
        pt_rank = pt_rank_row[0]["rank"] if pt_rank_row else None

        # Convergence/divergence trend (last 5 years)
        trend, convergence_rate = self._compute_trend(df, indicator)

        return {
            "indicator": indicator,
            "indicator_label": INDICATOR_LABELS.get(indicator, indicator),
            "latest_year": self.latest_year,
            "ranking": ranking,
            "portugal_vs_eu_avg": gap,
            "portugal_rank": pt_rank,
            "trend": trend,
            "convergence_rate": convergence_rate,
        }

    def _compute_trend(
        self, df: pd.DataFrame, indicator: str, window: int = 5
    ) -> Tuple[str, float]:
        """Compute whether Portugal is converging or diverging from the EU average.

        Parameters
        ----------
        df : pd.DataFrame
            Filtered data for a single indicator.
        indicator : str
            The indicator name.
        window : int
            Number of recent years to consider.

        Returns
        -------
        tuple[str, float]
            Trend label ('converging' or 'diverging') and rate in pp/year.
        """
        recent_years = sorted(df["year"].unique())[-window:]

        pt_data = (
            df[(df["country_code"] == "PT") & (df["year"].isin(recent_years))]
            .sort_values("year")
            .set_index("year")["value"]
        )
        eu_data = (
            df[(df["country_code"] == "EU_AVG") & (df["year"].isin(recent_years))]
            .sort_values("year")
            .set_index("year")["value"]
        )

        common_years = pt_data.index.intersection(eu_data.index)
        if len(common_years) < 2:
            return "insufficient_data", 0.0

        gaps = (pt_data[common_years] - eu_data[common_years]).abs()
        # Linear regression slope of the absolute gap
        x = np.arange(len(gaps))
        slope = float(np.polyfit(x, gaps.values, 1)[0])
        rate = round(slope, 3)

        trend = "diverging" if slope > 0 else "converging"
        return trend, rate

    def generate_convergence_analysis(self) -> dict:
        """Analyse Portugal's convergence/divergence with EU across all indicators.

        Returns
        -------
        dict
            Dictionary with per-indicator convergence results and an
            overall assessment.
        """
        log_section(logger, "Convergence Analysis")
        results = {}
        converging_count = 0

        for indicator in INDICATORS:
            comparison = self.compare_indicator(indicator)
            trend = comparison["trend"]
            rate = comparison["convergence_rate"]
            results[indicator] = {
                "trend": trend,
                "convergence_rate": rate,
                "gap_pp": comparison["portugal_vs_eu_avg"],
            }
            if trend == "converging":
                converging_count += 1

        overall = (
            "broadly converging"
            if converging_count >= 3
            else "mixed signals" if converging_count >= 2 else "broadly diverging"
        )

        logger.info(
            f"Convergence summary: {converging_count}/{len(INDICATORS)} indicators "
            f"converging => {overall}"
        )

        return {
            "indicators": results,
            "converging_count": converging_count,
            "diverging_count": len(INDICATORS) - converging_count,
            "overall_assessment": overall,
        }

    def generate_peer_comparison_table(self) -> pd.DataFrame:
        """Create a wide table of latest-year values: rows=indicators, columns=countries.

        Returns
        -------
        pd.DataFrame
            Pivot table with indicator labels as rows and country codes as columns.
        """
        log_section(logger, "Peer Comparison Table")
        latest = self.data[self.data["year"] == self.latest_year].copy()

        pivot = latest.pivot_table(
            index="indicator",
            columns="country_code",
            values="value",
            aggfunc="first",
        )

        # Reorder columns and rows
        col_order = [c for c in ALL_ENTITIES if c in pivot.columns]
        row_order = [i for i in INDICATORS if i in pivot.index]
        pivot = pivot.loc[row_order, col_order]

        # Add readable labels
        pivot.index = [INDICATOR_LABELS.get(i, i) for i in pivot.index]
        pivot.index.name = "Indicator"

        logger.info(
            f"Peer comparison table: {pivot.shape[0]} indicators x {pivot.shape[1]} entities"
        )
        return pivot

    def generate_ranking_history(self, indicator: str) -> pd.DataFrame:
        """Track Portugal's rank among peer countries over time for an indicator.

        Parameters
        ----------
        indicator : str
            The benchmark indicator to rank.

        Returns
        -------
        pd.DataFrame
            DataFrame with columns: year, PT_value, PT_rank, total_peers.
        """
        logger.info(f"Generating ranking history for {indicator}")
        df = self.data[
            (self.data["indicator"] == indicator) & (self.data["country_code"].isin(PEER_COUNTRIES))
        ].copy()

        ascending = indicator in LOWER_IS_BETTER
        results = []

        for year in sorted(df["year"].unique()):
            year_data = df[df["year"] == year].sort_values("value", ascending=ascending)
            year_data["rank"] = range(1, len(year_data) + 1)
            pt_row = year_data[year_data["country_code"] == "PT"]
            if not pt_row.empty:
                results.append(
                    {
                        "year": year,
                        "PT_value": pt_row["value"].values[0],
                        "PT_rank": int(pt_row["rank"].values[0]),
                        "total_peers": len(year_data),
                    }
                )

        return pd.DataFrame(results)

    def generate_benchmark_report(self) -> dict:
        """Generate a complete benchmark analysis across all indicators.

        Returns
        -------
        dict
            Comprehensive report with summary, comparisons, convergence
            analysis, peer table, and key findings.
        """
        log_section(logger, "EU Benchmark Report")

        comparisons = {}
        for indicator in INDICATORS:
            comparisons[indicator] = self.compare_indicator(indicator)

        convergence = self.generate_convergence_analysis()
        peer_table = self.generate_peer_comparison_table()

        # Derive key findings
        key_findings = self._derive_key_findings(comparisons, convergence)

        # Build summary
        n_conv = convergence["converging_count"]
        n_div = convergence["diverging_count"]
        summary = (
            f"EU Benchmark Report ({self.latest_year}): "
            f"Portugal is {convergence['overall_assessment']} with EU averages. "
            f"{n_conv} of {len(INDICATORS)} indicators show convergence, "
            f"{n_div} show divergence."
        )

        logger.info(summary)

        return {
            "summary": summary,
            "comparisons": comparisons,
            "convergence": convergence,
            "peer_table": peer_table,
            "key_findings": key_findings,
        }

    def _derive_key_findings(self, comparisons: dict, convergence: dict) -> List[str]:
        """Extract key findings from the benchmark analysis.

        Parameters
        ----------
        comparisons : dict
            Per-indicator comparison results.
        convergence : dict
            Convergence analysis results.

        Returns
        -------
        list[str]
            List of human-readable key findings.
        """
        findings = []

        # Best and worst rankings
        best_rank = min(comparisons.values(), key=lambda x: x["portugal_rank"] or 99)
        worst_rank = max(comparisons.values(), key=lambda x: x["portugal_rank"] or 0)

        findings.append(
            f"Portugal ranks best among peers in {best_rank['indicator_label']} "
            f"(rank {best_rank['portugal_rank']} of {len(PEER_COUNTRIES)})."
        )
        findings.append(
            f"Portugal ranks worst among peers in {worst_rank['indicator_label']} "
            f"(rank {worst_rank['portugal_rank']} of {len(PEER_COUNTRIES)})."
        )

        # Largest gap to EU
        largest_gap = max(comparisons.values(), key=lambda x: abs(x["portugal_vs_eu_avg"]))
        gap_direction = "above" if largest_gap["portugal_vs_eu_avg"] > 0 else "below"
        findings.append(
            f"Largest gap to EU average: {largest_gap['indicator_label']} "
            f"({abs(largest_gap['portugal_vs_eu_avg']):.1f} pp {gap_direction})."
        )

        # Convergence highlights
        for indicator, info in convergence["indicators"].items():
            if info["trend"] == "converging" and abs(info["convergence_rate"]) > 0.5:
                label = INDICATOR_LABELS.get(indicator, indicator)
                findings.append(
                    f"Strong convergence in {label} "
                    f"(gap narrowing by {abs(info['convergence_rate']):.1f} pp/year)."
                )

        return findings


# =============================================================================
# Visualisation
# =============================================================================


def plot_benchmark_comparison(
    db_path: str,
    output_dir: Optional[str] = None,
) -> List[Path]:
    """Generate benchmark visualisation charts.

    Produces two charts:
        1. Radar/spider chart: Portugal vs EU average across all 5 indicators
           (normalised 0-100 scale).
        2. Small multiples: 5 line charts (one per indicator) showing PT vs
           DE, ES, FR, IT, EU_AVG over time.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.
    output_dir : str, optional
        Directory to save charts. Defaults to reports/powerbi/charts/.

    Returns
    -------
    list[Path]
        Paths to the saved chart files.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    log_section(logger, "Generating Benchmark Charts")

    # Resolve output directory
    if output_dir is None:
        charts_dir = POWERBI_DIR / "charts"
    else:
        charts_dir = Path(output_dir)
    charts_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    bench = EUBenchmark(db_path)
    df = bench.data
    saved_files = []

    # -------------------------------------------------------------------------
    # Chart 1: Radar / Spider chart — Portugal vs EU Average
    # -------------------------------------------------------------------------
    logger.info("Creating radar chart: Portugal vs EU Average")

    latest = df[df["year"] == bench.latest_year].copy()

    # Normalise each indicator to 0-100 scale across all entities
    normalised = {}
    for indicator in INDICATORS:
        ind_data = latest[latest["indicator"] == indicator]
        values = ind_data["value"].values
        vmin, vmax = values.min(), values.max()

        if vmax == vmin:
            normalised[indicator] = {row["country_code"]: 50.0 for _, row in ind_data.iterrows()}
        else:
            # For lower-is-better indicators, invert the scale
            if indicator in LOWER_IS_BETTER:
                normalised[indicator] = {
                    row["country_code"]: round(100 * (vmax - row["value"]) / (vmax - vmin), 1)
                    for _, row in ind_data.iterrows()
                }
            else:
                normalised[indicator] = {
                    row["country_code"]: round(100 * (row["value"] - vmin) / (vmax - vmin), 1)
                    for _, row in ind_data.iterrows()
                }

    # Prepare radar data
    labels = [INDICATOR_LABELS[i] for i in INDICATORS]
    pt_values = [normalised[i].get("PT", 0) for i in INDICATORS]
    eu_values = [normalised[i].get("EU_AVG", 0) for i in INDICATORS]

    # Close the polygon
    angles = np.linspace(0, 2 * np.pi, len(INDICATORS), endpoint=False).tolist()
    pt_values_closed = pt_values + [pt_values[0]]
    eu_values_closed = eu_values + [eu_values[0]]
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw={"projection": "polar"})
    fig.set_facecolor(CHART_BACKGROUND)
    ax.set_facecolor(CHART_BACKGROUND)
    ax.set_theta_offset(np.pi / 2)  # type: ignore[attr-defined]
    ax.set_theta_direction(-1)  # type: ignore[attr-defined]

    ax.plot(
        angles_closed,
        pt_values_closed,
        "o-",
        linewidth=2,
        label="Portugal",
        color=COUNTRY_COLORS["PT"],
    )
    ax.fill(angles_closed, pt_values_closed, alpha=0.15, color=COUNTRY_COLORS["PT"])
    ax.plot(
        angles_closed,
        eu_values_closed,
        "s--",
        linewidth=2,
        label="EU-27 Average",
        color=COUNTRY_COLORS["FR"],
    )
    ax.fill(angles_closed, eu_values_closed, alpha=0.10, color=COUNTRY_COLORS["FR"])

    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=CHART_FONT_SIZES["label"])
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=CHART_FONT_SIZES["tick"])
    ax.set_title(
        f"Portugal vs EU Average — Normalised Indicators ({bench.latest_year})",
        fontsize=CHART_FONT_SIZES["title"],
        fontweight="bold",
        pad=25,
    )
    ax.legend(loc="lower right", bbox_to_anchor=(1.15, -0.05), fontsize=CHART_FONT_SIZES["legend"])

    radar_path = charts_dir / "benchmark_radar_pt_vs_eu.png"
    fig.savefig(
        radar_path, dpi=CHART_DPI, bbox_inches="tight", facecolor=CHART_BACKGROUND, pad_inches=0.3
    )
    plt.close(fig)
    logger.info(f"Saved radar chart: {radar_path}")
    saved_files.append(radar_path)

    # -------------------------------------------------------------------------
    # Chart 2: Small multiples — 5 line charts (one per indicator)
    # -------------------------------------------------------------------------
    logger.info("Creating small multiples: indicator time series")

    plot_entities = ["PT", "DE", "ES", "FR", "IT", "EU_AVG"]
    colours = COUNTRY_COLORS
    line_styles = {
        "PT": "-",
        "DE": "-",
        "ES": "-",
        "FR": "-",
        "IT": "-",
        "EU_AVG": "--",
    }
    line_widths = {
        "PT": 2.5,
        "DE": 1.2,
        "ES": 1.2,
        "FR": 1.2,
        "IT": 1.2,
        "EU_AVG": 2.0,
    }

    fig, axes = plt.subplots(3, 2, figsize=(15, 16))
    fig.set_facecolor(CHART_BACKGROUND)
    axes_flat = axes.flatten()

    for idx, indicator in enumerate(INDICATORS):
        ax = axes_flat[idx]
        ax.set_facecolor(CHART_BACKGROUND)
        ind_data = df[df["indicator"] == indicator]

        for entity in plot_entities:
            entity_data = ind_data[ind_data["country_code"] == entity].sort_values("year")
            label = entity if entity != "EU_AVG" else "EU Avg"
            ax.plot(
                entity_data["year"],
                entity_data["value"],
                linestyle=line_styles[entity],
                color=colours[entity],
                linewidth=line_widths[entity],
                label=label,
                alpha=0.9 if entity in ("PT", "EU_AVG") else 0.6,
            )

        ax.set_title(
            INDICATOR_LABELS[indicator],
            fontsize=CHART_FONT_SIZES["label"],
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel("Year", fontsize=CHART_FONT_SIZES["tick"])
        ax.set_ylabel("%", fontsize=CHART_FONT_SIZES["tick"])
        ax.grid(True, alpha=CHART_GRID_ALPHA)
        ax.tick_params(labelsize=CHART_FONT_SIZES["tick"])

        if idx == 0:
            ax.legend(fontsize=CHART_FONT_SIZES["legend"], loc="best", ncol=2)

    # Hide the 6th subplot (only 5 indicators)
    axes_flat[5].set_visible(False)

    fig.suptitle(
        f"Portugal vs EU Peers — Macroeconomic Indicators (2010-{bench.latest_year})",
        fontsize=CHART_FONT_SIZES["suptitle"],
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout(pad=2.5, h_pad=3.5, w_pad=3.0)

    multiples_path = charts_dir / "benchmark_small_multiples.png"
    fig.savefig(
        multiples_path,
        dpi=CHART_DPI,
        bbox_inches="tight",
        facecolor=CHART_BACKGROUND,
        pad_inches=0.3,
    )
    plt.close(fig)
    logger.info(f"Saved small multiples chart: {multiples_path}")
    saved_files.append(multiples_path)

    log_section(logger, "Charts Complete")
    return saved_files


# =============================================================================
# Main entry point
# =============================================================================

if __name__ == "__main__":
    ensure_directories()

    db_path = str(DATABASE_PATH)

    # Run benchmark analysis
    log_section(logger, "EU Benchmarking Analysis")
    bench = EUBenchmark(db_path)
    report = bench.generate_benchmark_report()

    # Print summary
    print("\n" + "=" * 70)
    print("  EU BENCHMARK REPORT")
    print("=" * 70)
    print(f"\n{report['summary']}\n")

    # Print peer comparison table
    print("\nPeer Comparison Table (Latest Year):")
    print("-" * 70)
    print(report["peer_table"].to_string())
    print()

    # Print key findings
    print("\nKey Findings:")
    print("-" * 70)
    for i, finding in enumerate(report["key_findings"], 1):
        print(f"  {i}. {finding}")
    print()

    # Print convergence analysis
    print("\nConvergence Analysis:")
    print("-" * 70)
    convergence = report["convergence"]
    for indicator, info in convergence["indicators"].items():
        label = INDICATOR_LABELS.get(indicator, indicator)
        arrow = "<-" if info["trend"] == "converging" else "->"
        print(
            f"  {label:30s}  {arrow}  {info['trend']:12s}  "
            f"(gap: {info['gap_pp']:+.1f} pp, rate: {info['convergence_rate']:.3f} pp/yr)"
        )
    print(f"\n  Overall: {convergence['overall_assessment']}")
    print()

    # Print ranking history for each indicator
    print("\nPortugal Ranking History (among 5 peers):")
    print("-" * 70)
    for indicator in INDICATORS:
        history = bench.generate_ranking_history(indicator)
        label = INDICATOR_LABELS.get(indicator, indicator)
        ranks = history["PT_rank"].tolist()
        rank_str = " ".join(f"{r}" for r in ranks)
        print(f"  {label:30s}  Ranks: {rank_str}")
    print()

    # Generate charts
    saved = plot_benchmark_comparison(db_path)
    print(f"\nCharts saved: {len(saved)} files")
    for path in saved:
        print(f"  - {path}")
