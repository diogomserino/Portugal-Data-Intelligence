"""
Portugal Data Intelligence - Visualisation Module
====================================================
Publication-quality chart generation for all six economic pillars.

Generates PNG charts (150 DPI) saved to reports/powerbi/charts/.
Uses a consistent professional style with colour-coded economic periods.

Usage:
    python -m src.analysis.visualisations
    python src/analysis/visualisations.py
"""

import sqlite3
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

# =============================================================================
# PROJECT PATHS
# =============================================================================

try:
    from config.settings import DATABASE_PATH as _DB_PATH
    from config.settings import POWERBI_DIR

    CHARTS_DIR = POWERBI_DIR / "charts"
    DEFAULT_DB = _DB_PATH
    PROJECT_ROOT = POWERBI_DIR.parent.parent
except ImportError:
    _THIS_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = _THIS_DIR.parent.parent
    CHARTS_DIR = PROJECT_ROOT / "reports" / "powerbi" / "charts"
    DEFAULT_DB = PROJECT_ROOT / "data" / "database" / "portugal_data_intelligence.db"

CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# DESIGN SYSTEM (imported from shared_styles)
# =============================================================================

import sys as _sys

if str(PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.shared_styles import (
    CHART_ACCENT,
    CHART_BACKGROUND,
)
from src.reporting.shared_styles import CHART_COLORS as COLORS
from src.reporting.shared_styles import (
    CHART_DARK_TEXT,
    CHART_DPI,
    CHART_FILL_ALPHA,
    CHART_FONT_SIZES,
    CHART_GRID,
    CHART_GRID_ALPHA,
    CHART_LEGEND_FRAMEALPHA,
    CHART_LIGHT_TEXT,
    CHART_NEGATIVE,
    CHART_NEUTRAL,
    CHART_PERIOD_ALPHA,
    CHART_PERIOD_LEGEND_ALPHA,
    CHART_POSITIVE,
    CHART_PRIMARY,
    CHART_PURPLE,
    CHART_SECONDARY,
    PERIOD_COLORS,
    ZONE_CAUTION,
    ZONE_THRESHOLD,
    apply_chart_style,
)

try:
    from config.settings import CHART_PERIODS as PERIODS
except ImportError:
    PERIODS = {
        "Pre-crisis": ("2010", "2011"),
        "Troika": ("2012", "2014"),
        "Recovery": ("2015", "2019"),
        "COVID": ("2020", "2020"),
        "Post-COVID": ("2021", "2025"),
    }

SOURCE_TEXT = "Source: Portugal Data Intelligence | Synthetic data based on INE, BdP, Eurostat"

# =============================================================================
# GLOBAL STYLE CONFIGURATION
# =============================================================================

apply_chart_style()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _connect(db_path=None):
    """Return a sqlite3 connection to the project database."""
    path = db_path or str(DEFAULT_DB)
    return sqlite3.connect(str(path))


def _add_source_text(fig, y=-0.02):
    """Add the standard source attribution to the bottom of a figure."""
    fig.text(
        0.5,
        y,
        SOURCE_TEXT,
        ha="center",
        va="top",
        fontsize=CHART_FONT_SIZES["source"],
        color=CHART_LIGHT_TEXT,
        style="italic",
    )


def _shade_periods(ax, date_series, periods=None, period_colors=None):
    """Shade economic periods on a matplotlib axes using datetime x-axis.

    NOTE: Call this AFTER plotting data so that ylim is auto-scaled correctly.
    The axvspan uses zorder=0 so shading always appears behind data lines.
    """
    periods = periods or PERIODS
    period_colors = period_colors or PERIOD_COLORS
    for label, (start, end) in periods.items():
        try:
            p_start = pd.Timestamp(f"{start}-01-01")
            p_end = pd.Timestamp(f"{end}-12-31")
            d_min = date_series.min()
            d_max = date_series.max()
            p_start = max(p_start, d_min)
            p_end = min(p_end, d_max)
            if p_start < p_end:
                ax.axvspan(
                    p_start,
                    p_end,
                    alpha=CHART_PERIOD_ALPHA,
                    color=period_colors.get(label, "#EEEEEE"),
                    zorder=0,
                )
        except Exception:
            continue


def _shade_periods_quarterly(ax, date_series):
    """Shade economic periods for quarterly date series."""
    _shade_periods(ax, date_series)


def _period_legend(ax, loc="upper right"):
    """Add a separate legend for economic period bands below the chart."""
    handles = []
    for label, colour in PERIOD_COLORS.items():
        handles.append(
            mpatches.Patch(facecolor=colour, alpha=CHART_PERIOD_LEGEND_ALPHA, label=label)
        )
    legend2 = ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.10),
        fontsize=CHART_FONT_SIZES["small"],
        title="Economic Periods",
        title_fontsize=CHART_FONT_SIZES["small"],
        frameon=False,
        ncol=len(PERIOD_COLORS),
    )
    ax.add_artist(legend2)


