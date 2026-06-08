"""
Portugal Data Intelligence - NUTS2 Regional Analysis
=====================================================
Analyses regional macroeconomic disparities across Portugal's NUTS2 regions
using Eurostat data on GDP per capita and unemployment rates.

NUTS2 regions covered:
    PT11 — Norte       PT15 — Alentejo    PT16 — Centro
    PT17 — Lisboa      PT18 — Algarve     PT20 — Açores
    PT30 — Madeira

Usage:
    from src.analysis.regional_analysis import run_regional_analysis
    result = run_regional_analysis()
"""

import json
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config.settings import DATABASE_PATH, PROJECT_ROOT
from src.utils.db import get_connection
from src.utils.logger import get_logger

logger = get_logger(__name__)

_NUTS2_REGIONS: Dict[str, str] = {
    "PT11": "Norte",
    "PT15": "Alentejo",
    "PT16": "Centro",
    "PT17": "Lisboa",
    "PT18": "Algarve",
    "PT20": "Açores",
    "PT30": "Madeira",
}

_REGIONAL_GDP_QUERY = """
    SELECT nuts2_code, nuts2_name, date_key, gdp_per_capita_pps, gdp_index_eu27
    FROM fact_regional
    WHERE nuts2_code IS NOT NULL AND gdp_per_capita_pps IS NOT NULL
    ORDER BY nuts2_code, date_key
"""

_REGIONAL_UNEMP_QUERY = """
    SELECT nuts2_code, nuts2_name, date_key, unemployment_rate, youth_unemployment_rate
    FROM fact_regional
    WHERE nuts2_code IS NOT NULL AND unemployment_rate IS NOT NULL
    ORDER BY nuts2_code, date_key
"""


def _latest_by_region(df: pd.DataFrame, col: str) -> Dict[str, float]:
    """Return {nuts2_code: latest_value} for a given column."""
    result: Dict[str, float] = {}
    for code, group in df.groupby("nuts2_code"):
        series = group[col].dropna()
        if not series.empty:
            result[str(code)] = float(series.iloc[-1])
    return result


def _regional_dispersion(values: Dict[str, float]) -> Dict[str, float]:
    """Compute dispersion metrics for a dict of regional values."""
    if not values:
        return {}
    vals = list(values.values())
    return {
        "mean": round(float(np.mean(vals)), 2),
        "std": round(float(np.std(vals, ddof=1)), 2),
        "cv": round(float(np.std(vals, ddof=1) / np.mean(vals)), 4) if np.mean(vals) != 0 else 0,
        "min": round(float(np.min(vals)), 2),
        "max": round(float(np.max(vals)), 2),
        "range": round(float(np.max(vals) - np.min(vals)), 2),
    }


def _convergence_trend(df: pd.DataFrame, col: str) -> Optional[float]:
    """Return slope of coefficient of variation over time (negative = convergence)."""
    try:
        cv_by_year = []
        for year, group in df.groupby(df["date_key"].str[:4]):
            vals = group[col].dropna().values
            if len(vals) >= 3 and np.mean(vals) != 0:
                cv = float(np.std(vals, ddof=1) / np.mean(vals))
                cv_by_year.append((int(year), cv))
        if len(cv_by_year) < 4:
            return None
        years = np.array([y for y, _ in cv_by_year])
        cvs = np.array([c for _, c in cv_by_year])
        slope = float(np.polyfit(years, cvs, 1)[0])
        return round(slope, 6)
    except Exception:
        return None


def _top_bottom(values: Dict[str, float], region_names: Dict[str, str]) -> Dict:
    """Return the best and worst region for a metric."""
    if not values:
        return {}
    best_code = max(values, key=values.__getitem__)
    worst_code = min(values, key=values.__getitem__)
    return {
        "best": {
            "code": best_code,
            "name": region_names.get(best_code, best_code),
            "value": values[best_code],
        },
        "worst": {
            "code": worst_code,
            "name": region_names.get(worst_code, worst_code),
            "value": values[worst_code],
        },
    }


