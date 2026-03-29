"""
Portugal Data Intelligence - Pillar-Specific Rule-Based Insights
=================================================================
Generates executive-level narrative commentary for each macroeconomic
pillar using a template-method pattern.

Each pillar defines its specific thresholds and text templates via a
configuration dict, while the common logic lives in ``_build_insight``.
"""

from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Safe formatting helper
# ---------------------------------------------------------------------------


def _safe(value, fmt: str = ".1f") -> str:
    """Format a numeric value safely, returning 'N/A' on failure."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):{fmt}}"
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# Common narrative builders (shared across all pillars)
# ---------------------------------------------------------------------------


def _classify_crisis_impact(mean_growth, longrun, label: str, mode: str = "growth") -> str:
    """Return a qualitative description of a crisis period's impact."""
    if mode == "growth":
        if mean_growth is not None and mean_growth < 0:
            return "significant economic stress"
        if mean_growth is not None and longrun is not None:
            if mean_growth > longrun + 0.5:
                return "resilience"
            if mean_growth < longrun - 0.5:
                return "significant stress"
    elif mode == "level":
        if mean_growth is not None and longrun is not None:
            if mean_growth > longrun + 1:
                return "reflecting significant stress"
            if mean_growth < longrun - 1:
                return "demonstrating resilience"
    return "performance broadly in line with the overall trend"


def _build_crisis_findings(d: dict, mode: str = "growth") -> List[str]:
    """Generate findings lines for each crisis period."""
    s = _safe
    longrun = d.get("longrun_avg_growth")
    findings = []
    for _ck, ci in d.get("crisis_impacts", {}).items():
        label = ci["label"]
        if mode == "growth":
            mg = ci.get("mean_growth")
            impact = _classify_crisis_impact(mg, longrun, label, mode="growth")
            findings.append(
                f"During the {label}, average growth was {s(mg)}%, indicating {impact}."
            )
        else:
            mean_v = ci.get("mean_value")
            findings.append(f"The {label} drove the indicator to an average of {s(mean_v)}.")
    return findings


def _select_by_threshold(
    value: Optional[float],
    thresholds: List[Tuple[Any, str]],
    default: str = "",
) -> str:
    """Pick the first matching template from a list of (condition_fn, template) pairs."""
    if value is None:
        return default
    for condition_fn, template in thresholds:
        if condition_fn(value):
            return template
    return default


# ---------------------------------------------------------------------------
# Pillar configurations — thresholds and templates
# ---------------------------------------------------------------------------

_GDP_CONFIG = {
    "headline_thresholds": [
        (lambda g: g > 3, "Robust economic expansion: Portugal's GDP grew {growth}% in {year}"),
        (lambda g: g > 1, "Moderate growth sustained: GDP advanced {growth}% in {year}"),
        (lambda g: g > 0, "Growth momentum fading: GDP expanded just {growth}% in {year}"),
        (lambda g: True, "Economic contraction: GDP declined {growth}% in {year}"),
    ],
    "risk_thresholds": [
        (
            lambda v, r: v is not None and v < 0,
            "HIGH RISK. The economy contracted by {abs_growth}% in {year}. Negative growth "
            "trajectories, if sustained, can trigger adverse feedback loops through employment, "
            "fiscal revenues, and credit quality. Immediate policy attention is warranted.",
        ),
        (
            lambda v, r: r is not None and r < 1,
            "ELEVATED RISK. Average growth over the past three years ({recent}%) is below the "
            "threshold needed to meaningfully reduce unemployment or stabilise public finances. "
            "The economy is vulnerable to external shocks.",
        ),
        (
            lambda v, r: r is not None and r > 3,
            "LOW RISK with OVERHEATING WATCH. Strong recent growth ({recent}%) may generate "
            "inflationary pressures or asset price imbalances. Monitor capacity utilisation "
            "and labour market tightness.",
        ),
        (
            lambda v, r: True,
            "MODERATE RISK. Growth is positive but not sufficiently above trend to provide a "
            "substantial buffer against downside scenarios. Vigilance on external demand "
            "conditions and structural bottlenecks is recommended.",
        ),
    ],
    "recommendations": {
        "low_growth": [
            "Accelerate implementation of the Recovery and Resilience Plan (PRR) to "
            "boost public investment and crowd in private capital.",
            "Consider targeted fiscal stimulus measures focused on productivity-enhancing "
            "sectors, including digital transformation and green transition.",
        ],
        "high_growth": [
            "Monitor capacity constraints and labour shortages that could bottleneck "
            "growth and push inflation above the ECB target.",
        ],
        "always": [
            "Strengthen export diversification to reduce dependence on tourism and "
            "European demand cycles.",
            "Prioritise human capital development through vocational training alignment "
            "with high-growth sectors (technology, renewable energy, advanced manufacturing).",
        ],
    },
}

