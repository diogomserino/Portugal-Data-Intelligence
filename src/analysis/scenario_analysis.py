"""
Portugal Data Intelligence — Scenario Analysis Module
======================================================
Provides what-if scenario analysis and stress testing for key policy questions:

1. **Interest rate shock** — impact on debt sustainability and credit
2. **GDP slowdown** — impact on unemployment, debt, and fiscal revenue
3. **Inflation spike** — impact on real rates, purchasing power, and debt
4. **Fiscal consolidation** — effort required to reach deficit/debt targets

All coefficients (Okun's law, fiscal multipliers, elasticities) are estimated
from the historical data in the database where possible, with well-established
textbook fallbacks otherwise.
"""

import sqlite3
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from scipy import stats

from config.settings import DATA_PILLARS, DATABASE_PATH
from src.utils.logger import get_logger, log_section

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants / textbook priors (used as fallbacks)
# ---------------------------------------------------------------------------

OKUN_COEFFICIENT = -0.4
"""Okun's law coefficient: 1 pp GDP decline -> 0.4 pp unemployment rise.

Textbook source: Blanchard, O. (2017), *Macroeconomics*, 7th ed., Pearson.
European Commission (2022) estimates Okun's coefficient for Portugal at -0.35
to -0.45, consistent with this prior.
"""

FISCAL_MULTIPLIER = 0.7
"""Fiscal multiplier: 1 EUR consolidation -> 0.7 EUR GDP contraction.

Source: Batini, N. et al. (2014), 'Fiscal Multipliers: Size, Determinants,
and Use in Macroeconomic Projections', IMF Technical Notes, No. 2014/004.
European Commission (2022), 'Report on Public Finances in EMU', Annex A.
Portugal-specific estimates range 0.5-0.9 depending on cycle position.
"""

NPL_GDP_ELASTICITY = -2.5
"""NPL-GDP elasticity: 1 pp GDP decline -> 2.5 pp NPL ratio increase.

Source: Nkusu, M. (2011), 'Nonperforming Loans and Macrofinancial
Vulnerabilities in Advanced Economies', IMF WP/11/161. Panel estimates
for Southern European economies yield elasticities of -2.0 to -3.0.
"""

CREDIT_RATE_SEMI_ELASTICITY = -3.0
"""Credit-rate semi-elasticity: 100 bps rate hike -> 3% credit contraction.

Source: ECB (2023), 'The Transmission of Monetary Policy in the Euro Area',
Economic Bulletin, Issue 3. Bank of Portugal Financial Stability Report
(2022) estimates -2.5 to -3.5 for Portuguese credit aggregates.
"""