def _parse_quarter_date(date_key_series):
    """Convert '2010-Q1' strings to Timestamps (first day of quarter)."""

    def _convert(v):
        parts = str(v).split("-Q")
        year = int(parts[0])
        quarter = int(parts[1])
        month = (quarter - 1) * 3 + 1
        return pd.Timestamp(year=year, month=month, day=1)

    return date_key_series.apply(_convert)


def _parse_month_date(date_key_series):
    """Convert '2010-01' strings to Timestamps."""
    return pd.to_datetime(date_key_series, format="%Y-%m")


def _setup_fig(fig):
    """Apply the standard background colour to a figure."""
    fig.set_facecolor(CHART_BACKGROUND)
    for ax in fig.get_axes():
        ax.set_facecolor(CHART_BACKGROUND)


def _savefig(fig, filename):
    """Save figure and return the output path."""
    out_path = CHARTS_DIR / filename
    fig.savefig(
        str(out_path),
        dpi=CHART_DPI,
        bbox_inches="tight",
        facecolor=CHART_BACKGROUND,
        pad_inches=0.3,
    )
    plt.close(fig)
    return str(out_path)


# =============================================================================
# 1. GDP EVOLUTION
# =============================================================================


def plot_gdp_evolution(db_path=None):
    """
    Dual-axis chart: nominal GDP bars + YoY growth rate line.
    Economic periods are shaded in the background.
    """
    conn = _connect(db_path)
    df = pd.read_sql(
        "SELECT date_key, nominal_gdp, gdp_growth_yoy FROM fact_gdp ORDER BY date_key", conn
    )
    conn.close()

    df["date"] = _parse_quarter_date(df["date_key"])
    df = df.sort_values("date").reset_index(drop=True)

    # Annualise: sum nominal GDP per year, average growth
    annual = (
        df.groupby(df["date"].dt.year)
        .agg(
            nominal_gdp=("nominal_gdp", "sum"),
            gdp_growth=("gdp_growth_yoy", "mean"),
        )
        .reset_index()
    )
    annual.columns = ["year", "nominal_gdp", "gdp_growth"]
    annual["date"] = pd.to_datetime(annual["year"], format="%Y")

    fig, ax1 = plt.subplots(figsize=(14, 7))
    _setup_fig(fig)

    # Bars for nominal GDP (subtle, supporting role)
    bar_width = pd.Timedelta(days=200)
    bars = ax1.bar(
        annual["date"],
        annual["nominal_gdp"] / 1e3,
        width=bar_width,
        color=COLORS["secondary"],
        alpha=0.35,
        label="Nominal GDP (EUR bn)",
        zorder=2,
    )
    ax1.set_ylabel("Nominal GDP (EUR billions)")
    ax1.set_xlabel("")

    # Growth line on secondary axis (the key decision metric)
    ax2 = ax1.twinx()
    valid = annual.dropna(subset=["gdp_growth"])
    ax2.plot(
        valid["date"],
        valid["gdp_growth"],
        color=COLORS["primary"],
        linewidth=2.8,
        marker="o",
        markersize=6,
        label="YoY Growth (%)",
        zorder=5,
    )
    ax2.axhline(0, color=COLORS["neutral"], linewidth=0.8, linestyle="--")
    ax2.set_ylabel("YoY Growth Rate (%)", color=COLORS["primary"])
    ax2.tick_params(axis="y", labelcolor=COLORS["primary"])

    # Shade periods (after data for correct ylim)
    _shade_periods(ax1, annual["date"])

    # Combined legend below chart
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(
        lines1 + lines2,
        labels1 + labels2,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.06),
        frameon=False,
        ncol=3,
    )

    _period_legend(ax1)

    ax1.set_title("Portugal GDP Evolution (2010-2025)", pad=20)
    fig.tight_layout(pad=2.0)
    fig.subplots_adjust(bottom=0.18)
    _add_source_text(fig, y=-0.01)

    return _savefig(fig, "gdp_evolution.png")


# =============================================================================
# 2. UNEMPLOYMENT TRENDS
# =============================================================================