_UNEMPLOYMENT_CONFIG = {
    "headline_thresholds": [
        (lambda v: v < 7, "Labour market strength: unemployment at {latest}% in {year}"),
        (
            lambda v: v < 10,
            "Moderate labour market conditions: unemployment at {latest}% in {year}",
        ),
        (lambda v: v < 14, "Elevated unemployment persists at {latest}% in {year}"),
        (lambda v: True, "Critical unemployment: rate at {latest}% in {year}"),
    ],
    "risk_thresholds": [
        (
            lambda v, _r: v > 12,
            "HIGH RISK. Unemployment at {latest}% remains critically elevated, creating "
            "significant social costs and constraining consumer demand. Long-term "
            "unemployment hysteresis is a concern.",
        ),
        (
            lambda v, _r: v > 8,
            "ELEVATED RISK. At {latest}%, the labour market has not fully normalised. "
            "Structural unemployment components may resist cyclical recovery, "
            "requiring targeted intervention.",
        ),
        (
            lambda v, _r: True,
            "MODERATE RISK. Unemployment at {latest}% indicates a healthy labour market, "
            "though tightness may generate wage pressures. Monitor for skills gaps and "
            "regional imbalances that could constrain further improvement.",
        ),
    ],
    "recommendations": {
        "always": [
            "Expand vocational training and reskilling programmes aligned with digital and green economy demands.",
            "Strengthen active labour market policies, particularly for youth and long-term unemployed cohorts.",
            "Address regional disparities through incentives for investment in higher-unemployment interior regions.",
        ],
        "high_unemployment": [
            "Consider temporary employment subsidies for sectors with highest job-creation potential.",
        ],
        "low_unemployment": [
            "Focus on quality of employment metrics, including contract types, wage growth, "
            "and productivity per worker, to ensure sustainable labour market outcomes.",
        ],
    },
}

_CREDIT_CONFIG = {
    "risk_thresholds": [
        (
            lambda t, r: t == "decreasing" and (r is None or r < 0),
            "HIGH RISK. Continued credit contraction signals impaired monetary policy "
            "transmission and potential credit rationing. Small and medium enterprises "
            "may face financing constraints that inhibit investment and growth.",
        ),
        (
            lambda t, r: t == "decreasing",
            "ELEVATED RISK. Although the pace of credit decline has moderated, the "
            "overall contracting trend indicates lingering balance sheet repair needs "
            "in the banking sector. Credit availability remains a potential bottleneck.",
        ),
        (
            lambda t, r: True,
            "MODERATE RISK. Credit conditions appear to be normalising. The primary "
            "risk lies in the quality of new lending and the adequacy of credit growth "
            "to support the economy's investment needs without rebuilding excessive leverage.",
        ),
    ],
    "recommendations": [
        "Monitor credit quality metrics closely, ensuring that credit expansion does not compromise underwriting standards.",
        "Support SME access to finance through guarantee programmes and development bank co-lending facilities.",
        "Encourage diversification of corporate financing toward capital markets and alternative lending platforms.",
        "Assess the effectiveness of ECB monetary policy transmission through Portuguese banking channels.",
    ],
}

_INTEREST_RATES_CONFIG = {
    "headline_thresholds": [
        (lambda v: v < 1, "Ultra-low rate environment: primary rate at {latest}% in {year}"),
        (lambda v: v < 3, "Rate normalisation underway: primary rate at {latest}% in {year}"),
        (lambda v: v > 5, "Elevated rate environment: primary rate at {latest}% in {year}"),
        (lambda v: True, "Interest rates at {latest}%: monetary conditions tightening in {year}"),
    ],
    "risk_thresholds": [
        (
            lambda v, _r: v > 4,
            "HIGH RISK. Elevated interest rates at {latest}% pose significant challenges "
            "for Portugal's debt-servicing capacity, mortgage holders, and corporate "
            "investment. The risk of financial stress in rate-sensitive sectors is material.",
        ),
        (
            lambda v, _r: v > 2,
            "ELEVATED RISK. Rate normalisation to {latest}% creates adjustment pressures "
            "across the economy, particularly for borrowers who accumulated debt during "
            "the low-rate period. Monitoring of household and corporate debt-service "
            "ratios is essential.",
        ),
        (
            lambda v, _r: v < 0.5,
            "MODERATE RISK (unusual conditions). Near-zero rates at {latest}% support "
            "borrowing costs but signal underlying economic weakness. Risks include "
            "misallocation of capital, compressed bank margins, and future adjustment "
            "costs when rates eventually normalise.",
        ),
        (
            lambda v, _r: True,
            "MODERATE RISK. The current rate of {latest}% represents a transitional "
            "monetary environment. Key risks include the pace and magnitude of future "
            "rate adjustments and their differential impact across economic sectors.",
        ),
    ],
    "recommendations": [
        "Conduct stress testing of public and private debt portfolios against further rate increases of 100-200 basis points.",
        "Encourage fixed-rate mortgage and lending products to reduce economy-wide exposure to rate volatility.",
        "Monitor the sovereign spread relative to euro area benchmarks as an early warning indicator for market confidence.",
        "Assess the impact of rate changes on bank profitability and lending capacity in the Portuguese banking sector.",
    ],
}

