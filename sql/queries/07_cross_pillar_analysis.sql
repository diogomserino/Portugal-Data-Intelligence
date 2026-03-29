-- =============================================================================
-- Portugal Data Intelligence - Cross-Pillar Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Tables   : All fact tables joined with dim_date
-- Period   : 2010 - 2025
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. MACRO DASHBOARD SUMMARY
--    Latest available values for all key indicators in one query.
-- -----------------------------------------------------------------------------
WITH latest_gdp AS (
    SELECT
        g.date_key,
        d.year,
        d.quarter,
        g.nominal_gdp,
        g.real_gdp,
        g.gdp_growth_yoy,
        g.gdp_per_capita
    FROM fact_gdp g
    JOIN dim_date d ON g.date_key = d.date_key
    ORDER BY d.year DESC, d.quarter DESC
    LIMIT 1
),
latest_unemployment AS (
    SELECT
        u.date_key,
        u.unemployment_rate,
        u.youth_unemployment_rate,
        u.labour_force_participation_rate
    FROM fact_unemployment u
    JOIN dim_date d ON u.date_key = d.date_key
    ORDER BY d.year DESC, d.month DESC
    LIMIT 1
),
latest_credit AS (
    SELECT
        c.date_key,
        c.total_credit,
        c.npl_ratio
    FROM fact_credit c
    JOIN dim_date d ON c.date_key = d.date_key
    ORDER BY d.year DESC, d.month DESC
    LIMIT 1
),
latest_rates AS (
    SELECT
        ir.date_key,
        ir.ecb_main_refinancing_rate,
        ir.euribor_12m,
        ir.portugal_10y_bond_yield
    FROM fact_interest_rates ir
    JOIN dim_date d ON ir.date_key = d.date_key
    ORDER BY d.year DESC, d.month DESC
    LIMIT 1
),
latest_inflation AS (
    SELECT
        inf.date_key,
        inf.hicp,
        inf.core_inflation
    FROM fact_inflation inf
    JOIN dim_date d ON inf.date_key = d.date_key
    ORDER BY d.year DESC, d.month DESC
    LIMIT 1
),
latest_debt AS (
    SELECT
        pd.date_key,
        pd.total_debt,
        pd.debt_to_gdp_ratio,
        pd.budget_deficit
    FROM fact_public_debt pd
    JOIN dim_date d ON pd.date_key = d.date_key
    ORDER BY d.year DESC, d.quarter DESC
    LIMIT 1
)
SELECT
    -- GDP
    lg.date_key                                       AS gdp_date,
    ROUND(lg.nominal_gdp, 2)                         AS nominal_gdp_eur_m,
    ROUND(lg.gdp_growth_yoy, 2)                      AS gdp_growth_yoy_pct,
    ROUND(lg.gdp_per_capita, 2)                       AS gdp_per_capita_eur,
    -- Unemployment
    lu.date_key                                       AS unemployment_date,
    lu.unemployment_rate                              AS unemployment_rate_pct,
    lu.youth_unemployment_rate                        AS youth_unemployment_pct,
    -- Credit
    lc.date_key                                       AS credit_date,
    ROUND(lc.total_credit, 2)                         AS total_credit_eur_m,
    lc.npl_ratio                                      AS npl_ratio_pct,
    -- Interest Rates
    lr.date_key                                       AS rates_date,
    lr.ecb_main_refinancing_rate                      AS ecb_rate_pct,
    lr.portugal_10y_bond_yield                        AS bond_yield_10y_pct,
    -- Inflation
    li.date_key                                       AS inflation_date,
    li.hicp                                           AS hicp_pct,
    li.core_inflation                                 AS core_inflation_pct,
    -- Public Debt
    ld.date_key                                       AS debt_date,
    ROUND(ld.total_debt, 2)                           AS total_debt_eur_m,
    ld.debt_to_gdp_ratio                              AS debt_to_gdp_pct,
    ld.budget_deficit                                 AS budget_balance_pct_gdp
FROM latest_gdp lg, latest_unemployment lu, latest_credit lc,
     latest_rates lr, latest_inflation li, latest_debt ld;