def plot_unemployment_trends(db_path=None):
    """
    Multi-line: general, youth, long-term unemployment with 12-month
    moving average (dashed) and crisis period shading.
    """
    conn = _connect(db_path)
    df = pd.read_sql(
        "SELECT date_key, unemployment_rate, youth_unemployment_rate, "
        "long_term_unemployment_rate FROM fact_unemployment ORDER BY date_key",
        conn,
    )
    conn.close()

    df["date"] = _parse_month_date(df["date_key"])
    df = df.sort_values("date").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(14, 7))
    _setup_fig(fig)

    # Main lines (plot BEFORE shading so ylim is auto-scaled)
    ax.plot(
        df["date"],
        df["unemployment_rate"],
        color=COLORS["primary"],
        linewidth=2.5,
        label="General Unemployment",
        zorder=3,
    )
    ax.plot(
        df["date"],
        df["youth_unemployment_rate"],
        color=COLORS["accent"],
        linewidth=2.5,
        label="Youth Unemployment (< 25)",
        zorder=3,
    )
    ax.plot(
        df["date"],
        df["long_term_unemployment_rate"],
        color=COLORS["positive"],
        linewidth=2,
        label="Long-term Unemployment",
        zorder=3,
    )

    # 12-month moving averages
    for col, color in [
        ("unemployment_rate", COLORS["primary"]),
        ("youth_unemployment_rate", COLORS["accent"]),
        ("long_term_unemployment_rate", COLORS["positive"]),
    ]:
        ma = df[col].rolling(12, min_periods=6).mean()
        ax.plot(df["date"], ma, color=color, linewidth=1.2, linestyle="--", alpha=0.5, zorder=2)

    # Dashed-line legend entry
    ax.plot(
        [], [], color=COLORS["neutral"], linewidth=1.2, linestyle="--", label="12-month Moving Avg."
    )

    # Period shading (after data so ylim is correct)
    _shade_periods(ax, df["date"])

    ax.set_ylabel("Rate (%)")
    ax.set_xlabel("")
    ax.set_title("Portugal Unemployment Trends (2010-2025)", pad=20)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), frameon=False, ncol=4)
    _period_legend(ax)

    fig.tight_layout(pad=2.0)
    fig.subplots_adjust(bottom=0.18)
    _add_source_text(fig, y=-0.01)

    return _savefig(fig, "unemployment_trends.png")


# =============================================================================
# 3. CREDIT PORTFOLIO
# =============================================================================


def plot_credit_portfolio(db_path=None):
    """
    Top panel: stacked area chart of NFC vs household credit.
    Bottom panel: NPL ratio line chart with danger zone (>10%) shading.
    """
    conn = _connect(db_path)
    df = pd.read_sql(
        "SELECT date_key, credit_nfc, credit_households, npl_ratio "
        "FROM fact_credit ORDER BY date_key",
        conn,
    )
    conn.close()

    df["date"] = _parse_month_date(df["date_key"])
    df = df.sort_values("date").reset_index(drop=True)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[3, 2], sharex=True)
    _setup_fig(fig)

    # --- Panel 1: Stacked area ---
    ax1.fill_between(
        df["date"],
        0,
        df["credit_nfc"] / 1e3,
        color=COLORS["primary"],
        alpha=0.6,
        label="NFC Credit",
    )
    ax1.fill_between(
        df["date"],
        df["credit_nfc"] / 1e3,
        (df["credit_nfc"] + df["credit_households"]) / 1e3,
        color=COLORS["secondary"],
        alpha=0.6,
        label="Household Credit",
    )
    ax1.set_ylabel("Credit Outstanding (EUR billions)")
    ax1.set_title("Portugal Credit Portfolio & Asset Quality (2010-2025)", pad=20)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.04), frameon=False, ncol=2)
    _shade_periods(ax1, df["date"])

    # --- Panel 2: NPL ratio ---
    ax2.plot(df["date"], df["npl_ratio"], color=COLORS["negative"], linewidth=2, label="NPL Ratio")
    ax2.axhline(10, color=COLORS["negative"], linewidth=0.8, linestyle="--", alpha=0.5)
    ax2.fill_between(
        df["date"],
        10,
        df["npl_ratio"].clip(lower=10),
        where=df["npl_ratio"] >= 10,
        color=COLORS["negative"],
        alpha=0.15,
        label="Danger Zone (>10%)",
    )
    ax2.fill_between(
        df["date"],
        5,
        10,
        color=ZONE_CAUTION,
        alpha=CHART_PERIOD_ALPHA,
        label="Caution Zone (5-10%)",
    )
    ax2.axhline(5, color=ZONE_THRESHOLD, linewidth=0.8, linestyle=":", alpha=0.5)
    ax2.set_ylabel("NPL Ratio (%)")
    ax2.set_xlabel("")
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), frameon=False, ncol=3)
    _shade_periods(ax2, df["date"])

    fig.tight_layout(pad=2.0, h_pad=3.0)
    fig.subplots_adjust(bottom=0.12)
    _add_source_text(fig, y=-0.03)

    return _savefig(fig, "credit_portfolio.png")


# =============================================================================
# 4. INTEREST RATE ENVIRONMENT
# =============================================================================