_INFLATION_CONFIG = {
    "headline_thresholds": [
        (lambda v: v > 5, "Inflationary surge: headline rate at {latest}% in {year}"),
        (
            lambda v: v > 3,
            "Above-target inflation: rate at {latest}% exceeds ECB 2% objective in {year}",
        ),
        (
            lambda v: v > 1.5,
            "Inflation near target: rate at {latest}% consistent with price stability in {year}",
        ),
        (lambda v: v > 0, "Low inflation environment: rate at {latest}% in {year}"),
        (lambda v: True, "Deflationary risk: inflation at {latest}% in {year}"),
    ],
    "risk_thresholds": [
        (
            lambda v, _r: v > 5,
            "HIGH RISK. Inflation at {latest}% is significantly above the ECB's 2% target, "
            "eroding purchasing power and creating uncertainty for investment decisions. "
            "Second-round effects through wage-price spirals are a material concern.",
        ),
        (
            lambda v, _r: v > 3,
            "ELEVATED RISK. Above-target inflation at {latest}% is squeezing real incomes "
            "and may prompt further ECB tightening. Portugal's competitiveness could be "
            "affected if domestic inflation persistently exceeds the euro area average.",
        ),
        (
            lambda v, _r: v < 0.5,
            "ELEVATED RISK (deflation). With inflation at {latest}%, the risk of "
            "deflationary expectations becoming entrenched is non-trivial. Low inflation "
            "also increases the real burden of debt, complicating fiscal consolidation.",
        ),
        (
            lambda v, _r: True,
            "LOW-TO-MODERATE RISK. Inflation at {latest}% is broadly consistent with "
            "price stability. The primary risk is an unexpected acceleration driven by "
            "energy prices, supply chain disruptions, or domestic wage pressures.",
        ),
    ],
    "recommendations": [
        "Monitor wage settlement patterns for signs of second-round effects that could entrench above-target inflation.",
        "Assess the distributional impact of inflation on lower-income households and consider targeted support measures.",
        "Evaluate the effectiveness of ECB monetary policy transmission to Portuguese consumer prices.",
        "Track core inflation divergence from the euro area average as an indicator of competitiveness dynamics.",
    ],
}

_PUBLIC_DEBT_CONFIG = {
    "risk_thresholds_ratio": [
        (
            lambda v, _r: v > 120,
            "HIGH RISK. Debt-to-GDP at {latest}% significantly exceeds the 60% Maastricht "
            "threshold and the euro area average. Portugal remains vulnerable to interest "
            "rate shocks, growth disappointments, and shifts in market sentiment. "
            "Sovereign rating downgrades could trigger adverse feedback through bank "
            "balance sheets.",
        ),
        (
            lambda v, _r: v > 90,
            "ELEVATED RISK. At {latest}% of GDP, public debt constrains fiscal policy "
            "space and carries refinancing risk in a rising rate environment. The "
            "debt-growth-interest rate dynamic must remain favourable to prevent "
            "a self-reinforcing upward spiral.",
        ),
        (
            lambda v, _r: v > 60,
            "MODERATE RISK. Debt at {latest}% of GDP exceeds the Maastricht reference "
            "but is on a manageable path if current fiscal discipline is maintained. "
            "The primary risk is an external shock that reverses consolidation progress.",
        ),
        (
            lambda v, _r: True,
            "MODERATE RISK. Public debt levels are within manageable bounds. Continued "
            "prudent fiscal management is necessary to maintain this position and build "
            "counter-cyclical buffers.",
        ),
    ],
    "recommendations": [
        "Maintain primary budget surpluses to ensure a declining debt trajectory, targeting a debt-to-GDP path below 100% within the medium-term fiscal framework.",
        "Extend the average maturity of public debt issuance to reduce rollover risk and lock in favourable financing conditions.",
        "Implement structural spending reviews to identify efficiency gains that support consolidation without compromising public investment.",
        "Develop contingency fiscal plans for adverse scenarios (growth shock, rate spike) to demonstrate institutional preparedness to markets and rating agencies.",
    ],
}


# ---------------------------------------------------------------------------
# Template-based insight builders
# ---------------------------------------------------------------------------


def _build_headline(
    value: Optional[float], thresholds: list, fmt_kwargs: dict, default: str
) -> str:
    """Select headline from threshold list and format with kwargs."""
    if value is None:
        return default
    for condition_fn, template in thresholds:
        if condition_fn(value):
            return template.format(**fmt_kwargs)
    return default


def _build_risk(value: float, recent: Optional[float], thresholds: list, fmt_kwargs: dict) -> str:
    """Select risk assessment from threshold list."""
    for condition_fn, template in thresholds:
        if condition_fn(value, recent):
            return template.format(**fmt_kwargs)
    return "MODERATE RISK. Further analysis required."


def _build_base_findings(d: dict) -> List[str]:
    """Generate the universal first 3 findings for any pillar."""
    s = _safe
    change = d["overall_change_pct"]
    return [
        f"Overall {'expansion' if change > 0 else 'contraction'} of {s(abs(change))}% from {d['earliest_year']} to {d['latest_year']}.",
        f"Peak: {s(d['peak_value'])} in {d['peak_year']}; Trough: {s(d['trough_value'])} in {d['trough_year']}.",
        f"Long-run average growth: {s(d.get('longrun_avg_growth'))}%; recent 3-year average: {s(d.get('recent_avg_growth'))}%.",
    ]


def _build_momentum_paragraph(d: dict) -> str:
    """Build a paragraph comparing recent momentum to long-run average."""
    s = _safe
    recent = d.get("recent_avg_growth")
    longrun = d.get("longrun_avg_growth")
    if recent is not None and longrun is not None:
        gap = recent - longrun
        if gap > 1:
            return (
                f"Recent momentum has been notably above trend, with the three-year average "
                f"growth rate of {s(recent)}% exceeding the long-run mean of {s(longrun)}% "
                f"by {s(gap)} percentage points. This above-trend expansion should be "
                f"assessed for sustainability."
            )
        elif gap < -1:
            return (
                f"The recent three-year average growth of {s(recent)}% trails the historical "
                f"mean of {s(longrun)}% by {s(abs(gap))} percentage points, indicating "
                f"a loss of momentum that may require policy attention."
            )
        else:
            return (
                f"Recent growth of {s(recent)}% is broadly aligned with the long-run average "
                f"of {s(longrun)}%, suggesting the economy is operating near its potential "
                f"growth trajectory."
            )
    return "Insufficient historical data to assess recent momentum against long-run trends."


