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
# DESIGN SYSTEM COLOUR PALETTE
# 60-30-10 Rule: 60% neutrals, 30% primary/secondary, 10% accent
# =============================================================================

_PRIMARY = "#9B2226"  # Deep red — risk, decline, critical
_SECONDARY = "#386641"  # Forest green — growth, success, positive
_ACCENT = "#D4A373"  # Warm gold — highlight, key insight

_BG = "#FFFFFF"  # Pure white background
_TEXT_PRIMARY = "#1A1A2E"  # Dark navy — body text (high contrast)
_TEXT_SECONDARY = "#3D3D5C"  # Dark slate — captions, labels (readable)
_BORDER = "#D0D0D0"  # Medium grey — grid lines, dividers
_MUTED_BG = "#F5F5F5"  # Very light grey — table headers, cards

_PRIMARY_LIGHT = "#C4494D"  # Lighter red for secondary elements
_PRIMARY_FAINT = "#F2D5D6"  # Very light red for backgrounds
_SECONDARY_LIGHT = "#5A8F62"  # Lighter green
_SECONDARY_FAINT = "#D6E8D4"  # Very light green for backgrounds
_ACCENT_LIGHT = "#E8C9A0"  # Lighter gold
_ACCENT_FAINT = "#F5EBD9"  # Very light gold for backgrounds

_NEGATIVE = _PRIMARY  # Declines, losses, risks
_POSITIVE = _SECONDARY  # Growth, gains, success
_NEUTRAL = _TEXT_SECONDARY  # Baseline, unchanged

_PALETTE_FULL = [_PRIMARY, _SECONDARY, _ACCENT, "#4A6FA5"]

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
    # Grid
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": _BORDER,
    "grid.linewidth": 0.4,
    "grid.alpha": 0.6,
    "grid.linestyle": "--",
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
    "font.sans-serif": ["Segoe UI", "Helvetica Neue", "Arial", "sans-serif"],
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
CHART_NEUTRAL = _TEXT_SECONDARY
CHART_BACKGROUND = _BG
CHART_DARK_TEXT = _TEXT_PRIMARY
CHART_LIGHT_TEXT = _TEXT_SECONDARY
CHART_GRID = _BORDER
CHART_PURPLE = "#4A6FA5"  # Steel blue — additional series

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
    "Pre-crisis": "#C8E6C9",  # Soft green
    "Troika": "#FFCDD2",  # Soft red
    "Recovery": "#BBDEFB",  # Soft blue
    "COVID": "#FFF9C4",  # Soft yellow
    "Post-COVID": "#E1BEE7",  # Soft purple
}

ZONE_CAUTION = "#FFF3CD"  # Light yellow — caution zone
ZONE_THRESHOLD = "#F0B27A"  # Orange — threshold line

# =============================================================================
# BENCHMARK / COUNTRY COLOURS
# =============================================================================

COUNTRY_COLORS = {
    "PT": _PRIMARY,  # Deep red — Portugal (always emphasised)
    "DE": "#1A1A2E",  # Dark navy — Germany
    "ES": "#E65100",  # Deep orange — Spain
    "FR": "#1565C0",  # Strong blue — France
    "IT": "#2E7D32",  # Green — Italy
    "EU_AVG": "#757575",  # Medium grey — EU average
    "EA_AVG": "#757575",  # Medium grey — Euro Area average
}

# =============================================================================
# CHART TYPOGRAPHY
# =============================================================================

FONT_HEADING = "Segoe UI"
FONT_BODY = "Segoe UI"

CHART_FONT_FAMILY = "sans-serif"
CHART_FONT_FALLBACK = ["Segoe UI", "Helvetica Neue", "Arial", "sans-serif"]

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