def plot_interest_rate_environment(db_path=None):
    """
    Multi-line: ECB rate, Euribor 3M, PT 10Y bond yield.
    Sovereign spread highlighted as shaded area between ECB rate and bond yield.
    """
    conn = _connect(db_path)
    df = pd.read_sql(
        "SELECT date_key, ecb_main_refinancing_rate, euribor_3m, "
        "portugal_10y_bond_yield FROM fact_interest_rates ORDER BY date_key",
        conn,
    )
    conn.close()

    df["date"] = _parse_month_date(df["date_key"])
    df = df.sort_values("date").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(14, 7))
    _setup_fig(fig)

    # Sovereign spread shading
    ax.fill_between(
        df["date"],
        df["ecb_main_refinancing_rate"],
        df["portugal_10y_bond_yield"],
        alpha=0.12,
        color=COLORS["accent"],
        label="Sovereign Spread",
    )

    ax.plot(
        df["date"],
        df["ecb_main_refinancing_rate"],
        color=COLORS["primary"],
        linewidth=2,
        label="ECB Main Refinancing Rate",
    )
    ax.plot(
        df["date"], df["euribor_3m"], color=COLORS["secondary"], linewidth=1.8, label="Euribor 3M"
    )
    ax.plot(
        df["date"],
        df["portugal_10y_bond_yield"],
        color=COLORS["accent"],
        linewidth=2,
        label="PT 10Y Bond Yield",
    )

    _shade_periods(ax, df["date"])

    ax.set_ylabel("Rate (%)")
    ax.set_xlabel("")
    ax.set_title("Interest Rate Environment (2010-2025)", pad=20)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), frameon=False, ncol=4)
    _period_legend(ax)

    fig.tight_layout(pad=2.0)
    fig.subplots_adjust(bottom=0.18)
    _add_source_text(fig, y=-0.01)

    return _savefig(fig, "interest_rate_environment.png")


# =============================================================================
# 5. INFLATION DASHBOARD
# =============================================================================


def plot_inflation_dashboard(db_path=None):
    """
    Panel 1: HICP vs core inflation lines with ECB 2% target.
    Panel 2: Annual average inflation bar chart.
    """
    conn = _connect(db_path)
    df = pd.read_sql(
        "SELECT date_key, hicp, core_inflation FROM fact_inflation ORDER BY date_key", conn
    )
    conn.close()

    df["date"] = _parse_month_date(df["date_key"])
    df = df.sort_values("date").reset_index(drop=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [3, 2]})
    _setup_fig(fig)

    # --- Panel 1: Monthly lines ---
    ax1.plot(df["date"], df["hicp"], color=COLORS["primary"], linewidth=1.8, label="HICP")
    ax1.plot(
        df["date"],
        df["core_inflation"],
        color=COLORS["secondary"],
        linewidth=1.8,
        label="Core Inflation",
    )
    ax1.axhline(
        2.0,
        color=COLORS["accent"],
        linewidth=1.2,
        linestyle="--",
        alpha=0.7,
        label="ECB Target (2%)",
    )
    ax1.axhline(0, color=COLORS["neutral"], linewidth=0.6, linestyle="-")
    _shade_periods(ax1, df["date"])
    ax1.set_ylabel("Rate (%)")
    ax1.set_title("Monthly Inflation (HICP & Core)", pad=10)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False, ncol=3)

    # --- Panel 2: Annual bar chart ---
    annual = df.groupby(df["date"].dt.year)["hicp"].mean().reset_index()
    annual.columns = ["year", "avg_hicp"]
    bar_colors = [
        COLORS["negative"] if v > 2 else (COLORS["positive"] if v >= 0 else COLORS["secondary"])
        for v in annual["avg_hicp"]
    ]
    ax2.bar(annual["year"], annual["avg_hicp"], color=bar_colors, alpha=0.8)
    ax2.axhline(2.0, color=COLORS["accent"], linewidth=1.2, linestyle="--", alpha=0.7)
    ax2.axhline(0, color=COLORS["neutral"], linewidth=0.6)
    ax2.set_ylabel("Average HICP (%)")
    ax2.set_xlabel("")
    ax2.set_title("Annual Average Inflation", pad=10)
    ax2.set_xticks(annual["year"])
    ax2.set_xticklabels(annual["year"].astype(int), rotation=45, ha="right")

    fig.suptitle(
        "Portugal Inflation Dashboard (2010-2025)",
        fontsize=CHART_FONT_SIZES["suptitle"],
        fontweight="bold",
        y=1.03,
    )
    fig.tight_layout(pad=2.0, w_pad=4.0)
    _add_source_text(fig, y=-0.05)

    return _savefig(fig, "inflation_dashboard.png")


# =============================================================================
# 6. PUBLIC DEBT SUSTAINABILITY
# =============================================================================