def _build_crisis_narrative(d: dict, mode: str = "growth", context: str = "") -> str:
    """Build a paragraph summarising crisis period impacts."""
    s = _safe
    longrun = d.get("longrun_avg_growth")
    parts = []
    for _ck, ci in d.get("crisis_impacts", {}).items():
        label = ci["label"]
        if mode == "growth":
            mg = ci.get("mean_growth")
            impact = _classify_crisis_impact(mg, longrun, label, mode="growth")
            parts.append(f"The {label} period saw average growth of {s(mg)}%, indicating {impact}.")
        else:
            mean_v = ci.get("mean_value")
            max_v = ci.get("max_value")
            parts.append(
                f"During the {label}, the indicator averaged {s(mean_v)} "
                f"and reached {s(max_v)} at its peak."
            )
    if not parts:
        return (
            f"Over the full observation window, the primary measure moved from "
            f"{s(d['earliest_value'])} to {s(d['latest_value'])}, a cumulative "
            f"change of {s(d['overall_change_pct'])}%."
        )
    return " ".join(parts)


def _add_secondary_findings(d: dict, findings: list, keywords_map: Dict[str, str]) -> List[str]:
    """Append findings from secondary columns based on keyword matching."""
    s = _safe
    for col_name, sec_data in d.get("secondary", {}).items():
        cl = col_name.lower()
        for keyword, template in keywords_map.items():
            if keyword in cl:
                findings.append(
                    template.format(
                        col=col_name,
                        mean=s(sec_data["mean"]),
                        latest=s(sec_data["latest"]),
                        min=s(sec_data["min"]),
                        max=s(sec_data["max"]),
                    )
                )
                break
    return findings[:6]


# ---------------------------------------------------------------------------
# GDP Insight
# ---------------------------------------------------------------------------


