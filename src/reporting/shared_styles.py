"""
Portugal Data Intelligence — Shared Style Constants
=====================================================
Single source of truth for all visual styling across the project:
matplotlib charts, Streamlit dashboard, and HTML reports.

Colours are stored as hex strings for matplotlib / seaborn.
"""

import logging

import matplotlib as mpl

logger = logging.getLogger(__name__)

# =============================================================================
# DESIGN SYSTEM COLOUR PALETTE — editorial "consulting research" look
# One brand hue (electric blue) supported by ink/cyan/grey for series;
# green/red are reserved for semantics (gains/losses, risk) only.
# Mirrors the HTML report design system (dashboard/generate_report.py).
# =============================================================================

_PRIMARY = "#2251FF"  # Electric blue — primary data series / brand accent
_SECONDARY = "#051C2C"  # Deep navy ink — second series
_ACCENT = "#00A9F4"  # Cyan — third series / highlight

_BG = "#FFFFFF"  # Pure white background
_TEXT_PRIMARY = "#15191E"  # Near-black ink — body text (high contrast)
_TEXT_SECONDARY = "#3D4754"  # Slate — captions, labels (readable)
_BORDER = "#E4E7EB"  # Hairline grey — grid lines, dividers
_MUTED_BG = "#F6F7F8"  # Very light grey — table headers, cards

_PRIMARY_LIGHT = "#6E8FFF"  # Lighter blue for secondary elements
_PRIMARY_FAINT = "#E6EBFF"  # Very light blue for backgrounds
_SECONDARY_LIGHT = "#2E4456"  # Lighter navy
_SECONDARY_FAINT = "#DCE3E9"  # Very light navy for backgrounds
_ACCENT_LIGHT = "#66C9F8"  # Lighter cyan
_ACCENT_FAINT = "#DFF4FE"  # Very light cyan for backgrounds

_NEGATIVE = "#C03434"  # Declines, losses, risks (muted red)
_POSITIVE = "#0E7C3F"  # Growth, gains, success (muted green)
_NEUTRAL = "#6A737F"  # Baseline, unchanged (cool grey)

_PALETTE_FULL = [_PRIMARY, _SECONDARY, _ACCENT, "#6E7B8A"]

# =============================================================================
# MATPLOTLIB RC PARAMS
# =============================================================================

_DS_RC = {
    # Figure
    "figure.facecolor": _BG,
    "figure.edgecolor": "none",
    "figure.figsize": (12, 6),
    "figure.dpi": 150,
    "figure.titlesize": 16,
    "figure.titleweight": "bold",
    # Axes
    "axes.facecolor": _BG,
    "axes.edgecolor": _BORDER,
    "axes.linewidth": 0.8,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.titlecolor": _TEXT_PRIMARY,
    "axes.titlepad": 16,
    "axes.labelsize": 11,
    "axes.labelcolor": _TEXT_PRIMARY,
    "axes.labelpad": 8,
    "axes.prop_cycle": mpl.cycler(color=_PALETTE_FULL),  # type: ignore[attr-defined]
    "axes.spines.top": False,
    "axes.spines.right": False,
    # Grid — solid hairlines (editorial style), horizontal only
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": _BORDER,
    "grid.linewidth": 0.6,
    "grid.alpha": 0.9,
    "grid.linestyle": "-",
    # Ticks
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "xtick.color": _TEXT_SECONDARY,
    "ytick.color": _TEXT_SECONDARY,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "xtick.major.pad": 6,
    "ytick.major.pad": 6,
    # Lines
    "lines.linewidth": 2.4,
    "lines.markersize": 6,
    # Patches (bars, etc.)
    "patch.edgecolor": "none",
    # Legend
    "legend.frameon": False,
    "legend.fontsize": 10,
    "legend.title_fontsize": 11,
    "legend.labelcolor": _TEXT_PRIMARY,
    # Font
    "font.family": "sans-serif",
    "font.sans-serif": ["Inter", "Segoe UI", "Helvetica Neue", "Arial", "sans-serif"],
    "font.size": 10,
    "text.color": _TEXT_PRIMARY,
    # Savefig
    "savefig.facecolor": _BG,
    "savefig.edgecolor": "none",
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.3,
}

# =============================================================================
# CHART COLOUR PALETTE  (hex strings — for matplotlib / seaborn)
# =============================================================================

CHART_PRIMARY = _PRIMARY
CHART_SECONDARY = _SECONDARY
CHART_ACCENT = _ACCENT
CHART_POSITIVE = _POSITIVE
CHART_NEGATIVE = _NEGATIVE
CHART_NEUTRAL = _NEUTRAL
CHART_BACKGROUND = _BG
CHART_DARK_TEXT = _TEXT_PRIMARY
CHART_LIGHT_TEXT = _TEXT_SECONDARY
CHART_GRID = _BORDER
CHART_PURPLE = "#6E7B8A"  # Cool grey — additional series

CHART_COLORS = {
    "primary": CHART_PRIMARY,
    "secondary": CHART_SECONDARY,
    "accent": CHART_ACCENT,
    "positive": CHART_POSITIVE,
    "negative": CHART_NEGATIVE,
    "neutral": CHART_NEUTRAL,
    "background": CHART_BACKGROUND,
    "dark_text": CHART_DARK_TEXT,
    "light_text": CHART_LIGHT_TEXT,
}