-- -----------------------------------------------------------------------------
-- 2. ECONOMIC HEALTH SCORECARD
--    Normalised scores (0-100) for each pillar, combined into a composite index.
--    Higher score = healthier economy.
-- -----------------------------------------------------------------------------
WITH annual_metrics AS (
    SELECT
        d.year,
        -- GDP: average quarterly YoY growth
        (SELECT AVG(g2.gdp_growth_yoy)
         FROM fact_gdp g2
         JOIN dim_date d2 ON g2.date_key = d2.date_key
         WHERE d2.year = d.year) AS avg_gdp_growth,
        -- Unemployment: annual average
        (SELECT AVG(u2.unemployment_rate)
         FROM fact_unemployment u2
         JOIN dim_date d2 ON u2.date_key = d2.date_key
         WHERE d2.year = d.year) AS avg_unemployment,
        -- Inflation: annual average HICP
        (SELECT AVG(inf2.hicp)
         FROM fact_inflation inf2
         JOIN dim_date d2 ON inf2.date_key = d2.date_key
         WHERE d2.year = d.year) AS avg_inflation,
        -- Credit health: annual average NPL ratio
        (SELECT AVG(c2.npl_ratio)
         FROM fact_credit c2
         JOIN dim_date d2 ON c2.date_key = d2.date_key
         WHERE d2.year = d.year) AS avg_npl_ratio,
        -- Debt: annual average debt-to-GDP
        (SELECT AVG(pd2.debt_to_gdp_ratio)
         FROM fact_public_debt pd2
         JOIN dim_date d2 ON pd2.date_key = d2.date_key
         WHERE d2.year = d.year) AS avg_debt_to_gdp,
        -- Bond yield spread as risk indicator
        (SELECT AVG(ir2.portugal_10y_bond_yield - ir2.ecb_main_refinancing_rate)
         FROM fact_interest_rates ir2
         JOIN dim_date d2 ON ir2.date_key = d2.date_key
         WHERE d2.year = d.year) AS avg_spread
    FROM dim_date d
    GROUP BY d.year
),
bounds AS (
    SELECT
        MIN(avg_gdp_growth)   AS min_gdp,    MAX(avg_gdp_growth)   AS max_gdp,
        MIN(avg_unemployment) AS min_unemp,   MAX(avg_unemployment) AS max_unemp,
        MIN(ABS(avg_inflation - 2.0)) AS min_inf_dev,
        MAX(ABS(avg_inflation - 2.0)) AS max_inf_dev,
        MIN(avg_npl_ratio)    AS min_npl,     MAX(avg_npl_ratio)    AS max_npl,
        MIN(avg_debt_to_gdp)  AS min_debt,    MAX(avg_debt_to_gdp)  AS max_debt,
        MIN(avg_spread)       AS min_spread,  MAX(avg_spread)       AS max_spread
    FROM annual_metrics
    WHERE avg_gdp_growth IS NOT NULL
)
SELECT
    am.year,
    -- GDP score: higher growth = better
    ROUND(
        (am.avg_gdp_growth - b.min_gdp)
        / NULLIF(b.max_gdp - b.min_gdp, 0) * 100.0, 1
    )                                                 AS gdp_score,
    -- Unemployment score: lower = better (inverted)
    ROUND(
        (1.0 - (am.avg_unemployment - b.min_unemp)
              / NULLIF(b.max_unemp - b.min_unemp, 0)) * 100.0, 1
    )                                                 AS unemployment_score,
    -- Inflation score: closer to 2% target = better (inverted deviation)
    ROUND(
        (1.0 - (ABS(am.avg_inflation - 2.0) - b.min_inf_dev)
              / NULLIF(b.max_inf_dev - b.min_inf_dev, 0)) * 100.0, 1
    )                                                 AS inflation_score,
    -- Credit health score: lower NPL = better (inverted)
    ROUND(
        (1.0 - (am.avg_npl_ratio - b.min_npl)
              / NULLIF(b.max_npl - b.min_npl, 0)) * 100.0, 1
    )                                                 AS credit_health_score,
    -- Fiscal score: lower debt-to-GDP = better (inverted)
    ROUND(
        (1.0 - (am.avg_debt_to_gdp - b.min_debt)
              / NULLIF(b.max_debt - b.min_debt, 0)) * 100.0, 1
    )                                                 AS fiscal_score,
    -- Financial stability score: lower spread = better (inverted)
    ROUND(
        (1.0 - (am.avg_spread - b.min_spread)
              / NULLIF(b.max_spread - b.min_spread, 0)) * 100.0, 1
    )                                                 AS financial_stability_score,
    -- Composite index: equal-weighted average of all six pillar scores
    ROUND(
        (
            (am.avg_gdp_growth - b.min_gdp)
                / NULLIF(b.max_gdp - b.min_gdp, 0)
          + (1.0 - (am.avg_unemployment - b.min_unemp)
                  / NULLIF(b.max_unemp - b.min_unemp, 0))
          + (1.0 - (ABS(am.avg_inflation - 2.0) - b.min_inf_dev)
                  / NULLIF(b.max_inf_dev - b.min_inf_dev, 0))
          + (1.0 - (am.avg_npl_ratio - b.min_npl)
                  / NULLIF(b.max_npl - b.min_npl, 0))
          + (1.0 - (am.avg_debt_to_gdp - b.min_debt)
                  / NULLIF(b.max_debt - b.min_debt, 0))
          + (1.0 - (am.avg_spread - b.min_spread)
                  / NULLIF(b.max_spread - b.min_spread, 0))
        ) / 6.0 * 100.0, 1
    )                                                 AS composite_health_index