def _insight_gdp(d: dict) -> dict:
    s = _safe
    growth = d.get("latest_growth")
    recent = d.get("recent_avg_growth")
    longrun = d.get("longrun_avg_growth")
    latest = d["latest_value"]

    fmt = {
        "growth": s(growth),
        "abs_growth": s(abs(growth)) if growth else "N/A",
        "recent": s(recent),
        "longrun": s(longrun),
        "latest": s(latest),
        "year": d["latest_year"],
    }

    headline = _build_headline(
        growth,
        _GDP_CONFIG["headline_thresholds"],
        fmt,
        default=f"GDP analysis covering {d['earliest_year']}-{d['latest_year']}",
    )

    # Executive summary — 3 paragraphs
    if growth is not None and growth > 3:
        para1 = (
            f"Portugal's economy demonstrated robust expansion in {d['latest_year']}, "
            f"with GDP growing at {s(growth)}% year-on-year. This pace exceeded "
            f"the long-run average of {s(longrun)}%, signalling strengthening momentum."
        )
    elif growth is not None and growth > 1:
        para1 = (
            f"The Portuguese economy maintained moderate growth in {d['latest_year']}, "
            f"posting a {s(growth)}% year-on-year expansion, broadly consistent with "
            f"Portugal's structural growth potential and the long-run average of {s(longrun)}%."
        )
    elif growth is not None and growth > 0:
        para1 = (
            f"Economic growth decelerated in {d['latest_year']}, advancing by just "
            f"{s(growth)}% year-on-year — a notable slowdown relative to the "
            f"long-run average of {s(longrun)}%."
        )
    elif growth is not None:
        para1 = (
            f"Portugal entered a contractionary phase in {d['latest_year']}, with GDP "
            f"declining by {s(abs(growth))}% year-on-year, a significant departure from "
            f"the long-run average growth of {s(longrun)}%."
        )
    else:
        para1 = (
            f"The GDP dataset spans {d['earliest_year']} to {d['latest_year']}, covering "
            f"a period of significant macroeconomic evolution for Portugal."
        )

    para2 = _build_crisis_narrative(d, mode="growth")
    para3 = _build_momentum_paragraph(d)

    # Findings
    findings = _build_base_findings(d) + _build_crisis_findings(d, mode="growth")
    findings = findings[:6]

    # Risk
    risk = _build_risk(growth or 0, recent, _GDP_CONFIG["risk_thresholds"], fmt)

    # Recommendations
    recs = []
    if growth is not None and growth < 1:
        recs.extend(_GDP_CONFIG["recommendations"]["low_growth"])
    if recent is not None and recent > 3:
        recs.extend(_GDP_CONFIG["recommendations"]["high_growth"])
    recs.extend(_GDP_CONFIG["recommendations"]["always"])
    recs = recs[:4]

    # Outlook
    if recent is not None and recent > 2:
        outlook = (
            f"The near-term outlook is cautiously optimistic. With recent growth averaging "
            f"{s(recent)}%, the economy has demonstrated resilience. However, convergence "
            f"toward the EU average requires sustained structural reform. External risks, "
            f"including global trade tensions and energy price volatility, remain key factors."
        )
    elif recent is not None and recent > 0:
        outlook = (
            f"Portugal's GDP growth trajectory is expected to remain modest. The recent "
            f"average of {s(recent)}% suggests limited room for fiscal manoeuvre without "
            f"growth-enhancing reforms. Upside potential exists through EU-funded investment "
            f"programmes and continued tourism sector strength."
        )
    else:
        outlook = (
            "The economic outlook carries significant uncertainty. Recovery will depend on "
            "counter-cyclical policy effectiveness and the pace of external demand normalisation."
        )

    return {
        "pillar": "gdp",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Unemployment Insight
# ---------------------------------------------------------------------------


def _insight_unemployment(d: dict) -> dict:
    s = _safe
    latest = d["latest_value"]
    trend = d["trend"]
    change = d["overall_change_pct"]
    peak = d["peak_value"]
    peak_y = d["peak_year"]
    trough = d["trough_value"]
    trough_y = d["trough_year"]

    fmt = {"latest": s(latest), "year": d["latest_year"], "recent": s(d.get("recent_avg_growth"))}

    headline = _build_headline(
        latest,
        _UNEMPLOYMENT_CONFIG["headline_thresholds"],
        fmt,
        default=f"Unemployment at {s(latest)}% in {d['latest_year']}",
    )

    # Executive summary
    direction = (
        "declined"
        if trend == "decreasing"
        else "increased" if trend == "increasing" else "remained broadly stable"
    )
    pp_change = abs(latest - d["earliest_value"])  # actual percentage point difference
    para1 = (
        f"Portugal's labour market has undergone significant transformation over "
        f"{d['earliest_year']}-{d['latest_year']}. The unemployment rate {direction} "
        f"from {s(d['earliest_value'])}% to {s(latest)}%, representing a "
        f"{s(pp_change)} percentage point {'improvement' if change < 0 else 'deterioration'}."
    )

    # Crisis impacts
    overall_mean = d.get("mean")
    crisis_text = []
    for _ck, ci in d.get("crisis_impacts", {}).items():
        mean_v = ci.get("mean_value")
        max_v = ci.get("max_value")
        if mean_v is not None and overall_mean is not None and mean_v > overall_mean + 1:
            tone = "reflecting significant stress on the labour market"
        elif mean_v is not None and overall_mean is not None and mean_v < overall_mean - 1:
            tone = "demonstrating labour market resilience"
        else:
            tone = "broadly in line with the overall trend"
        crisis_text.append(
            f"During the {ci['label']}, unemployment averaged {s(mean_v)}% and peaked at "
            f"{s(max_v)}%, {tone}."
        )
    para2 = (
        " ".join(crisis_text)
        if crisis_text
        else (
            f"Unemployment peaked at {s(peak)}% in {peak_y} before declining to {s(trough)}% in {trough_y}."
        )
    )

    if latest <= trough * 1.1:
        para3 = (
            f"The current rate of {s(latest)}% is near historical lows, indicating "
            f"substantial labour market recovery. However, structural issues including "
            f"skills mismatches and regional disparities continue to require policy attention."
        )
    else:
        para3 = (
            f"At {s(latest)}%, unemployment remains {s(latest - trough)} percentage points "
            f"above the period low of {s(trough)}% ({trough_y}). Further improvement will "
            f"require continued economic expansion and targeted active labour market policies."
        )

    # Findings
    findings = [
        f"Unemployment {'fell' if change < 0 else 'rose'} by {s(pp_change)} percentage points over the full period.",
        f"Peak: {s(peak)}% in {peak_y}; Trough: {s(trough)}% in {trough_y}.",
        f"Overall trend classified as {trend}.",
    ]
    findings = _add_secondary_findings(
        d,
        findings,
        {
            "youth": "Youth unemployment averaged {mean}%, latest reading: {latest}% — highlighting persistent generational disparity.",
        },
    )
    for _ck, ci in d.get("crisis_impacts", {}).items():
        findings.append(
            f"The {ci['label']} drove unemployment to an average of {s(ci.get('mean_value'))}%."
        )
    findings = findings[:6]

    # Risk
    risk = _build_risk(latest, None, _UNEMPLOYMENT_CONFIG["risk_thresholds"], fmt)

    # Recommendations
    recs = list(_UNEMPLOYMENT_CONFIG["recommendations"]["always"])
    if latest > 10:
        recs.extend(_UNEMPLOYMENT_CONFIG["recommendations"]["high_unemployment"])
    else:
        recs.extend(_UNEMPLOYMENT_CONFIG["recommendations"]["low_unemployment"])

    # Outlook
    if trend == "decreasing" and latest < 8:
        outlook = (
            "The labour market outlook is positive. The downward unemployment trend is "
            "expected to continue, supported by economic growth and tourism sector resilience. "
            "However, demographic pressures and emigration may tighten labour supply."
        )
    elif trend == "decreasing":
        outlook = (
            "The declining trajectory is encouraging, though improvement may slow as the "
            "economy approaches its natural rate. Focus should shift from job creation "
            "volume to job quality and productivity enhancement."
        )
    else:
        outlook = (
            "The labour market faces headwinds. Without sustained GDP growth above 2%, "
            "material unemployment reduction will be difficult. Policy coordination between "
            "education, industry, and employment services will be critical."
        )

    return {
        "pillar": "unemployment",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Credit Insight
# ---------------------------------------------------------------------------


def _insight_credit(d: dict) -> dict:
    s = _safe
    latest = d["latest_value"]
    trend = d["trend"]
    change = d["overall_change_pct"]
    recent = d.get("recent_avg_growth")
    longrun = d.get("longrun_avg_growth")

    # Headline
    if trend == "decreasing":
        headline = (
            f"Credit contraction: lending declined {s(abs(change))}% over the analysis period"
        )
    elif recent is not None and recent > 3:
        headline = f"Credit expansion accelerates: recent growth averaging {s(recent)}% annually"
    else:
        headline = f"Credit conditions stabilise: latest balance at {s(latest, '.0f')} EUR million"

    para1 = (
        f"Credit to the Portuguese economy has exhibited a {trend} trajectory over "
        f"{d['earliest_year']}-{d['latest_year']}. Total outstanding credit moved from "
        f"{s(d['earliest_value'], '.0f')} to {s(latest, '.0f')} EUR million, a cumulative "
        f"change of {s(change)}%. This evolution reflects deleveraging pressures following "
        f"the sovereign debt crisis, regulatory tightening, and subsequent normalisation."
    )

    para2 = _build_crisis_narrative(d, mode="growth")

    if recent is not None and longrun is not None:
        if recent > longrun:
            para3 = (
                f"Recent credit dynamics ({s(recent)}% average growth) show improvement "
                f"relative to the long-run average ({s(longrun)}%), suggesting the "
                f"deleveraging cycle may be approaching completion."
            )
        else:
            para3 = (
                f"Despite accommodative monetary conditions, recent credit growth ({s(recent)}%) "
                f"remains below the long-run average ({s(longrun)}%), indicating persistent "
                f"structural headwinds in lending."
            )
    else:
        para3 = "Credit market data suggests gradual normalisation of lending conditions."

    findings = _build_base_findings(d)
    findings = _add_secondary_findings(
        d,
        findings,
        {
            "npl": "NPL indicator ({col}) averaged {mean}%, latest: {latest}%.",
            "non_performing": "NPL indicator ({col}) averaged {mean}%, latest: {latest}%.",
            "household": "Segment '{col}' latest: {latest}, mean: {mean}.",
            "nfc": "Segment '{col}' latest: {latest}, mean: {mean}.",
        },
    )

    risk = _build_risk(trend, recent, _CREDIT_CONFIG["risk_thresholds"], {"latest": s(latest)})

    recs = list(_CREDIT_CONFIG["recommendations"])

    if trend == "increasing" and recent is not None and recent > 3:
        outlook = (
            "Credit conditions are expected to remain supportive, with lending growth "
            "likely to moderate toward a sustainable pace as the ECB adjusts monetary policy."
        )
    else:
        outlook = (
            "The credit outlook remains cautious. While banking fundamentals have improved "
            "since the sovereign debt crisis, structural challenges including consolidation "
            "pressures and digital transformation costs may constrain lending capacity."
        )

    return {
        "pillar": "credit",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Interest Rates Insight
# ---------------------------------------------------------------------------


def _insight_interest_rates(d: dict) -> dict:
    s = _safe
    latest = d["latest_value"]
    trend = d["trend"]
    peak = d["peak_value"]
    peak_y = d["peak_year"]
    trough = d["trough_value"]
    trough_y = d["trough_year"]

    fmt = {"latest": s(latest), "year": d["latest_year"]}

    headline = _build_headline(
        latest,
        _INTEREST_RATES_CONFIG["headline_thresholds"],
        fmt,
        default=f"Interest rates at {s(latest)}% in {d['latest_year']}",
    )

    para1 = (
        f"The interest rate environment in Portugal has been shaped by extraordinary "
        f"monetary policy cycles over {d['earliest_year']}-{d['latest_year']}. "
        f"The primary rate moved from {s(d['earliest_value'])}% to {s(latest)}%, "
        f"reflecting the ECB's response to successive crises and subsequent normalisation."
    )

    # Sovereign spread commentary
    spread_text = ""
    for col_name, sec_data in d.get("secondary", {}).items():
        cl = col_name.lower()
        if any(kw in cl for kw in ("spread", "sovereign", "bond", "yield")):
            spread_text = (
                f" Portuguese sovereign yields ({col_name}) averaged {s(sec_data['mean'])}%, "
                f"latest at {s(sec_data['latest'])}%."
            )
            break

    para2 = (
        f"Rates peaked at {s(peak)}% in {peak_y}, reflecting crisis-era risk premia, "
        f"before declining to {s(trough)}% in {trough_y} under ECB accommodative "
        f"measures.{spread_text}"
    )

    para3 = (
        f"The current rate of {s(latest)}% must be assessed in the context of the ECB's "
        f"inflation mandate. For Portugal, the transmission to lending conditions, "
        f"mortgage costs, and sovereign debt servicing requires careful monitoring."
    )

    findings = [
        f"Primary rate moved from {s(d['earliest_value'])}% to {s(latest)}% over the period.",
        f"Peak: {s(peak)}% in {peak_y}; Trough: {s(trough)}% in {trough_y}.",
        f"Overall trend classified as {trend}.",
    ]
    findings = _add_secondary_findings(
        d,
        findings,
        {
            "": "{col}: mean {mean}%, range [{min}% - {max}%], latest {latest}%.",
        },
    )

    risk = _build_risk(latest, None, _INTEREST_RATES_CONFIG["risk_thresholds"], fmt)
    recs = list(_INTEREST_RATES_CONFIG["recommendations"])

    if trend == "increasing":
        outlook = (
            f"Rates are expected to remain influenced by ECB decisions. At {s(latest)}%, "
            f"the critical question is whether Portugal can absorb higher financing costs "
            f"without triggering adverse feedback through the sovereign-bank-corporate nexus."
        )
    else:
        outlook = (
            "The accommodative environment may persist if inflation remains subdued, "
            "but policy normalisation represents a significant medium-term adjustment risk. "
            "Portugal should use this window to reduce debt and strengthen fiscal buffers."
        )

    return {
        "pillar": "interest_rates",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Inflation Insight
# ---------------------------------------------------------------------------


def _insight_inflation(d: dict) -> dict:
    s = _safe
    latest = d["latest_value"]
    trend = d["trend"]
    mean_val = d["mean"]
    peak = d["peak_value"]
    peak_y = d["peak_year"]
    trough = d["trough_value"]
    trough_y = d["trough_year"]

    fmt = {"latest": s(latest), "year": d["latest_year"]}

    headline = _build_headline(
        latest,
        _INFLATION_CONFIG["headline_thresholds"],
        fmt,
        default=f"Inflation at {s(latest)}% in {d['latest_year']}",
    )

    para1 = (
        f"Portugal's inflation dynamics over {d['earliest_year']}-{d['latest_year']} "
        f"reflect the broader European experience. Headline inflation averaged "
        f"{s(mean_val)}% per annum, moving from {s(d['earliest_value'])}% to {s(latest)}%. "
        f"The trend is classified as {trend}, with significant variation driven by "
        f"external shocks, energy prices, and monetary policy transmission."
    )

    # Crisis impacts
    crisis_parts = []
    for ck, ci in d.get("crisis_impacts", {}).items():
        mean_v = ci.get("mean_value")
        label = ci["label"]
        if "energy" in ck.lower() or "covid" in ck.lower():
            crisis_parts.append(
                f"The {label} had a pronounced impact on prices, with inflation averaging "
                f"{s(mean_v)}% during the period."
            )
        else:
            crisis_parts.append(
                f"During the {label}, inflation averaged {s(mean_v)}%, "
                f"{'with disinflationary pressures dominating' if mean_v is not None and mean_v < 1 else 'reflecting cost-push factors'}."
            )
    para2 = (
        " ".join(crisis_parts)
        if crisis_parts
        else (f"Inflation peaked at {s(peak)}% in {peak_y} and reached {s(trough)}% in {trough_y}.")
    )

    # Core vs headline
    core_text = ""
    for col_name, sec_data in d.get("secondary", {}).items():
        if "core" in col_name.lower():
            core_text = (
                f"Core inflation (excluding energy and food) averaged {s(sec_data['mean'])}%, "
                f"with a latest reading of {s(sec_data['latest'])}%. The gap between headline "
                f"and core measures indicates the persistence of price pressures."
            )
            break
    para3 = core_text or (
        f"The current inflation rate of {s(latest)}% must be assessed against the ECB's "
        f"2% target and in light of second-round effects from wage negotiations."
    )

    findings = [
        f"Average inflation: {s(mean_val)}% over the full period.",
        f"Peak: {s(peak)}% in {peak_y}; Minimum: {s(trough)}% in {trough_y}.",
        f"Trend classified as {trend}.",
    ]
    findings = _add_secondary_findings(
        d,
        findings,
        {
            "core": "{col} averaged {mean}%, latest: {latest}%.",
            "cpi_estimated": "{col} averaged {mean}%, latest: {latest}%.",
        },
    )

    risk = _build_risk(latest, None, _INFLATION_CONFIG["risk_thresholds"], fmt)
    recs = list(_INFLATION_CONFIG["recommendations"])

    if latest > 3:
        outlook = (
            "Inflation is expected to moderate as energy base effects diminish and "
            "monetary tightening works through the economy. Services inflation and wage "
            "dynamics in tourism will be key determinants of the medium-term path."
        )
    elif latest < 1:
        outlook = (
            "Low inflation may persist if demand remains subdued. Structural factors "
            "including globalisation and demographics could keep price pressures muted."
        )
    else:
        outlook = (
            "The inflation outlook is balanced. Near-target inflation provides a stable "
            "environment for planning. Principal uncertainties are external: energy markets, "
            "global supply chains, and ECB monetary policy calibration."
        )

    return {
        "pillar": "inflation",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Public Debt Insight
# ---------------------------------------------------------------------------


def _insight_public_debt(d: dict) -> dict:
    s = _safe
    latest = d["latest_value"]
    trend = d["trend"]
    change = d["overall_change_pct"]
    peak = d["peak_value"]
    peak_y = d["peak_year"]
    trough = d["trough_value"]
    trough_y = d["trough_year"]
    primary_col = d.get("primary_col", "")

    is_ratio = any(kw in primary_col.lower() for kw in ("ratio", "gdp", "percent"))
    unit = "% of GDP" if is_ratio else "EUR million"
    vfmt = ".1f" if is_ratio else ".0f"

    # Headline
    if is_ratio:
        if latest > 120:
            headline = f"Debt sustainability concern: public debt at {s(latest)}% of GDP in {d['latest_year']}"
        elif latest > 100:
            headline = f"Elevated public debt: ratio at {s(latest)}% of GDP in {d['latest_year']}"
        elif latest > 60:
            headline = f"Debt above Maastricht threshold: {s(latest)}% of GDP in {d['latest_year']}"
        else:
            headline = f"Public debt within benchmark: {s(latest)}% of GDP in {d['latest_year']}"
    else:
        headline = f"Public debt at {s(latest, '.0f')} {unit} in {d['latest_year']}"

    para1 = (
        f"Portugal's public debt trajectory over {d['earliest_year']}-{d['latest_year']} "
        f"has been a defining challenge of the macroeconomic framework. The primary measure "
        f"moved from {s(d['earliest_value'], vfmt)} to {s(latest, vfmt)} {unit}, "
        f"a cumulative change of {s(change)}%, shaped by the sovereign debt crisis, "
        f"austerity programmes, and post-crisis recovery dynamics."
    )

    crisis_parts = []
    for _ck, ci in d.get("crisis_impacts", {}).items():
        mean_v = ci.get("mean_value")
        max_v = ci.get("max_value")
        crisis_parts.append(
            f"During the {ci['label']}, debt averaged {s(mean_v, vfmt)} {unit}, "
            f"reaching {s(max_v, vfmt)} at its peak."
        )
    para2 = (
        " ".join(crisis_parts)
        if crisis_parts
        else (
            f"Debt peaked at {s(peak, vfmt)} {unit} in {peak_y}, before "
            f"{'declining' if trend == 'decreasing' else 'stabilising'} toward the current level."
        )
    )

    trend_narratives = {
        "decreasing": (
            f"The declining debt trend is a positive signal. However, at "
            f"{s(latest, vfmt)} {unit}, Portugal remains above the euro area average "
            f"and the 60% Maastricht threshold. Continued fiscal discipline is essential."
        ),
        "increasing": (
            f"The rising trajectory raises sustainability concerns. At "
            f"{s(latest, vfmt)} {unit}, fiscal space is constrained. Credible "
            f"medium-term consolidation plans are critical for market confidence."
        ),
    }
    para3 = trend_narratives.get(
        trend,
        (
            f"Debt stabilisation around {s(latest, vfmt)} {unit} represents a transitional "
            f"phase. The path forward depends on primary surplus generation, nominal GDP "
            f"growth, and the effective interest rate on outstanding debt."
        ),
    )

    findings = [
        f"Public debt {'increased' if change > 0 else 'decreased'} by {s(abs(change))}% over the full period.",
        f"Peak: {s(peak, vfmt)} {unit} in {peak_y}; Trough: {s(trough, vfmt)} in {trough_y}.",
        f"Debt trend classified as {trend}.",
    ]
    findings = _add_secondary_findings(
        d,
        findings,
        {
            "balance": "Fiscal balance ({col}): average {mean}, latest {latest}.",
            "deficit": "Fiscal balance ({col}): average {mean}, latest {latest}.",
        },
    )

    # Risk — use ratio-specific thresholds if applicable
    fmt = {"latest": s(latest), "year": d["latest_year"]}
    if is_ratio:
        risk = _build_risk(latest, None, _PUBLIC_DEBT_CONFIG["risk_thresholds_ratio"], fmt)
    else:
        risk = (
            f"MODERATE RISK. Public debt at {s(latest, '.0f')} {unit} requires ongoing monitoring."
        )

    recs = list(_PUBLIC_DEBT_CONFIG["recommendations"])

    if trend == "decreasing":
        outlook = (
            "The fiscal outlook is cautiously positive. A sustained declining debt "
            "trajectory positions Portugal for potential credit rating upgrades. "
            "Key assumptions: GDP growth above 1.5%, primary surpluses, and stable "
            "financing conditions."
        )
    else:
        outlook = (
            "The fiscal outlook carries material risks. Without credible consolidation, "
            "debt dynamics could deteriorate, particularly if rates remain elevated. "
            "Demographic pressures on pension and healthcare spending will intensify."
        )

    return {
        "pillar": "public_debt",
        "headline": headline,
        "executive_summary": f"{para1}\n\n{para2}\n\n{para3}",
        "key_findings": findings,
        "risk_assessment": risk,
        "recommendations": recs,
        "outlook": outlook,
    }


# ---------------------------------------------------------------------------
# Generic fallback
# ---------------------------------------------------------------------------


def _insight_generic(d: dict) -> dict:
    s = _safe
    pillar = d.get("pillar", "unknown")
    pillar_name = pillar.replace("_", " ").title()
    return {
        "pillar": pillar,
        "headline": f"{pillar_name}: latest value {s(d.get('latest_value'))} in {d.get('latest_year')}",
        "executive_summary": (
            f"Analysis of the {pillar_name} pillar covers "
            f"{d.get('earliest_year')}-{d.get('latest_year')}. The overall trend is "
            f"classified as {d.get('trend')}. The primary measure moved from "
            f"{s(d.get('earliest_value'))} to {s(d.get('latest_value'))}, representing "
            f"a cumulative change of {s(d.get('overall_change_pct'))}%."
        ),
        "key_findings": [
            f"Overall change: {s(d.get('overall_change_pct'))}%.",
            f"Peak: {s(d.get('peak_value'))} in {d.get('peak_year')}.",
            f"Trough: {s(d.get('trough_value'))} in {d.get('trough_year')}.",
        ],
        "risk_assessment": f"MODERATE RISK. Further analysis required for the {pillar_name} pillar.",
        "recommendations": [
            f"Conduct deeper analysis of {pillar_name} drivers and structural factors.",
        ],
        "outlook": f"The outlook for {pillar_name} depends on domestic and European-level policy developments.",
    }


# ---------------------------------------------------------------------------
# Dispatch dictionary mapping pillar names to their insight functions
# ---------------------------------------------------------------------------
PILLAR_DISPATCH = {
    "gdp": _insight_gdp,
    "unemployment": _insight_unemployment,
    "credit": _insight_credit,
    "interest_rates": _insight_interest_rates,
    "inflation": _insight_inflation,
    "public_debt": _insight_public_debt,
}