def _synthetic_fallback() -> Dict:
    """Return synthetic NUTS2 data based on Eurostat estimates when DB table is absent."""
    gdp_pps_2022 = {
        "PT11": 17_800,
        "PT15": 14_100,
        "PT16": 15_200,
        "PT17": 26_500,
        "PT18": 19_800,
        "PT20": 15_900,
        "PT30": 18_200,
    }
    unemp_2023 = {
        "PT11": 6.8,
        "PT15": 8.2,
        "PT16": 7.1,
        "PT17": 6.2,
        "PT18": 9.1,
        "PT20": 10.4,
        "PT30": 8.7,
    }
    gdp_dispersion = _regional_dispersion(gdp_pps_2022)
    unemp_dispersion = _regional_dispersion(unemp_2023)

    return {
        "source": "synthetic_fallback",
        "note": "fact_regional table not found; using synthetic estimates based on Eurostat data",
        "gdp_per_capita_pps": {
            "latest_by_region": {
                k: {"name": _NUTS2_REGIONS[k], "value": v} for k, v in gdp_pps_2022.items()
            },
            "dispersion": gdp_dispersion,
            "ranking": sorted(_NUTS2_REGIONS, key=lambda c: gdp_pps_2022.get(c, 0), reverse=True),
            "top_bottom": _top_bottom(gdp_pps_2022, _NUTS2_REGIONS),
        },
        "unemployment_rate": {
            "latest_by_region": {
                k: {"name": _NUTS2_REGIONS[k], "value": v} for k, v in unemp_2023.items()
            },
            "dispersion": unemp_dispersion,
            "ranking": sorted(_NUTS2_REGIONS, key=lambda c: unemp_2023.get(c, 0)),
            "top_bottom": _top_bottom({k: -v for k, v in unemp_2023.items()}, _NUTS2_REGIONS),
        },
        "key_findings": [
            "Lisboa has the highest GDP per capita (PPS), at ~49% above the national average",
            "Açores has the highest unemployment rate among all NUTS2 regions",
            "Alentejo has the lowest GDP per capita; the Lisboa–Alentejo gap exceeds EUR 12,000 PPS",
            "Regional convergence in GDP has been slow; CV remained above 0.20 throughout 2000–2022",
        ],
    }


def run_regional_analysis(db_path: Optional[str] = None) -> Dict:
    """Analyse NUTS2 regional disparities in GDP and unemployment.

    Falls back to synthetic estimates if the fact_regional table does not exist.

    Returns
    -------
    dict
        Keys: gdp_per_capita_pps, unemployment_rate, convergence, key_findings
    """
    db_path = db_path or str(DATABASE_PATH)

    with get_connection(db_path) as conn:
        try:
            gdp_df = pd.read_sql(_REGIONAL_GDP_QUERY, conn)
            unemp_df = pd.read_sql(_REGIONAL_UNEMP_QUERY, conn)
        except Exception as exc:
            logger.warning("fact_regional not available (%s); using synthetic fallback", exc)
            return _synthetic_fallback()

    if gdp_df.empty and unemp_df.empty:
        return _synthetic_fallback()

    result: Dict = {}

    # GDP per capita (PPS)
    if not gdp_df.empty and "gdp_per_capita_pps" in gdp_df.columns:
        latest_gdp = _latest_by_region(gdp_df, "gdp_per_capita_pps")
        dispersion_gdp = _regional_dispersion(latest_gdp)
        conv_gdp = _convergence_trend(gdp_df, "gdp_per_capita_pps")
        result["gdp_per_capita_pps"] = {
            "latest_by_region": {
                k: {
                    "name": (
                        gdp_df.loc[gdp_df["nuts2_code"] == k, "nuts2_name"].iloc[0]
                        if not gdp_df.loc[gdp_df["nuts2_code"] == k].empty
                        else k
                    ),
                    "value": v,
                }
                for k, v in latest_gdp.items()
            },
            "dispersion": dispersion_gdp,
            "convergence_slope": conv_gdp,
            "ranking": sorted(latest_gdp, key=latest_gdp.__getitem__, reverse=True),
            "top_bottom": _top_bottom(latest_gdp, _NUTS2_REGIONS),
        }

    # Unemployment
    if not unemp_df.empty and "unemployment_rate" in unemp_df.columns:
        latest_unemp = _latest_by_region(unemp_df, "unemployment_rate")
        dispersion_unemp = _regional_dispersion(latest_unemp)
        conv_unemp = _convergence_trend(unemp_df, "unemployment_rate")
        result["unemployment_rate"] = {
            "latest_by_region": {
                k: {
                    "name": (
                        unemp_df.loc[unemp_df["nuts2_code"] == k, "nuts2_name"].iloc[0]
                        if not unemp_df.loc[unemp_df["nuts2_code"] == k].empty
                        else k
                    ),
                    "value": v,
                }
                for k, v in latest_unemp.items()
            },
            "dispersion": dispersion_unemp,
            "convergence_slope": conv_unemp,
            "ranking": sorted(latest_unemp, key=latest_unemp.__getitem__),
            "top_bottom": _top_bottom({k: -v for k, v in latest_unemp.items()}, _NUTS2_REGIONS),
        }

    # Summary findings
    findings: List[str] = []
    gdp_block = result.get("gdp_per_capita_pps", {})
    unemp_block = result.get("unemployment_rate", {})
    if gdp_block.get("top_bottom"):
        best = gdp_block["top_bottom"].get("best", {})
        worst = gdp_block["top_bottom"].get("worst", {})
        if best and worst:
            findings.append(
                f"{best.get('name', best.get('code', ''))} has the highest GDP per capita (PPS): "
                f"{best.get('value', 0):,.0f}"
            )
            findings.append(
                f"{worst.get('name', worst.get('code', ''))} has the lowest: "
                f"{worst.get('value', 0):,.0f} — a gap of "
                f"{best.get('value', 0) - worst.get('value', 0):,.0f} PPS"
            )
    if unemp_block.get("dispersion", {}).get("range"):
        findings.append(
            f"Unemployment range across regions: " f"{unemp_block['dispersion']['range']:.1f} pp"
        )
    if gdp_block.get("convergence_slope") is not None:
        slope = gdp_block["convergence_slope"]
        direction = "converging" if slope < 0 else "diverging"
        findings.append(
            f"Regional GDP dispersion is {direction} (CV trend slope: {slope:.6f} per year)"
        )

    result["key_findings"] = findings

    logger.info(
        "Regional analysis complete: %d GDP obs, %d unemployment obs",
        len(gdp_df),
        len(unemp_df),
    )
    return result