FROM annual_metrics am
CROSS JOIN bounds b
WHERE am.avg_gdp_growth IS NOT NULL
ORDER BY am.year;


-- -----------------------------------------------------------------------------
-- 3. CRISIS TIMELINE
--    Identify economic stress periods using multiple indicators.
--    A month is flagged as "stress" when 2+ indicators breach thresholds.
-- -----------------------------------------------------------------------------
WITH monthly_stress AS (
    SELECT
        d.year,
        d.month,
        d.date_key,
        -- Unemployment stress: rate above 12%
        CASE WHEN u.unemployment_rate > 12.0 THEN 1 ELSE 0 END
                                                      AS unemployment_stress,
        -- Inflation stress: deflation or rate above 4%
        CASE WHEN inf.hicp < 0 OR inf.hicp > 4.0 THEN 1 ELSE 0 END
                                                      AS inflation_stress,
        -- Credit stress: NPL ratio above 7%
        CASE WHEN c.npl_ratio > 7.0 THEN 1 ELSE 0 END
                                                      AS credit_stress,
        -- Bond market stress: 10Y yield above 6%
        CASE WHEN ir.portugal_10y_bond_yield > 6.0 THEN 1 ELSE 0 END
                                                      AS bond_stress,
        -- Key values for context
        u.unemployment_rate,
        inf.hicp,
        c.npl_ratio,
        ir.portugal_10y_bond_yield
    FROM dim_date d
    LEFT JOIN fact_unemployment u   ON d.date_key = u.date_key
    LEFT JOIN fact_inflation inf    ON d.date_key = inf.date_key
    LEFT JOIN fact_credit c         ON d.date_key = c.date_key
    LEFT JOIN fact_interest_rates ir ON d.date_key = ir.date_key
    WHERE d.month IS NOT NULL
)
SELECT
    year,
    month,
    date_key,
    unemployment_stress + inflation_stress + credit_stress + bond_stress
                                                      AS stress_count,
    CASE
        WHEN (unemployment_stress + inflation_stress + credit_stress + bond_stress) >= 3
            THEN 'Severe stress'
        WHEN (unemployment_stress + inflation_stress + credit_stress + bond_stress) >= 2
            THEN 'Moderate stress'
        WHEN (unemployment_stress + inflation_stress + credit_stress + bond_stress) >= 1
            THEN 'Mild stress'
        ELSE 'No stress'
    END                                               AS stress_classification,
    unemployment_rate,
    hicp                                              AS inflation_pct,
    npl_ratio                                         AS npl_ratio_pct,
    portugal_10y_bond_yield                           AS bond_yield_pct
FROM monthly_stress
WHERE (unemployment_stress + inflation_stress + credit_stress + bond_stress) >= 1
ORDER BY year, month;