def plot_public_debt_sustainability(db_path=None):
    """
    Dual axis: debt-to-GDP ratio line + budget balance bars.
    Traffic-light zones: green (<60%), yellow (60-90%), red (>90%).
    """
    conn = _connect(db_path)
    df = pd.read_sql(
        "SELECT date_key, debt_to_gdp_ratio, budget_deficit "
        "FROM fact_public_debt ORDER BY date_key",
        conn,
    )
    conn.close()

    df["date"] = _parse_quarter_date(df["date_key"])
    df = df.sort_values("date").reset_index(drop=True)

    fig, ax1 = plt.subplots(figsize=(14, 7))
    _setup_fig(fig)

    # Traffic-light zones
    ymax = max(df["debt_to_gdp_ratio"].max() * 1.1, 150)
    ax1.axhspan(0, 60, color=COLORS["positive"], alpha=0.07, zorder=0)
    ax1.axhspan(60, 90, color=ZONE_CAUTION, alpha=CHART_PERIOD_ALPHA, zorder=0)
    ax1.axhspan(90, ymax, color=COLORS["negative"], alpha=0.07, zorder=0)
    ax1.axhline(60, color=COLORS["positive"], linewidth=0.8, linestyle=":", alpha=0.6)
    ax1.axhline(90, color=COLORS["negative"], linewidth=0.8, linestyle=":", alpha=0.6)

    # Debt-to-GDP line
    ax1.plot(
        df["date"],
        df["debt_to_gdp_ratio"],
        color=COLORS["primary"],
        linewidth=2.5,
        label="Debt-to-GDP Ratio (%)",
        zorder=4,
    )
    ax1.set_ylabel("Debt-to-GDP Ratio (%)", color=COLORS["primary"])
    ax1.set_ylim(0, ymax)
    ax1.tick_params(axis="y", labelcolor=COLORS["primary"])

    # Budget balance bars on secondary axis
    ax2 = ax1.twinx()
    bar_colors = [
        COLORS["positive"] if v >= 0 else COLORS["negative"] for v in df["budget_deficit"]
    ]
    bar_width = pd.Timedelta(days=60)
    ax2.bar(
        df["date"],
        df["budget_deficit"],
        width=bar_width,
        color=bar_colors,
        alpha=0.5,
        label="Budget Balance (% GDP)",
        zorder=3,
    )
    ax2.axhline(0, color=COLORS["dark_text"], linewidth=0.6)
    ax2.set_ylabel("Budget Balance (% of GDP)", color=COLORS["negative"])
    ax2.tick_params(axis="y", labelcolor=COLORS["negative"])

    # Traffic-light legend
    traffic_handles = [
        mpatches.Patch(facecolor=COLORS["positive"], alpha=0.2, label="Sustainable (<60%)"),
        mpatches.Patch(facecolor=ZONE_CAUTION, alpha=0.4, label="Caution (60-90%)"),
        mpatches.Patch(facecolor=COLORS["negative"], alpha=0.2, label="High Risk (>90%)"),
    ]
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(
        handles=lines1 + lines2 + traffic_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.06),
        frameon=False,
        ncol=3,
        fontsize=CHART_FONT_SIZES["annotation"],
    )

    ax1.set_title("Public Debt Sustainability (2010-2025)", pad=20)
    ax1.set_xlabel("")

    fig.tight_layout(pad=2.0)
    fig.subplots_adjust(bottom=0.15)
    _add_source_text(fig, y=-0.01)

    return _savefig(fig, "public_debt_sustainability.png")


# =============================================================================
# 7. CORRELATION HEATMAP
# =============================================================================


def plot_correlation_heatmap(db_path=None):
    """
    Correlation matrix heatmap of all monthly indicators.
    Diverging colour map (red-white-blue) with annotated cells.
    """
    conn = _connect(db_path)

    unemp = pd.read_sql(
        "SELECT date_key, unemployment_rate FROM fact_unemployment ORDER BY date_key", conn
    )
    credit = pd.read_sql(
        "SELECT date_key, total_credit, npl_ratio FROM fact_credit ORDER BY date_key", conn
    )
    rates = pd.read_sql(
        "SELECT date_key, ecb_main_refinancing_rate, euribor_3m, "
        "portugal_10y_bond_yield FROM fact_interest_rates ORDER BY date_key",
        conn,
    )
    infl = pd.read_sql(
        "SELECT date_key, hicp, core_inflation FROM fact_inflation ORDER BY date_key", conn
    )
    conn.close()

    # Merge on monthly date_key
    merged = unemp.merge(credit, on="date_key", how="inner")
    merged = merged.merge(rates, on="date_key", how="inner")
    merged = merged.merge(infl, on="date_key", how="inner")

    # Rename for readability
    rename_map = {
        "unemployment_rate": "Unemployment",
        "total_credit": "Total Credit",
        "npl_ratio": "NPL Ratio",
        "ecb_main_refinancing_rate": "ECB Rate",
        "euribor_3m": "Euribor 3M",
        "portugal_10y_bond_yield": "PT 10Y Yield",
        "hicp": "HICP",
        "core_inflation": "Core Inflation",
    }
    numeric_cols = list(rename_map.keys())
    corr_df = merged[numeric_cols].rename(columns=rename_map)
    corr_matrix = corr_df.corr()

    fig, ax = plt.subplots(figsize=(10, 9))
    _setup_fig(fig)

    mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
    cmap = sns.diverging_palette(240, 10, as_cmap=True)

    sns.heatmap(
        corr_matrix,
        mask=mask,
        cmap=cmap,
        center=0,
        annot=True,
        fmt=".2f",
        linewidths=0.5,
        square=True,
        ax=ax,
        cbar_kws={"shrink": 0.8, "label": "Correlation"},
        vmin=-1,
        vmax=1,
        annot_kws={"size": CHART_FONT_SIZES["annotation"]},
    )

    ax.set_title("Correlation Matrix of Monthly Economic Indicators", pad=20)
    fig.tight_layout(pad=2.0)
    _add_source_text(fig, y=-0.03)

    return _savefig(fig, "correlation_heatmap.png")