# =============================================================================
# Choropleth map helpers
# =============================================================================

_GEOJSON_CACHE = PROJECT_ROOT / "data" / "reference" / "nuts2_portugal.geojson"
_GEOJSON_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/"
    "NUTS_RG_10M_2021_4326_LEVL_2.geojson"
)


def _get_nuts2_geojson() -> Optional[dict]:
    """Fetch and cache the Portugal NUTS2 GeoJSON from Eurostat GISCO."""
    _GEOJSON_CACHE.parent.mkdir(parents=True, exist_ok=True)

    if _GEOJSON_CACHE.exists():
        try:
            return json.loads(_GEOJSON_CACHE.read_text(encoding="utf-8"))
        except Exception:
            _GEOJSON_CACHE.unlink(missing_ok=True)

    try:
        # _GEOJSON_URL is a hardcoded HTTPS Eurostat GISCO URL, not user input
        with urllib.request.urlopen(_GEOJSON_URL, timeout=30) as resp:  # nosec B310
            full_geo = json.loads(resp.read().decode("utf-8"))
        pt_features = [
            f
            for f in full_geo.get("features", [])
            if str(f.get("properties", {}).get("NUTS_ID", "")).startswith("PT")
        ]
        pt_geo: dict = {"type": "FeatureCollection", "features": pt_features}
        _GEOJSON_CACHE.write_text(json.dumps(pt_geo), encoding="utf-8")
        logger.info("Downloaded and cached Portugal NUTS2 GeoJSON (%d features)", len(pt_features))
        return pt_geo
    except Exception as exc:
        logger.warning("Could not fetch NUTS2 GeoJSON: %s", exc)
        return None


def build_choropleth_div(db_path: Optional[str] = None, include_plotlyjs: object = "cdn") -> str:
    """Build an interactive Plotly choropleth of Portuguese NUTS2 regions.

    Returns an HTML <div> string for embedding in reports, or empty string
    if plotly or the GeoJSON are unavailable.

    ``include_plotlyjs`` is forwarded to ``plotly.offline.plot`` so callers
    that already embed plotly.js elsewhere can pass ``False`` to avoid
    duplicating the library.
    """
    try:
        import plotly.express as px
        import plotly.offline as pyo
    except ImportError:
        return ""

    geojson = _get_nuts2_geojson()
    if not geojson:
        return ""

    regional = run_regional_analysis(db_path)
    gdp_block = regional.get("gdp_per_capita_pps", {})
    unemp_block = regional.get("unemployment_rate", {})
    latest_gdp = gdp_block.get("latest_by_region", {})
    latest_unemp = unemp_block.get("latest_by_region", {})

    if not latest_gdp:
        return ""

    rows = []
    for code in _NUTS2_REGIONS:
        gdp_info = latest_gdp.get(code, {})
        unemp_info = latest_unemp.get(code, {})
        gdp_val = gdp_info.get("value") if isinstance(gdp_info, dict) else gdp_info
        unemp_val = unemp_info.get("value") if isinstance(unemp_info, dict) else unemp_info
        rows.append(
            {
                "nuts2_code": code,
                "name": _NUTS2_REGIONS[code],
                "gdp_pps": float(gdp_val) if gdp_val is not None else float("nan"),
                "unemployment": float(unemp_val) if unemp_val is not None else float("nan"),
            }
        )

    df = pd.DataFrame(rows).dropna(subset=["gdp_pps"])

    fig = px.choropleth(
        df,
        geojson=geojson,
        locations="nuts2_code",
        color="gdp_pps",
        featureidkey="properties.NUTS_ID",
        color_continuous_scale="Blues",
        labels={
            "gdp_pps": "GDP per Capita (PPS)",
            "nuts2_code": "Code",
            "unemployment": "Unemp. (%)",
        },
        hover_name="name",
        hover_data={"nuts2_code": False, "gdp_pps": ":,.0f", "unemployment": ":.1f"},
        title="GDP per Capita by NUTS2 Region (PPS)",
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r": 10, "t": 40, "l": 10, "b": 10},
        height=420,
        paper_bgcolor="white",
        coloraxis_colorbar={"title": "GDP PPS", "thickness": 14},
        font={"family": "Inter, 'Segoe UI', sans-serif", "size": 12},
        title_font={"size": 14},
    )

    try:
        return pyo.plot(
            fig,
            output_type="div",
            include_plotlyjs=include_plotlyjs,
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            },
        )
    except Exception as exc:
        logger.warning("Choropleth render failed: %s", exc)
        return ""