-- -----------------------------------------------------------------------------
-- 4. PHILLIPS CURVE DATA
--    Unemployment vs inflation pairs by year (for scatter plot analysis).
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(AVG(u.unemployment_rate), 2)                AS avg_unemployment_pct,
    ROUND(AVG(inf.hicp), 2)                           AS avg_inflation_pct,
    ROUND(AVG(inf.core_inflation), 2)                 AS avg_core_inflation_pct,
    CASE
        WHEN d.year BETWEEN 2010 AND 2011 THEN '1. Pre-crisis'
        WHEN d.year BETWEEN 2012 AND 2014 THEN '2. Troika'
        WHEN d.year BETWEEN 2015 AND 2019 THEN '3. Recovery'
        WHEN d.year = 2020                 THEN '4. COVID'
        WHEN d.year BETWEEN 2021 AND 2025  THEN '5. Post-COVID'
    END                                               AS economic_period
FROM fact_unemployment u
JOIN dim_date d ON u.date_key = d.date_key
JOIN fact_inflation inf ON u.date_key = inf.date_key
WHERE u.unemployment_rate IS NOT NULL
  AND inf.hicp IS NOT NULL
GROUP BY d.year
ORDER BY d.year;


-- -----------------------------------------------------------------------------
-- 5. INTEREST RATE TRANSMISSION
--    ECB rate vs credit growth with lag analysis.
--    Shows whether credit responds to rate changes with a delay.
-- -----------------------------------------------------------------------------
WITH monthly_data AS (
    SELECT
        d.year,
        d.month,
        d.date_key,
        ir.ecb_main_refinancing_rate,
        c.total_credit,
        -- Credit YoY growth
        (c.total_credit - LAG(c.total_credit, 12) OVER (ORDER BY d.year, d.month))
        / NULLIF(LAG(c.total_credit, 12) OVER (ORDER BY d.year, d.month), 0) * 100.0
                                                      AS credit_yoy_growth
    FROM fact_interest_rates ir
    JOIN dim_date d ON ir.date_key = d.date_key
    JOIN fact_credit c ON ir.date_key = c.date_key
)
SELECT
    year,
    month,
    date_key,
    ROUND(ecb_main_refinancing_rate, 3)               AS ecb_rate_pct,
    ROUND(credit_yoy_growth, 2)                       AS credit_yoy_growth_pct,
    -- Lagged ECB rates to test transmission delays
    ROUND(
        LAG(ecb_main_refinancing_rate, 3) OVER (ORDER BY year, month), 3
    )                                                 AS ecb_rate_3m_lag,
    ROUND(
        LAG(ecb_main_refinancing_rate, 6) OVER (ORDER BY year, month), 3
    )                                                 AS ecb_rate_6m_lag,
    ROUND(
        LAG(ecb_main_refinancing_rate, 12) OVER (ORDER BY year, month), 3
    )                                                 AS ecb_rate_12m_lag,
    -- Rate change over preceding 12 months (transmission impulse)
    ROUND(
        ecb_main_refinancing_rate
        - LAG(ecb_main_refinancing_rate, 12) OVER (ORDER BY year, month), 3
    )                                                 AS ecb_rate_change_12m_pp
FROM monthly_data
WHERE credit_yoy_growth IS NOT NULL
ORDER BY year, month;