# =============================================================================
# 8. ECONOMIC DASHBOARD (Executive Summary)
# =============================================================================


def plot_economic_dashboard(db_path=None):
    """
    2x3 grid of sparkline mini-charts for all six pillars.
    Each cell shows the indicator sparkline, latest value, and trend arrow.
    """
    conn = _connect(db_path)

    # Load latest data for each pillar
    gdp = pd.read_sql(
        "SELECT date_key, nominal_gdp, gdp_growth_yoy FROM fact_gdp ORDER BY date_key", conn
    )
    unemp = pd.read_sql(
        "SELECT date_key, unemployment_rate FROM fact_unemployment ORDER BY date_key", conn
    )
    credit = pd.read_sql(
        "SELECT date_key, total_credit, npl_ratio FROM fact_credit ORDER BY date_key", conn
    )
    rates = pd.read_sql(
        "SELECT date_key, portugal_10y_bond_yield FROM fact_interest_rates ORDER BY date_key", conn
    )
    infl = pd.read_sql("SELECT date_key, hicp FROM fact_inflation ORDER BY date_key", conn)
    debt = pd.read_sql(
        "SELECT date_key, debt_to_gdp_ratio FROM fact_public_debt ORDER BY date_key", conn
    )
    conn.close()

    # Parse dates
    gdp["date"] = _parse_quarter_date(gdp["date_key"])
    unemp["date"] = _parse_month_date(unemp["date_key"])
    credit["date"] = _parse_month_date(credit["date_key"])
    rates["date"] = _parse_month_date(rates["date_key"])
    infl["date"] = _parse_month_date(infl["date_key"])
    debt["date"] = _parse_quarter_date(debt["date_key"])

    panels = [
        ("GDP (EUR bn)", gdp["date"], gdp["nominal_gdp"] / 1e3, COLORS["primary"], "EUR bn"),
        ("Unemployment Rate", unemp["date"], unemp["unemployment_rate"], COLORS["accent"], "%"),
        (
            "Total Credit (EUR bn)",
            credit["date"],
            credit["total_credit"] / 1e3,
            COLORS["secondary"],
            "EUR bn",
        ),
        (
            "PT 10Y Bond Yield",
            rates["date"],
            rates["portugal_10y_bond_yield"],
            COLORS["primary"],
            "%",
        ),
        ("HICP Inflation", infl["date"], infl["hicp"], COLORS["accent"], "%"),
        ("Debt-to-GDP Ratio", debt["date"], debt["debt_to_gdp_ratio"], COLORS["primary"], "%"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    _setup_fig(fig)
    axes = axes.flatten()

    for idx, (title, dates, values, color, unit) in enumerate(panels):
        ax = axes[idx]
        values_clean = values.dropna()
        dates_clean = dates.loc[values_clean.index]

        ax.plot(dates_clean, values_clean, color=color, linewidth=1.5)
        ax.fill_between(dates_clean, values_clean.min(), values_clean, alpha=0.08, color=color)
        ax.set_title(title, fontsize=CHART_FONT_SIZES["label"], fontweight="bold", pad=8)

        # Latest value and trend
        if values_clean.empty:
            continue
        latest = values_clean.iloc[-1]
        prev = values_clean.iloc[-13] if len(values_clean) > 13 else values_clean.iloc[0]
        change = latest - prev
        arrow = "\u2191" if change > 0 else ("\u2193" if change < 0 else "\u2192")
        # For GDP and credit, up is good; for unemployment and debt, down is good
        if title in ("Unemployment Rate", "Debt-to-GDP Ratio", "PT 10Y Bond Yield"):
            arrow_color = COLORS["positive"] if change < 0 else COLORS["negative"]
        elif title in ("GDP (EUR bn)", "Total Credit (EUR bn)"):
            arrow_color = COLORS["positive"] if change > 0 else COLORS["negative"]
        else:
            arrow_color = COLORS["neutral"]

        ax.text(
            0.98,
            0.95,
            f"{latest:.1f} {unit} {arrow}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=CHART_FONT_SIZES["axis_label"],
            fontweight="bold",
            color=arrow_color,
        )

        # Minimalist style
        ax.tick_params(axis="both", labelsize=CHART_FONT_SIZES["small"])
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle(
        "Portugal Economic Dashboard - Executive Summary",
        fontsize=CHART_FONT_SIZES["suptitle"],
        fontweight="bold",
        y=1.03,
    )
    fig.tight_layout(pad=2.5, h_pad=3.5, w_pad=3.0)
    _add_source_text(fig, y=-0.04)

    return _savefig(fig, "economic_dashboard.png")


# =============================================================================
# 9. PHILLIPS CURVE
# =============================================================================


def plot_phillips_curve(db_path=None):
    """
    Scatter plot: unemployment (x) vs inflation (y), coloured by year.
    Includes a regression line.
    """
    conn = _connect(db_path)
    unemp = pd.read_sql(
        "SELECT date_key, unemployment_rate FROM fact_unemployment ORDER BY date_key", conn
    )
    infl = pd.read_sql("SELECT date_key, hicp FROM fact_inflation ORDER BY date_key", conn)
    conn.close()

    merged = unemp.merge(infl, on="date_key", how="inner")
    merged["date"] = _parse_month_date(merged["date_key"])
    merged["year"] = merged["date"].dt.year

    fig, ax = plt.subplots(figsize=(10, 9))
    _setup_fig(fig)

    years = sorted(merged["year"].unique())
    cmap = plt.cm.viridis
    norm = plt.Normalize(vmin=min(years), vmax=max(years))

    scatter = ax.scatter(
        merged["unemployment_rate"],
        merged["hicp"],
        c=merged["year"],
        cmap=cmap,
        norm=norm,
        s=30,
        alpha=0.7,
        edgecolors="white",
        linewidths=0.3,
        zorder=4,
    )

    # Regression line
    mask = merged[["unemployment_rate", "hicp"]].dropna()
    if len(mask) > 2:
        from scipy import stats as _stats

        z = np.polyfit(mask["unemployment_rate"], mask["hicp"], 1)
        p = np.poly1d(z)
        x_line = np.linspace(mask["unemployment_rate"].min(), mask["unemployment_rate"].max(), 100)
        ax.plot(
            x_line,
            p(x_line),
            color=COLORS["accent"],
            linewidth=2,
            linestyle="--",
            label=f"Linear fit (slope={z[0]:.2f})",
            zorder=5,
        )

        # 95% confidence band (prediction interval)
        n = len(mask)
        x_vals = mask["unemployment_rate"].values
        y_vals = mask["hicp"].values
        y_hat = p(x_vals)
        residuals = y_vals - y_hat
        se = np.sqrt(np.sum(residuals**2) / (n - 2))
        x_mean = np.mean(x_vals)
        ss_x = np.sum((x_vals - x_mean) ** 2)
        t_crit = _stats.t.ppf(0.975, df=n - 2)
        ci_half = t_crit * se * np.sqrt(1 / n + (x_line - x_mean) ** 2 / ss_x)
        y_line = p(x_line)
        ax.fill_between(
            x_line,
            y_line - ci_half,
            y_line + ci_half,
            alpha=0.15,
            color=COLORS["accent"],
            label="95% Prediction Interval",
        )

    # Year labels for extremes
    for year in [2010, 2013, 2015, 2020, 2022, 2025]:
        yr_data = merged[merged["year"] == year]
        if len(yr_data) > 0:
            mean_x = yr_data["unemployment_rate"].mean()
            mean_y = yr_data["hicp"].mean()
            ax.annotate(
                str(year),
                (mean_x, mean_y),
                fontsize=CHART_FONT_SIZES["annotation"],
                fontweight="bold",
                color=CHART_DARK_TEXT,
                xytext=(5, 5),
                textcoords="offset points",
            )

    cbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    cbar.set_label("Year", fontsize=CHART_FONT_SIZES["legend"])

    ax.set_xlabel("Unemployment Rate (%)", fontsize=CHART_FONT_SIZES["axis_label"])
    ax.set_ylabel("HICP Inflation (%)", fontsize=CHART_FONT_SIZES["axis_label"])
    ax.set_title("Phillips Curve: Portugal (2010-2025)", pad=20)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False, ncol=3)

    fig.tight_layout(pad=2.0)
    fig.subplots_adjust(bottom=0.15)
    _add_source_text(fig, y=-0.01)

    return _savefig(fig, "phillips_curve.png")


# =============================================================================
# 10. CRISIS TIMELINE
# =============================================================================


def plot_crisis_timeline(db_path=None):
    """
    Normalised (0-100 scale) multi-line chart showing how all indicators
    moved during key events: 2012 crisis, COVID, inflation shock.
    """
    conn = _connect(db_path)
    unemp = pd.read_sql(
        "SELECT date_key, unemployment_rate FROM fact_unemployment ORDER BY date_key", conn
    )
    credit = pd.read_sql("SELECT date_key, npl_ratio FROM fact_credit ORDER BY date_key", conn)
    rates = pd.read_sql(
        "SELECT date_key, portugal_10y_bond_yield FROM fact_interest_rates ORDER BY date_key", conn
    )
    infl = pd.read_sql("SELECT date_key, hicp FROM fact_inflation ORDER BY date_key", conn)
    conn.close()

    # Merge all monthly
    merged = unemp.merge(credit, on="date_key", how="inner")
    merged = merged.merge(rates, on="date_key", how="inner")
    merged = merged.merge(infl, on="date_key", how="inner")
    merged["date"] = _parse_month_date(merged["date_key"])
    merged = merged.sort_values("date").reset_index(drop=True)

    # Also add quarterly data interpolated to monthly
    conn2 = _connect(db_path)
    gdp_q = pd.read_sql("SELECT date_key, gdp_growth_yoy FROM fact_gdp ORDER BY date_key", conn2)
    conn2.close()
    gdp_q["date"] = _parse_quarter_date(gdp_q["date_key"])
    gdp_q = gdp_q.set_index("date")[["gdp_growth_yoy"]].resample("MS").mean()
    gdp_q["gdp_growth"] = gdp_q["gdp_growth_yoy"].interpolate(method="linear")
    gdp_monthly = gdp_q[["gdp_growth"]].reset_index()
    gdp_monthly.columns = ["date", "gdp_growth"]
    merged = merged.merge(gdp_monthly, on="date", how="left")

    # Normalise each indicator to 0-100 scale
    indicators = {
        "Unemployment": "unemployment_rate",
        "NPL Ratio": "npl_ratio",
        "PT 10Y Yield": "portugal_10y_bond_yield",
        "HICP Inflation": "hicp",
        "GDP Growth": "gdp_growth",
    }

    line_colors = [
        COLORS["primary"],
        COLORS["accent"],
        COLORS["secondary"],
        COLORS["positive"],
        CHART_PURPLE,
    ]

    fig, ax = plt.subplots(figsize=(14, 8))
    _setup_fig(fig)

    for (label, col), color in zip(indicators.items(), line_colors):
        series = merged[col].dropna()
        if len(series) == 0:
            continue
        smin, smax = series.min(), series.max()
        if smax - smin == 0:
            normalised = series * 0 + 50
        else:
            normalised = (series - smin) / (smax - smin) * 100
        ax.plot(
            merged.loc[normalised.index, "date"],
            normalised,
            color=color,
            linewidth=1.8,
            label=label,
        )

    # Highlight crisis events
    events = [
        ("2011-04", "Bailout\nRequest", 92),
        ("2012-01", "Troika\nAusterity", 85),
        ("2020-03", "COVID-19\nLockdown", 92),
        ("2022-03", "Inflation\nShock", 85),
    ]
    for date_str, label, y_pos in events:
        evt_date = pd.Timestamp(date_str)
        ax.axvline(
            evt_date, color=COLORS["neutral"], linewidth=1, linestyle="--", alpha=0.6, zorder=1
        )
        ax.annotate(
            label,
            xy=(evt_date, y_pos),
            fontsize=CHART_FONT_SIZES["annotation"],
            fontweight="bold",
            ha="center",
            color=CHART_DARK_TEXT,
            bbox=dict(
                boxstyle="round,pad=0.3", facecolor="white", edgecolor=CHART_NEUTRAL, alpha=0.85
            ),
        )

    _shade_periods(ax, merged["date"])

    ax.set_ylabel("Normalised Scale (0-100)")
    ax.set_xlabel("")
    ax.set_ylim(-5, 105)
    ax.set_title("Crisis Timeline: Normalised Economic Indicators (2010-2025)", pad=20)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), frameon=False, ncol=3)
    _period_legend(ax)

    fig.tight_layout(pad=2.0)
    fig.subplots_adjust(bottom=0.20)
    _add_source_text(fig, y=-0.01)

    return _savefig(fig, "crisis_timeline.png")