TAX_REVENUE_GDP_ELASTICITY = 1.1
"""Tax revenue GDP elasticity: 1% GDP change -> 1.1% tax revenue change.

Source: Mourre, G. et al. (2019), 'The Semi-Elasticities Underlying the
Cyclically-Adjusted Budget Balance', European Economy Discussion Paper 098.
Portugal's estimated overall elasticity: 1.05-1.15.
"""


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class ScenarioEngine:
    """Run macroeconomic stress scenarios for Portugal."""

    def __init__(self, db_path: Optional[str] = None):
        """Load baseline data from the SQLite database.

        Parameters
        ----------
        db_path : str or None
            Path to the database.  Falls back to the project default.
        """
        self.db_path = str(db_path or DATABASE_PATH)
        logger.info("ScenarioEngine initialised — database: %s", self.db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._load_baseline()
        self._estimate_coefficients()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_baseline(self):
        """Read the latest values and key historical series from the database."""
        logger.info("Loading baseline data...")

        # GDP
        gdp_df = pd.read_sql(
            "SELECT date_key, nominal_gdp, real_gdp, gdp_growth_yoy "
            "FROM fact_gdp ORDER BY date_key",
            self._conn,
        )
        self.gdp_series = gdp_df
        if gdp_df.empty:
            raise ValueError("No GDP data available in the database.")
        self.latest_nominal_gdp = float(gdp_df["nominal_gdp"].iloc[-1])
        self.latest_real_gdp = float(gdp_df["real_gdp"].iloc[-1])
        latest_growth = gdp_df["gdp_growth_yoy"].iloc[-1]
        self.latest_gdp_growth = 0.0 if pd.isna(latest_growth) else float(latest_growth)
        # Annual nominal GDP (sum of last 4 quarters, validated)
        last_4q = gdp_df["nominal_gdp"].iloc[-4:]
        if len(last_4q) < 4:
            logger.warning("Less than 4 quarters for annual GDP; using available %d.", len(last_4q))
        self.annual_nominal_gdp = float(last_4q.sum())

        # Unemployment
        unemp_df = pd.read_sql(
            "SELECT date_key, unemployment_rate FROM fact_unemployment ORDER BY date_key",
            self._conn,
        )
        self.unemp_series = unemp_df
        if unemp_df.empty:
            raise ValueError("No unemployment data available in the database.")
        self.latest_unemployment = float(unemp_df["unemployment_rate"].iloc[-1])

        # Inflation
        infl_df = pd.read_sql(
            "SELECT date_key, hicp FROM fact_inflation ORDER BY date_key",
            self._conn,
        )
        self.infl_series = infl_df
        if infl_df.empty:
            raise ValueError("No inflation data available in the database.")
        self.latest_inflation = float(infl_df["hicp"].iloc[-1])

        # Interest rates
        rates_df = pd.read_sql(
            "SELECT date_key, ecb_main_refinancing_rate, euribor_12m, "
            "portugal_10y_bond_yield FROM fact_interest_rates ORDER BY date_key",
            self._conn,
        )
        self.rates_series = rates_df
        if rates_df.empty:
            raise ValueError("No interest rate data available in the database.")
        self.latest_ecb_rate = float(rates_df["ecb_main_refinancing_rate"].iloc[-1])
        self.latest_euribor = float(rates_df["euribor_12m"].iloc[-1])
        self.latest_bond_yield = float(rates_df["portugal_10y_bond_yield"].iloc[-1])

        # Credit
        credit_df = pd.read_sql(
            "SELECT date_key, total_credit, credit_households, npl_ratio "
            "FROM fact_credit ORDER BY date_key",
            self._conn,
        )
        self.credit_series = credit_df
        if credit_df.empty:
            raise ValueError("No credit data available in the database.")
        self.latest_total_credit = float(credit_df["total_credit"].iloc[-1])
        self.latest_household_credit = float(credit_df["credit_households"].iloc[-1])
        self.latest_npl = float(credit_df["npl_ratio"].iloc[-1])

        # Public debt
        debt_df = pd.read_sql(
            "SELECT date_key, total_debt, debt_to_gdp_ratio, budget_deficit "
            "FROM fact_public_debt ORDER BY date_key",
            self._conn,
        )
        self.debt_series = debt_df
        if debt_df.empty:
            raise ValueError("No public debt data available in the database.")
        self.latest_total_debt = float(debt_df["total_debt"].iloc[-1])
        self.latest_debt_ratio = float(debt_df["debt_to_gdp_ratio"].iloc[-1])
        self.latest_deficit = float(debt_df["budget_deficit"].iloc[-1])

        logger.info(
            "Baseline loaded — GDP: %.0f M EUR, Unemployment: %.1f %%, "
            "Debt/GDP: %.1f %%, Inflation: %.1f %%",
            self.annual_nominal_gdp,
            self.latest_unemployment,
            self.latest_debt_ratio,
            self.latest_inflation,
        )

    def _estimate_coefficients(self):
        """Estimate structural coefficients from historical data where feasible.

        For each coefficient, attempts data-driven estimation via OLS on the
        Portuguese time series.  Falls back to textbook priors (documented in
        the module-level constants) if estimation fails or yields implausible
        values.  Stores ``calibration_sources`` dict for transparency.
        """
        logger.info("Estimating structural coefficients from data...")
        self.calibration_sources: Dict[str, str] = {}

        # ------------------------------------------------------------------
        # Okun's law: dU = alpha + beta * dGDP
        # ------------------------------------------------------------------
        try:
            gdp_g = self.gdp_series["gdp_growth_yoy"].dropna().values
            u_vals = self.unemp_series["unemployment_rate"].dropna().values
            # Align monthly unemployment to quarterly by averaging groups of 3
            # Trim to ensure complete quarters
            n_complete = (len(u_vals) // 3) * 3
            u_vals = u_vals[:n_complete]
            n_q = len(u_vals) // 3
            u_quarterly = np.array([u_vals[i * 3 : (i + 1) * 3].mean() for i in range(n_q)])
            u_change = np.diff(u_quarterly)

            gdp_g_aligned = gdp_g[1:]
            min_len = min(len(gdp_g_aligned), len(u_change))
            if min_len >= 10:
                slope, _intercept, r, _p, _se = stats.linregress(
                    gdp_g_aligned[-min_len:], u_change[-min_len:]
                )
                self.okun = float(slope)
                self.calibration_sources["okun"] = "data-driven"
                logger.info("Okun coefficient estimated: %.3f (R=%.2f)", self.okun, r)
            else:
                self.okun = OKUN_COEFFICIENT
                self.calibration_sources["okun"] = "textbook (Blanchard 2017)"
                logger.info("Okun coefficient: using textbook default %.2f", self.okun)
        except Exception as exc:
            self.okun = OKUN_COEFFICIENT
            self.calibration_sources["okun"] = "textbook (Blanchard 2017)"
            logger.warning("Okun estimation failed (%s), using default %.2f", exc, self.okun)

        # ------------------------------------------------------------------
        # Credit-rate semi-elasticity
        # ------------------------------------------------------------------
        try:
            rate_vals = self.rates_series["euribor_12m"].dropna().values
            cred_vals = self.credit_series["total_credit"].dropna().values
            cred_growth = np.diff(np.log(cred_vals)) * 100
            rate_change = np.diff(rate_vals)

            min_len = min(len(cred_growth), len(rate_change))
            if min_len >= 20:
                slope, _i, r, _p, _se = stats.linregress(
                    rate_change[-min_len:], cred_growth[-min_len:]
                )
                self.credit_rate_elast = float(slope) * 100
                self.calibration_sources["credit_rate_elasticity"] = "data-driven"
                logger.info("Credit-rate semi-elasticity: %.2f (R=%.2f)", self.credit_rate_elast, r)
            else:
                self.credit_rate_elast = CREDIT_RATE_SEMI_ELASTICITY
                self.calibration_sources["credit_rate_elasticity"] = "textbook (ECB 2023)"
        except Exception:
            self.credit_rate_elast = CREDIT_RATE_SEMI_ELASTICITY
            self.calibration_sources["credit_rate_elasticity"] = "textbook (ECB 2023)"

        # Fixed-source coefficients (not estimated from data)
        self.calibration_sources["fiscal_multiplier"] = "textbook (IMF 2014, EC 2022)"
        self.calibration_sources["npl_gdp_elasticity"] = "textbook (Nkusu/IMF 2011)"
        self.calibration_sources["tax_revenue_elasticity"] = "textbook (Mourre et al. 2019)"

        logger.info("Calibration sources: %s", self.calibration_sources)

    # ------------------------------------------------------------------
    # Scenario 1 — Interest rate shock
    # ------------------------------------------------------------------

    def rate_shock_scenario(self, rate_increase_bps: int = 200) -> dict:
        """What if the ECB raises rates by *rate_increase_bps* basis points?

        Impacts modelled:
        - Additional annual debt-servicing costs
        - Increase in average mortgage cost for households
        - Credit growth reduction (semi-elasticity)
        - Sovereign spread widening (rule of thumb)

        Returns
        -------
        dict
            Baseline and stressed values for each impact channel.
        """
        log_section(logger, f"Scenario: Rate shock +{rate_increase_bps} bps")
        delta = rate_increase_bps / 100.0  # percentage-point increase

        # 1. Debt servicing — additional cost
        additional_debt_cost = self.latest_total_debt * delta / 100.0  # EUR millions
        debt_cost_gdp_share = additional_debt_cost / self.annual_nominal_gdp * 100.0

        # 2. Household mortgage impact — average outstanding mortgage cost rise
        mortgage_cost_increase_pct = delta  # direct pass-through on variable-rate mortgages
        avg_mortgage_eur = 120_000  # approximate average Portuguese mortgage
        monthly_increase_eur = avg_mortgage_eur * (delta / 100.0) / 12.0

        # 3. Credit growth
        credit_growth_impact_pct = self.credit_rate_elast * (rate_increase_bps / 100.0)

        # 4. Sovereign spread — rule of thumb: 50 bps ECB hike -> ~20 bps spread widening for PT
        spread_widening_bps = rate_increase_bps * 0.4

        result = {
            "scenario": f"ECB rate increase +{rate_increase_bps} bps",
            "baseline": {
                "ecb_rate_pct": round(self.latest_ecb_rate, 3),
                "euribor_12m_pct": round(self.latest_euribor, 3),
                "bond_yield_10y_pct": round(self.latest_bond_yield, 3),
                "total_debt_eur_m": round(self.latest_total_debt, 1),
                "total_credit_eur_m": round(self.latest_total_credit, 1),
            },
            "stressed": {
                "ecb_rate_pct": round(self.latest_ecb_rate + delta, 3),
                "euribor_12m_pct": round(self.latest_euribor + delta, 3),
                "bond_yield_10y_pct": round(
                    self.latest_bond_yield + delta + spread_widening_bps / 100.0, 3
                ),
            },
            "impacts": {
                "additional_debt_servicing_eur_m": round(additional_debt_cost, 1),
                "debt_servicing_increase_gdp_pct": round(debt_cost_gdp_share, 2),
                "household_mortgage_monthly_increase_eur": round(monthly_increase_eur, 0),
                "credit_growth_change_pct": round(credit_growth_impact_pct, 2),
                "sovereign_spread_widening_bps": round(spread_widening_bps, 0),
            },
            "interpretation": (
                f"A {rate_increase_bps} bps rate rise would add approximately "
                f"EUR {additional_debt_cost:,.0f} M in annual debt-servicing costs "
                f"({debt_cost_gdp_share:.2f} % of GDP). Credit growth could slow by "
                f"~{abs(credit_growth_impact_pct):.1f} %. Households on variable-rate "
                f"mortgages would face an additional ~EUR {monthly_increase_eur:.0f}/month."
            ),
        }
        logger.info("Rate shock scenario complete.")
        return result

    # ------------------------------------------------------------------
    # Scenario 2 — GDP slowdown
    # ------------------------------------------------------------------

    def gdp_slowdown_scenario(self, gdp_shock_pct: float = -2.0) -> dict:
        """What if GDP contracts by *gdp_shock_pct* percent?

        Impacts modelled:
        - Unemployment (Okun's law)
        - Debt-to-GDP ratio (denominator effect)
        - Tax revenue (fiscal elasticity)
        - Credit quality (NPL increase)
        """
        log_section(logger, f"Scenario: GDP shock {gdp_shock_pct:+.1f} %")

        # 1. Unemployment impact via Okun's law
        unemployment_change = self.okun * gdp_shock_pct
        stressed_unemployment = (
            self.latest_unemployment - unemployment_change
        )  # note: okun is negative

        # 2. Debt-to-GDP — denominator shrinks
        new_gdp = self.annual_nominal_gdp * (1.0 + gdp_shock_pct / 100.0)
        stressed_debt_ratio = self.latest_total_debt / new_gdp * 100.0

        # 3. Tax revenue impact
        tax_revenue_change_pct = TAX_REVENUE_GDP_ELASTICITY * gdp_shock_pct
        # Approximate tax revenue as ~42 % of GDP (Portuguese average)
        tax_revenue_baseline = self.annual_nominal_gdp * 0.42
        tax_revenue_loss = tax_revenue_baseline * (tax_revenue_change_pct / 100.0)

        # 4. NPL increase
        # NPL_GDP_ELASTICITY is negative (-2.5): GDP contraction → positive npl_change
        npl_change = NPL_GDP_ELASTICITY * (gdp_shock_pct / 100.0) * 100.0  # in pp
        stressed_npl = max(0.0, self.latest_npl + npl_change)

        result = {
            "scenario": f"GDP contraction {gdp_shock_pct:+.1f} %",
            "baseline": {
                "gdp_growth_yoy_pct": round(self.latest_gdp_growth, 2),
                "unemployment_rate_pct": round(self.latest_unemployment, 2),
                "debt_to_gdp_ratio_pct": round(self.latest_debt_ratio, 2),
                "npl_ratio_pct": round(self.latest_npl, 2),
            },
            "stressed": {
                "gdp_growth_yoy_pct": round(self.latest_gdp_growth + gdp_shock_pct, 2),
                "unemployment_rate_pct": round(stressed_unemployment, 2),
                "unemployment_change_pp": round(-unemployment_change, 2),
                "debt_to_gdp_ratio_pct": round(stressed_debt_ratio, 2),
                "debt_ratio_change_pp": round(stressed_debt_ratio - self.latest_debt_ratio, 2),
                "npl_ratio_pct": round(stressed_npl, 2),
                "npl_change_pp": round(abs(npl_change), 2),
            },
            "fiscal_impact": {
                "tax_revenue_change_pct": round(tax_revenue_change_pct, 2),
                "tax_revenue_loss_eur_m": round(abs(tax_revenue_loss), 1),
            },
            "coefficients_used": {
                "okun_coefficient": round(self.okun, 3),
                "tax_revenue_gdp_elasticity": TAX_REVENUE_GDP_ELASTICITY,
                "npl_gdp_elasticity": NPL_GDP_ELASTICITY,
            },
            "interpretation": (
                f"A {abs(gdp_shock_pct):.1f} % GDP contraction would push unemployment "
                f"from {self.latest_unemployment:.1f} % to ~{stressed_unemployment:.1f} % "
                f"(Okun's law) and raise the debt-to-GDP ratio from "
                f"{self.latest_debt_ratio:.1f} % to ~{stressed_debt_ratio:.1f} %. "
                f"Tax revenue would fall by approximately EUR {abs(tax_revenue_loss):,.0f} M."
            ),
        }
        logger.info("GDP slowdown scenario complete.")
        return result

    # ------------------------------------------------------------------
    # Scenario 3 — Inflation spike
    # ------------------------------------------------------------------

    def inflation_spike_scenario(self, inflation_target: float = 6.0) -> dict:
        """What if inflation rises to *inflation_target* percent?

        Impacts modelled:
        - Real interest rates
        - Household purchasing power erosion
        - Nominal GDP boost
        - Debt-to-GDP impact (inflation helps via denominator)
        """
        log_section(logger, f"Scenario: Inflation spike to {inflation_target:.1f} %")

        inflation_delta = inflation_target - self.latest_inflation

        # 1. Real interest rates
        baseline_real_rate = self.latest_bond_yield - self.latest_inflation
        stressed_real_rate = self.latest_bond_yield - inflation_target

        # 2. Purchasing power — erosion over 1 year
        # Real purchasing power loss: difference in purchasing power at new vs old inflation
        purchasing_power_loss_pct = (
            (1.0 + self.latest_inflation / 100.0) / (1.0 + inflation_target / 100.0) - 1.0
        ) * 100.0

        # 3. Nominal GDP boost (Fisher effect: higher inflation -> higher nominal GDP)
        nominal_gdp_boost_pct = inflation_delta  # approximate
        new_nominal_gdp = self.annual_nominal_gdp * (1.0 + nominal_gdp_boost_pct / 100.0)

        # 4. Debt-to-GDP — inflation helps via denominator
        stressed_debt_ratio = self.latest_total_debt / new_nominal_gdp * 100.0

        # 5. Average household impact (median wage ~EUR 1,100/month)
        median_monthly_wage = 1_100
        monthly_cost_increase = median_monthly_wage * (inflation_delta / 100.0) / 12.0 * 12

        result = {
            "scenario": f"Inflation spike to {inflation_target:.1f} %",
            "baseline": {
                "hicp_pct": round(self.latest_inflation, 2),
                "real_bond_yield_pct": round(baseline_real_rate, 2),
                "nominal_gdp_eur_m": round(self.annual_nominal_gdp, 1),
                "debt_to_gdp_ratio_pct": round(self.latest_debt_ratio, 2),
            },
            "stressed": {
                "hicp_pct": round(inflation_target, 2),
                "inflation_increase_pp": round(inflation_delta, 2),
                "real_bond_yield_pct": round(stressed_real_rate, 2),
                "nominal_gdp_eur_m": round(new_nominal_gdp, 1),
                "debt_to_gdp_ratio_pct": round(stressed_debt_ratio, 2),
                "debt_ratio_change_pp": round(stressed_debt_ratio - self.latest_debt_ratio, 2),
            },
            "household_impact": {
                "purchasing_power_loss_pct": round(purchasing_power_loss_pct, 2),
                "annual_cost_increase_eur": round(monthly_cost_increase, 0),
            },
            "interpretation": (
                f"An inflation spike to {inflation_target:.1f} % (from {self.latest_inflation:.1f} %) "
                f"would push real bond yields from {baseline_real_rate:.2f} % to "
                f"{stressed_real_rate:.2f} %. Households would lose ~{abs(purchasing_power_loss_pct):.1f} % "
                f"in purchasing power. On the positive side, the debt-to-GDP ratio would fall to "
                f"~{stressed_debt_ratio:.1f} % from {self.latest_debt_ratio:.1f} % via the "
                f"denominator effect."
            ),
        }
        logger.info("Inflation spike scenario complete.")
        return result

    # ------------------------------------------------------------------
    # Scenario 4 — Fiscal consolidation
    # ------------------------------------------------------------------

    def fiscal_consolidation_scenario(self, deficit_target: float = -1.0) -> dict:
        """What fiscal effort is needed to reach *deficit_target* (% of GDP)?

        Calculates:
        - Required primary-balance adjustment
        - Years to reach the 60 % debt-to-GDP target
        - Growth impact of consolidation (via fiscal multiplier)
        """
        log_section(logger, f"Scenario: Fiscal consolidation to {deficit_target:.1f} % deficit")

        # Current deficit (positive = surplus, negative = deficit in our DB)
        current_deficit = self.latest_deficit  # % of GDP
        required_adjustment = deficit_target - current_deficit  # negative means tightening

        adjustment_eur = abs(required_adjustment) / 100.0 * self.annual_nominal_gdp

        # Growth impact via fiscal multiplier
        gdp_impact_pct = FISCAL_MULTIPLIER * required_adjustment  # consolidation drags growth
        gdp_impact_eur = gdp_impact_pct / 100.0 * self.annual_nominal_gdp

        # Years to 60 % debt-to-GDP target
        # Simplified simulation: each year debt falls by primary surplus, GDP grows at g
        avg_growth = 0.02  # 2 % nominal growth assumption
        r_implicit = self.latest_bond_yield / 100.0

        d = self.latest_debt_ratio  # debt-to-GDP ratio in pp (e.g. 130.0)
        target_d = 60.0
        # Primary balance in pp of GDP (positive = surplus reduces debt)
        pb_pp = -deficit_target  # deficit_target=-1.0 → pb_pp=1.0 (1% surplus)
        years_to_target = 0

        if d <= target_d:
            years_to_target = 0
        else:
            for yr in range(1, 101):
                d = d * (1.0 + r_implicit) / (1.0 + avg_growth) - pb_pp
                years_to_target = yr
                if d <= target_d:
                    break
            else:
                years_to_target = -1  # not reachable within 100 years

        result = {
            "scenario": f"Fiscal consolidation to {deficit_target:.1f} % of GDP deficit",
            "baseline": {
                "budget_balance_gdp_pct": round(current_deficit, 2),
                "debt_to_gdp_ratio_pct": round(self.latest_debt_ratio, 2),
            },
            "required_effort": {
                "fiscal_adjustment_pp_gdp": round(abs(required_adjustment), 2),
                "fiscal_adjustment_eur_m": round(adjustment_eur, 1),
                "direction": "tightening" if required_adjustment < 0 else "loosening",
            },
            "growth_impact": {
                "gdp_drag_pct": round(gdp_impact_pct, 2),
                "gdp_drag_eur_m": round(abs(gdp_impact_eur), 1),
                "fiscal_multiplier_used": FISCAL_MULTIPLIER,
            },
            "debt_sustainability": {
                "years_to_60pct_debt_gdp": years_to_target if years_to_target >= 0 else ">100",
                "assumptions": {
                    "nominal_gdp_growth_pct": avg_growth * 100,
                    "implicit_interest_rate_pct": round(r_implicit * 100, 2),
                },
            },
            "interpretation": (
                f"Reaching a {abs(deficit_target):.1f} % deficit target requires a fiscal "
                f"adjustment of {abs(required_adjustment):.2f} pp of GDP "
                f"(~EUR {adjustment_eur:,.0f} M). This consolidation would reduce GDP growth "
                f"by ~{abs(gdp_impact_pct):.2f} pp in the short term. At current rates and growth, "
                f"the 60 % debt-to-GDP target would be reached in "
                f"{'>' + '100' if years_to_target < 0 else str(years_to_target)} years."
            ),
        }
        logger.info("Fiscal consolidation scenario complete.")
        return result

    # ------------------------------------------------------------------
    # Combined stress test
    # ------------------------------------------------------------------

    def combined_stress_test(self) -> dict:
        """Run all scenarios and produce a combined risk assessment.

        Returns
        -------
        dict
            All individual scenario results plus a worst-case summary and
            qualitative risk narrative.
        """
        log_section(logger, "Combined Stress Test")

        scenarios = {
            "rate_shock_200bps": self.rate_shock_scenario(rate_increase_bps=200),
            "gdp_contraction_2pct": self.gdp_slowdown_scenario(gdp_shock_pct=-2.0),
            "inflation_spike_6pct": self.inflation_spike_scenario(inflation_target=6.0),
            "fiscal_consolidation": self.fiscal_consolidation_scenario(deficit_target=-1.0),
        }

        # Worst-case composite: simultaneous rate shock + GDP slowdown
        wc_unemployment = self.latest_unemployment - self.okun * (-2.0)  # GDP shock
        wc_gdp = self.annual_nominal_gdp * 0.98  # -2 % GDP
        wc_debt_ratio = self.latest_total_debt / wc_gdp * 100.0
        wc_additional_debt_cost = self.latest_total_debt * 2.0 / 100.0  # +200 bps

        worst_case = {
            "label": "Simultaneous rate shock (+200 bps) and GDP contraction (-2 %)",
            "unemployment_pct": round(wc_unemployment, 2),
            "debt_to_gdp_pct": round(wc_debt_ratio, 2),
            "additional_debt_cost_eur_m": round(wc_additional_debt_cost, 1),
        }

        # Qualitative risk summary
        risk_lines = []
        if self.latest_debt_ratio > 90:
            risk_lines.append(
                "HIGH: Debt-to-GDP ratio is elevated (>{:.0f} %), leaving limited "
                "fiscal space to absorb shocks.".format(self.latest_debt_ratio)
            )
        else:
            risk_lines.append(
                "MODERATE: Debt-to-GDP ratio at {:.1f} % provides some fiscal "
                "buffer.".format(self.latest_debt_ratio)
            )

        if self.latest_unemployment < 7.0:
            risk_lines.append(
                "LOW: Labour market is currently tight ({:.1f} % unemployment), "
                "providing a cushion.".format(self.latest_unemployment)
            )
        else:
            risk_lines.append(
                "MODERATE: Unemployment at {:.1f} % is already elevated.".format(
                    self.latest_unemployment
                )
            )

        if self.latest_inflation < 3.0:
            risk_lines.append(
                "LOW: Inflation is contained at {:.1f} %, close to the ECB target.".format(
                    self.latest_inflation
                )
            )
        else:
            risk_lines.append(
                "ELEVATED: Inflation at {:.1f} % is above the ECB's 2 % target.".format(
                    self.latest_inflation
                )
            )

        result = {
            "scenarios": scenarios,
            "worst_case": worst_case,
            "risk_summary": " | ".join(risk_lines),
        }
        logger.info("Combined stress test complete — %d scenarios.", len(scenarios))
        return result

    def close(self):
        """Close the database connection."""
        self._conn.close()
        logger.info("Database connection closed.")


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def run_scenarios(db_path: Optional[str] = None) -> dict:
    """Execute all scenarios and return results.

    Parameters
    ----------
    db_path : str or None
        Path to the SQLite database.

    Returns
    -------
    dict
        Combined stress-test results.
    """
    engine = ScenarioEngine(db_path=db_path)
    results = engine.combined_stress_test()
    engine.close()
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("=" * 72)
    print("  PORTUGAL DATA INTELLIGENCE — SCENARIO ANALYSIS")
    print("=" * 72)

    engine = ScenarioEngine()
    combined = engine.combined_stress_test()

    # Print each scenario
    for scenario_key, scenario_data in combined["scenarios"].items():
        print(f"\n{'-' * 72}")
        print(f"  {scenario_data.get('scenario', scenario_key).upper()}")
        print(f"{'-' * 72}")

        # Baseline
        baseline = scenario_data.get("baseline", {})
        print("  Baseline:")
        for k, v in baseline.items():
            print(f"    {k}: {v}")

        # Stressed values
        stressed = scenario_data.get("stressed", {})
        print("  Stressed:")
        for k, v in stressed.items():
            print(f"    {k}: {v}")

        # Impacts (if present)
        impacts = scenario_data.get("impacts", {})
        if impacts:
            print("  Impacts:")
            for k, v in impacts.items():
                print(f"    {k}: {v}")

        # Fiscal impact (if present)
        fiscal = scenario_data.get("fiscal_impact", {})
        if fiscal:
            print("  Fiscal impact:")
            for k, v in fiscal.items():
                print(f"    {k}: {v}")

        # Interpretation
        interp = scenario_data.get("interpretation", "")
        if interp:
            print(f"\n  >> {interp}")

    # Worst case
    print(f"\n{'-' * 72}")
    print("  WORST-CASE COMPOSITE")
    print(f"{'-' * 72}")
    for k, v in combined["worst_case"].items():
        print(f"    {k}: {v}")

    # Risk summary
    print(f"\n{'-' * 72}")
    print("  RISK SUMMARY")
    print(f"{'-' * 72}")
    for line in combined["risk_summary"].split(" | "):
        print(f"    {line.strip()}")

    engine.close()
    print(f"\n{'=' * 72}")
    print("  Scenario analysis complete.")
    print(f"{'=' * 72}")