-- -----------------------------------------------------------------------------
-- 6. COMPLETE ECONOMIC SNAPSHOT BY YEAR
--    All pillars summarised annually in one wide table.
-- -----------------------------------------------------------------------------
WITH annual_gdp AS (
    SELECT
        d.year,
        SUM(g.nominal_gdp)        AS annual_nominal_gdp,
        SUM(g.real_gdp)           AS annual_real_gdp,
        AVG(g.gdp_growth_yoy)     AS avg_gdp_growth_yoy,
        AVG(g.gdp_per_capita)     AS avg_gdp_per_capita
    FROM fact_gdp g
    JOIN dim_date d ON g.date_key = d.date_key
    GROUP BY d.year
),
annual_unemployment AS (
    SELECT
        d.year,
        AVG(u.unemployment_rate)                AS avg_unemployment,
        AVG(u.youth_unemployment_rate)          AS avg_youth_unemployment,
        AVG(u.labour_force_participation_rate)  AS avg_participation
    FROM fact_unemployment u
    JOIN dim_date d ON u.date_key = d.date_key
    GROUP BY d.year
),
annual_credit AS (
    SELECT
        d.year,
        AVG(c.total_credit)       AS avg_total_credit,
        AVG(c.npl_ratio)          AS avg_npl_ratio
    FROM fact_credit c
    JOIN dim_date d ON c.date_key = d.date_key
    GROUP BY d.year
),
annual_rates AS (
    SELECT
        d.year,
        AVG(ir.ecb_main_refinancing_rate)    AS avg_ecb_rate,
        AVG(ir.euribor_12m)                  AS avg_euribor_12m,
        AVG(ir.portugal_10y_bond_yield)      AS avg_bond_yield
    FROM fact_interest_rates ir
    JOIN dim_date d ON ir.date_key = d.date_key
    GROUP BY d.year
),
annual_inflation AS (
    SELECT
        d.year,
        AVG(inf.hicp)             AS avg_hicp,
        AVG(inf.core_inflation)   AS avg_core_inflation
    FROM fact_inflation inf
    JOIN dim_date d ON inf.date_key = d.date_key
    GROUP BY d.year
),
annual_debt AS (
    SELECT
        d.year,
        AVG(pd.total_debt)          AS avg_total_debt,
        AVG(pd.debt_to_gdp_ratio)   AS avg_debt_to_gdp,
        AVG(pd.budget_deficit)       AS avg_budget_balance
    FROM fact_public_debt pd
    JOIN dim_date d ON pd.date_key = d.date_key
    GROUP BY d.year
)
SELECT
    g.year,
    -- Economic period label
    CASE
        WHEN g.year BETWEEN 2010 AND 2011 THEN 'Pre-crisis'
        WHEN g.year BETWEEN 2012 AND 2014 THEN 'Troika'
        WHEN g.year BETWEEN 2015 AND 2019 THEN 'Recovery'
        WHEN g.year = 2020                 THEN 'COVID'
        WHEN g.year BETWEEN 2021 AND 2025  THEN 'Post-COVID'
    END                                               AS economic_period,
    -- GDP pillar
    ROUND(g.annual_nominal_gdp, 0)                    AS nominal_gdp_eur_m,
    ROUND(g.avg_gdp_growth_yoy, 2)                    AS gdp_growth_yoy_pct,
    ROUND(g.avg_gdp_per_capita, 0)                    AS gdp_per_capita_eur,
    -- Unemployment pillar
    ROUND(u.avg_unemployment, 2)                      AS unemployment_pct,
    ROUND(u.avg_youth_unemployment, 2)                AS youth_unemployment_pct,
    ROUND(u.avg_participation, 2)                     AS participation_rate_pct,
    -- Credit pillar
    ROUND(c.avg_total_credit, 0)                      AS total_credit_eur_m,
    ROUND(c.avg_npl_ratio, 2)                         AS npl_ratio_pct,
    -- Interest rates pillar
    ROUND(r.avg_ecb_rate, 3)                          AS ecb_rate_pct,
    ROUND(r.avg_euribor_12m, 3)                       AS euribor_12m_pct,
    ROUND(r.avg_bond_yield, 3)                        AS bond_yield_10y_pct,
    ROUND(r.avg_bond_yield - r.avg_ecb_rate, 3)      AS sovereign_spread_pp,
    -- Inflation pillar
    ROUND(i.avg_hicp, 2)                              AS hicp_pct,
    ROUND(i.avg_core_inflation, 2)                    AS core_inflation_pct,
    -- Real interest rate
    ROUND(r.avg_ecb_rate - i.avg_hicp, 2)            AS real_interest_rate_pct,
    -- Public debt pillar
    ROUND(d.avg_total_debt, 0)                        AS total_debt_eur_m,
    ROUND(d.avg_debt_to_gdp, 2)                       AS debt_to_gdp_pct,
    ROUND(d.avg_budget_balance, 2)                     AS budget_balance_pct_gdp
FROM annual_gdp g
LEFT JOIN annual_unemployment u ON g.year = u.year
LEFT JOIN annual_credit c       ON g.year = c.year
LEFT JOIN annual_rates r        ON g.year = r.year
LEFT JOIN annual_inflation i    ON g.year = i.year
LEFT JOIN annual_debt d         ON g.year = d.year
ORDER BY g.year;

-- =============================================================================
-- END OF CROSS-PILLAR ANALYSIS
-- =============================================================================