# =============================================================================
# 11. GENERATE ALL CHARTS
# =============================================================================


def generate_all_charts(db_path=None):
    """
    Generate all charts and return a list of output file paths.

    Parameters
    ----------
    db_path : str or Path, optional
        Path to the SQLite database. Defaults to the project database.

    Returns
    -------
    list[str]
        List of absolute file paths for the generated PNG charts.
    """
    chart_functions = [
        ("GDP Evolution", plot_gdp_evolution),
        ("Unemployment Trends", plot_unemployment_trends),
        ("Credit Portfolio", plot_credit_portfolio),
        ("Interest Rate Environment", plot_interest_rate_environment),
        ("Inflation Dashboard", plot_inflation_dashboard),
        ("Public Debt Sustainability", plot_public_debt_sustainability),
        ("Correlation Heatmap", plot_correlation_heatmap),
        ("Economic Dashboard", plot_economic_dashboard),
        ("Phillips Curve", plot_phillips_curve),
        ("Crisis Timeline", plot_crisis_timeline),
    ]

    paths = []
    for name, func in chart_functions:
        try:
            print(f"  Generating: {name}...", end=" ", flush=True)
            path = func(db_path)
            paths.append(path)
            print(f"OK -> {Path(path).name}")
        except Exception as e:
            print(f"FAILED -> {e}")

    return paths


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Portugal Data Intelligence - Chart Generation")
    print("=" * 60)
    print(f"Database : {DEFAULT_DB}")
    print(f"Output   : {CHARTS_DIR}")
    print("-" * 60)

    paths = generate_all_charts()

    print("-" * 60)
    print(f"Generated {len(paths)} / 10 charts successfully.")
    print("=" * 60)