# =============================================================================
# ECONOMIC PERIOD SHADING COLOURS (subtle, don't overpower data)
# =============================================================================

PERIOD_COLORS = {
    "Pre-crisis": "#D9E2EC",  # Cool blue-grey
    "Troika": "#F3D8D8",  # Muted red — crisis
    "Recovery": "#D6E4F7",  # Soft blue
    "COVID": "#F5E5C8",  # Muted amber
    "Post-COVID": "#DEF0E4",  # Muted green
}

ZONE_CAUTION = "#F5E9C9"  # Muted amber — caution zone
ZONE_THRESHOLD = "#D9A441"  # Amber — threshold line

# =============================================================================
# BENCHMARK / COUNTRY COLOURS
# Portugal carries the brand blue; peers stay in restrained supporting hues.
# =============================================================================

COUNTRY_COLORS = {
    "PT": _PRIMARY,  # Electric blue — Portugal (always emphasised)
    "DE": "#051C2C",  # Deep navy — Germany
    "ES": "#D9A441",  # Amber — Spain
    "FR": "#00A9F4",  # Cyan — France
    "IT": "#6E7B8A",  # Cool grey — Italy
    "EU_AVG": "#9AA3AE",  # Light grey — EU average
    "EA_AVG": "#9AA3AE",  # Light grey — Euro Area average
}

# =============================================================================
# CHART TYPOGRAPHY
# =============================================================================

FONT_HEADING = "Inter"
FONT_BODY = "Inter"

CHART_FONT_FAMILY = "sans-serif"
CHART_FONT_FALLBACK = ["Inter", "Segoe UI", "Helvetica Neue", "Arial", "sans-serif"]

CHART_FONT_SIZES = {
    "suptitle": 20,
    "title": 16,
    "subtitle": 14,
    "label": 12,
    "axis_label": 12,
    "tick": 10,
    "legend": 10,
    "annotation": 10,
    "source": 9,
    "small": 9,
}

# =============================================================================
# CHART RENDERING
# =============================================================================

CHART_DPI = 300  # Publication-quality (300 DPI)
CHART_DISPLAY_DPI = 100  # Screen display

# =============================================================================
# CHART ALPHA / TRANSPARENCY CONSTANTS
# =============================================================================

CHART_PERIOD_ALPHA = 0.10  # Economic period background (very subtle)
CHART_GRID_ALPHA = 0.6  # Grid line transparency
CHART_LEGEND_FRAMEALPHA = 0.0  # Legend background (frameon=False)
CHART_PERIOD_LEGEND_ALPHA = 0.40  # Period legend patches
CHART_FILL_ALPHA = 0.08  # Sparkline area fill


# =============================================================================
# HELPER — apply matplotlib rcParams
# =============================================================================


def apply_chart_style():
    """Apply the project-wide matplotlib rcParams.

    Call this once at module level in any script that generates charts.
    """
    import matplotlib.pyplot as plt

    params = _DS_RC.copy()

    params.update(
        {
            "figure.dpi": CHART_DISPLAY_DPI,
            "figure.facecolor": CHART_BACKGROUND,
            "axes.facecolor": CHART_BACKGROUND,
            "axes.titlesize": CHART_FONT_SIZES["title"],
            "axes.titlepad": 14,
            "axes.labelsize": CHART_FONT_SIZES["axis_label"],
            "axes.labelcolor": _TEXT_PRIMARY,
            "axes.labelpad": 8,
            "xtick.labelsize": CHART_FONT_SIZES["tick"],
            "ytick.labelsize": CHART_FONT_SIZES["tick"],
            "xtick.color": _TEXT_SECONDARY,
            "ytick.color": _TEXT_SECONDARY,
            "legend.fontsize": CHART_FONT_SIZES["legend"],
            "legend.title_fontsize": CHART_FONT_SIZES["label"],
            "legend.labelcolor": _TEXT_PRIMARY,
            "figure.titlesize": CHART_FONT_SIZES["suptitle"],
            "figure.subplot.hspace": 0.35,
            "figure.subplot.wspace": 0.35,
            "savefig.dpi": CHART_DPI,
            "savefig.bbox": "tight",
            "savefig.facecolor": CHART_BACKGROUND,
            "savefig.edgecolor": "none",
            "savefig.pad_inches": 0.3,
        }
    )

    plt.rcParams.update(params)

    try:
        import seaborn as sns

        sns.set_theme(
            style="whitegrid",
            rc=params,
            palette=_PALETTE_FULL,
        )
        sns.set_context(
            "notebook",
            rc={
                "axes.titlesize": CHART_FONT_SIZES["title"],
                "axes.labelsize": CHART_FONT_SIZES["axis_label"],
                "xtick.labelsize": CHART_FONT_SIZES["tick"],
                "ytick.labelsize": CHART_FONT_SIZES["tick"],
            },
        )
    except ImportError:
        logger.debug("seaborn not available — skipping seaborn theme configuration.")
