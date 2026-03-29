"""
Portugal Data Intelligence - Cross-Pillar Rule-Based Insights
==============================================================
Standalone functions that generate cross-pillar narrative commentary
analysing relationships between macroeconomic pillars.

Extracted from InsightEngine to keep the facade class slim.
"""

import sqlite3
from typing import Dict


def _safe(value, fmt: str = ".1f") -> str:
    """Format a numeric value safely, returning 'N/A' on failure."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):{fmt}}"
    except (TypeError, ValueError):
        return str(value)


def generate_rule_based_cross_pillar(summaries: Dict[str, dict], db_path: str) -> dict:
    """Produce cross-pillar narrative using economic relationships.

    Parameters
    ----------
    summaries : dict
        Mapping of pillar name to its data summary dict.
    db_path : str
        Path to the SQLite database (needed by the macro narrative).
    """
    relationships = []
    s = _safe

    # 1. Unemployment-GDP (Okun's Law)
    gdp = summaries.get("gdp", {})
    unemp = summaries.get("unemployment", {})
    if gdp.get("status") == "ok" and unemp.get("status") == "ok":
        gdp_growth = gdp.get("recent_avg_growth")
        unemp_trend = unemp.get("trend")
        unemp_latest = unemp.get("latest_value")
        if gdp_growth is not None and gdp_growth > 2 and unemp_trend == "decreasing":
            narrative = (
                f"Okun's Law relationship is functioning as expected: GDP growth averaging "
                f"{s(gdp_growth)}% has been accompanied by declining unemployment (currently "
                f"{s(unemp_latest)}%). The labour market is absorbing output expansion, "
                f"consistent with a healthy growth-employment nexus."
            )
            strength = "strong"
        elif gdp_growth is not None and gdp_growth > 0 and unemp_trend != "decreasing":
            narrative = (
                f"A disconnect is emerging between GDP growth ({s(gdp_growth)}%) and the "
                f"labour market (unemployment trend: {unemp_trend}). This 'jobless growth' "
                f"pattern may indicate structural mismatches, increased automation, or "
                f"labour market rigidities that prevent output gains from translating "
                f"into employment creation."
            )
            strength = "weak"
        else:
            narrative = (
                f"Both GDP and employment indicators suggest economic weakness. GDP growth "
                f"of {s(gdp_growth)}% is insufficient to drive meaningful unemployment reduction. "
                f"The economy may be operating in a low-growth equilibrium."
            )
            strength = "consistent_weakness"
        relationships.append(
            {
                "name": "GDP-Unemployment Nexus (Okun's Law)",
                "pillars": ["gdp", "unemployment"],
                "narrative": narrative,
                "relationship_strength": strength,
            }
        )

    # 2. Interest Rates-Credit Transmission
    ir = summaries.get("interest_rates", {})
    credit = summaries.get("credit", {})
    if ir.get("status") == "ok" and credit.get("status") == "ok":
        ir_trend = ir.get("trend")
        credit_trend = credit.get("trend")
        if ir_trend == "decreasing" and credit_trend == "increasing":
            narrative = (
                f"Monetary policy transmission appears effective: declining interest rates "
                f"have been accompanied by expanding credit. The ECB's accommodative stance "
                f"is successfully lowering borrowing costs and stimulating lending in Portugal."
            )
            strength = "strong"
        elif ir_trend == "decreasing" and credit_trend != "increasing":
            narrative = (
                f"Despite declining interest rates, credit has not expanded as expected "
                f"(credit trend: {credit_trend}). This impaired transmission suggests "
                f"structural impediments in the banking sector, including legacy NPL "
                f"burdens, risk aversion, or weak demand for credit."
            )
            strength = "impaired"
        elif ir_trend == "increasing" and credit_trend == "decreasing":
            narrative = (
                f"Rising interest rates are dampening credit creation, consistent with "
                f"standard monetary policy mechanics. The tightening cycle is transmitting "
                f"through Portuguese lending conditions as intended."
            )
            strength = "strong"
        else:
            narrative = (
                f"The interest rate-credit relationship shows atypical patterns, with "
                f"rates trending {ir_trend} while credit is trending {credit_trend}. "
                f"Non-standard factors may be at play, including regulatory changes, "
                f"capital market substitution, or structural shifts in credit demand."
            )
            strength = "atypical"
        relationships.append(
            {
                "name": "Monetary Policy Transmission (Rates-Credit)",
                "pillars": ["interest_rates", "credit"],
                "narrative": narrative,
                "relationship_strength": strength,
            }
        )

    # 3. Inflation-Monetary Policy Alignment
    inflation = summaries.get("inflation", {})
    if ir.get("status") == "ok" and inflation.get("status") == "ok":
        inf_latest = inflation.get("latest_value")
        ir_latest = ir.get("latest_value")
        if inf_latest is not None and ir_latest is not None:
            real_rate = ir_latest - inf_latest
            if inf_latest > 3 and ir_latest > inf_latest:
                narrative = (
                    f"Monetary policy is restrictive: the nominal rate ({s(ir_latest)}%) exceeds "
                    f"inflation ({s(inf_latest)}%), yielding a positive real rate of {s(real_rate)}%. "
                    f"This stance is appropriate for bringing inflation back toward the 2% target, "
                    f"though the contractionary impact on economic activity must be weighed."
                )
            elif inf_latest > 3 and ir_latest < inf_latest:
                narrative = (
                    f"Monetary policy may be insufficiently restrictive: with inflation at "
                    f"{s(inf_latest)}% and the nominal rate at {s(ir_latest)}%, the real rate "
                    f"is negative ({s(real_rate)}%). This risks embedding inflationary "
                    f"expectations and may require further rate increases."
                )
            elif inf_latest < 1 and ir_latest < 1:
                narrative = (
                    f"Both inflation ({s(inf_latest)}%) and interest rates ({s(ir_latest)}%) "
                    f"are at historically low levels, reflecting a disinflationary environment. "
                    f"The ECB's ultra-accommodative stance aims to prevent deflation but has "
                    f"limited further room for conventional easing."
                )
            else:
                narrative = (
                    f"Inflation at {s(inf_latest)}% and interest rates at {s(ir_latest)}% suggest "
                    f"a broadly neutral monetary stance with a real rate of {s(real_rate)}%. "
                    f"The calibration appears appropriate given current conditions."
                )
            relationships.append(
                {
                    "name": "Inflation-Monetary Policy Alignment",
                    "pillars": ["inflation", "interest_rates"],
                    "narrative": narrative,
                    "relationship_strength": "assessed",
                }
            )

    # 4. Debt Sustainability vs Growth Dynamics
    debt = summaries.get("public_debt", {})
    if gdp.get("status") == "ok" and debt.get("status") == "ok":
        gdp_growth_val = gdp.get("recent_avg_growth")
        debt_trend = debt.get("trend")
        debt_latest = debt.get("latest_value")
        primary_col = debt.get("primary_col", "")
        is_ratio = any(kw in primary_col.lower() for kw in ["ratio", "gdp", "percent"])

        if gdp_growth_val is not None and gdp_growth_val > 2 and debt_trend == "decreasing":
            narrative = (
                f"The growth-debt dynamic is favourable: GDP growth of {s(gdp_growth_val)}% "
                f"is driving a declining debt trajectory (trend: {debt_trend}). "
                f"{'At ' + s(debt_latest) + '% of GDP, ' if is_ratio else ''}"
                f"the denominator effect of growth is working to improve sustainability ratios. "
                f"This virtuous circle should be reinforced through continued structural reform."
            )
            strength = "favourable"
        elif gdp_growth_val is not None and gdp_growth_val < 1 and debt_trend == "increasing":
            narrative = (
                f"A concerning adverse loop is emerging: weak GDP growth ({s(gdp_growth_val)}%) "
                f"is coinciding with rising debt levels. "
                f"{'At ' + s(debt_latest) + '% of GDP, ' if is_ratio else ''}"
                f"the debt-growth dynamic risks becoming self-reinforcing as fiscal space "
                f"narrows and counter-cyclical policy options diminish."
            )
            strength = "adverse"
        else:
            narrative = (
                f"The growth-debt relationship is in a transitional phase. GDP growth of "
                f"{s(gdp_growth_val)}% alongside a {debt_trend} debt trajectory suggests "
                f"that sustainability depends critically on maintaining current fiscal "
                f"discipline and avoiding growth shocks."
            )
            strength = "transitional"
        relationships.append(
            {
                "name": "Debt Sustainability-Growth Dynamic",
                "pillars": ["public_debt", "gdp"],
                "narrative": narrative,
                "relationship_strength": strength,
            }
        )

    # Macro narrative synthesis
    macro_narrative = synthesise_macro_narrative(summaries, relationships, db_path)

    return {
        "relationships": relationships,
        "macro_narrative": macro_narrative,
    }


def synthesise_macro_narrative(summaries: dict, relationships: list, db_path: str) -> str:
    """Build a data-driven macro narrative structured as a 3-act story.

    Uses actual data points from the database to construct a concrete,
    evidence-based strategic narrative rather than generic templates.

    Parameters
    ----------
    summaries : dict
        Pillar data summaries.
    relationships : list
        Cross-pillar relationship dicts.
    db_path : str
        Path to the SQLite database.
    """
    s = _safe
    parts = []

    # --- Pull key data points directly from DB for accuracy ---
    conn = sqlite3.connect(db_path)
    try:

        def _q(sql):
            r = conn.execute(sql).fetchone()
            return r[0] if r else None

        latest_unemp = _q(
            "SELECT unemployment_rate FROM fact_unemployment f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "ORDER BY d.year DESC, d.month DESC LIMIT 1"
        )
        latest_debt = _q(
            "SELECT debt_to_gdp_ratio FROM fact_public_debt f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "ORDER BY d.year DESC, d.quarter DESC LIMIT 1"
        )
        latest_deficit = _q(
            "SELECT budget_deficit FROM fact_public_debt f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "ORDER BY d.year DESC, d.quarter DESC LIMIT 1"
        )
        latest_npl = _q(
            "SELECT npl_ratio FROM fact_credit f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "WHERE npl_ratio IS NOT NULL "
            "ORDER BY d.year DESC, d.month DESC LIMIT 1"
        )
        latest_hicp = _q(
            "SELECT hicp FROM fact_inflation f "
            "JOIN dim_date d ON f.date_key=d.date_key "
            "ORDER BY d.year DESC, d.month DESC LIMIT 1"
        )
        peak_unemp = _q("SELECT MAX(unemployment_rate) FROM fact_unemployment")
        peak_debt = _q("SELECT MAX(debt_to_gdp_ratio) FROM fact_public_debt")
    finally:
        conn.close()

    # --- Act 1: Crisis and Adjustment (2010-2014) ---
    parts.append(
        "ACT 1 - CRISIS AND ADJUSTMENT (2010-2014): "
        "Portugal entered the decade under severe macroeconomic stress. "
        f"Unemployment peaked at {s(peak_unemp)}%, "
        f"the debt-to-GDP ratio climbed to {s(peak_debt)}%, "
        "and sovereign bond yields exceeded 10% as markets priced in default risk. "
        "The EU/IMF bailout programme imposed fiscal consolidation that contracted "
        "the economy but laid the foundations for structural reform."
    )

    # --- Act 2: Organic Recovery (2015-2019) ---
    parts.append(
        "ACT 2 - ORGANIC RECOVERY (2015-2019): "
        "Portugal achieved a rare combination: declining unemployment, "
        "falling debt ratios, and a budget surplus in 2019 - the first in Portuguese "
        "democratic history. The sovereign spread normalised to near-zero, "
        "the banking system began its NPL cleanup, and GDP growth consistently "
        "outpaced the eurozone average."
    )

    # --- Act 3: Resilience and Convergence (2020-2025) ---
    parts.append(
        "ACT 3 - RESILIENCE AND CONVERGENCE (2020-2025): "
        "The COVID shock caused a sharp but temporary contraction. "
        "The recovery was swift: real GDP surpassed pre-pandemic levels by 2022. "
        f"By 2025, unemployment stands at {s(latest_unemp)}% (near EU average), "
        f"debt-to-GDP has fallen to {s(latest_debt)}% (below 100% for the first time "
        f"since 2011), and the budget balance shows a surplus of {s(latest_deficit)}% of GDP. "
        f"The NPL ratio at {s(latest_npl)}% confirms a clean banking system."
    )

    # --- Forward risks ---
    risk_signals = []
    if latest_npl is not None and latest_npl < 3:
        risk_signals.append("credit complacency (NPL at historic lows may mask emerging risks)")
    if latest_hicp is not None and latest_hicp > 2.0:
        risk_signals.append(
            f"inflation persistence ({s(latest_hicp)}% still above the ECB 2% target)"
        )
    risk_signals.append("the productivity gap (GDP per capita remains ~70% of the EU average)")

    parts.append(
        "FORWARD RISKS: Despite the structural improvement, Portugal faces "
        + ", ".join(risk_signals)
        + ". "
        "The era of easy growth (crisis recovery plus inflation-driven nominal expansion) "
        "is ending. Future growth must come from productivity gains, not cyclical tailwinds."
    )

    # --- Strategic implication ---
    parts.append(
        "STRATEGIC IMPLICATION: Portugal has completed a fundamental transformation "
        "from bailout recipient to fiscally credible eurozone member. The policy priority "
        "must now shift from stabilisation to sustained convergence - investing the fiscal "
        "surplus in human capital, digitalisation, and innovation rather than consuming it."
    )

    return "\n\n".join(parts)
