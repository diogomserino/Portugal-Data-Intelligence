-- =============================================================================
-- Portugal Data Intelligence - Interest Rates Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_interest_rates joined with dim_date
-- Period   : January 2010 - December 2025
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. RATE ENVIRONMENT CLASSIFICATION
--    Categorise each month into a rate environment based on the ECB main
--    refinancing rate.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.date_key,
    ir.ecb_main_refinancing_rate,
    CASE
        WHEN ir.ecb_main_refinancing_rate <= 0.0  THEN 'Zero / Negative'
        WHEN ir.ecb_main_refinancing_rate <= 1.0  THEN 'Low'
        WHEN ir.ecb_main_refinancing_rate <= 2.5  THEN 'Medium'
        WHEN ir.ecb_main_refinancing_rate <= 4.0  THEN 'High'
        ELSE                                           'Very high'
    END                                               AS rate_environment,
    ROUND(
        AVG(ir.ecb_main_refinancing_rate) OVER (
            ORDER BY d.year, d.month
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ), 3
    )                                                 AS ecb_rate_12m_ma
FROM fact_interest_rates ir
JOIN dim_date d ON ir.date_key = d.date_key
WHERE ir.ecb_main_refinancing_rate IS NOT NULL
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- 2. YIELD SPREAD (SOVEREIGN RISK PREMIUM)
--    Portugal 10Y bond yield minus ECB main refinancing rate.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.date_key,
    ir.portugal_10y_bond_yield,
    ir.ecb_main_refinancing_rate,
    ROUND(
        ir.portugal_10y_bond_yield - ir.ecb_main_refinancing_rate, 3
    )                                                 AS sovereign_spread_pp,
    CASE
        WHEN (ir.portugal_10y_bond_yield - ir.ecb_main_refinancing_rate) > 5.0
            THEN 'Extreme stress'
        WHEN (ir.portugal_10y_bond_yield - ir.ecb_main_refinancing_rate) > 3.0
            THEN 'High stress'
        WHEN (ir.portugal_10y_bond_yield - ir.ecb_main_refinancing_rate) > 1.5
            THEN 'Elevated'
        ELSE 'Normal'
    END                                               AS stress_level,
    ROUND(
        AVG(ir.portugal_10y_bond_yield - ir.ecb_main_refinancing_rate) OVER (
            ORDER BY d.year, d.month
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ), 3
    )                                                 AS spread_12m_ma
FROM fact_interest_rates ir
JOIN dim_date d ON ir.date_key = d.date_key
WHERE ir.portugal_10y_bond_yield IS NOT NULL
  AND ir.ecb_main_refinancing_rate IS NOT NULL
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- 3. EURIBOR TERM STRUCTURE
--    Compare 3M, 6M, and 12M Euribor rates and their spreads.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.date_key,
    ir.euribor_3m,
    ir.euribor_6m,
    ir.euribor_12m,
    -- Term spreads
    ROUND(ir.euribor_6m  - ir.euribor_3m,  3)        AS spread_6m_3m_pp,
    ROUND(ir.euribor_12m - ir.euribor_3m,  3)        AS spread_12m_3m_pp,
    ROUND(ir.euribor_12m - ir.euribor_6m,  3)        AS spread_12m_6m_pp,
    -- Curve shape indicator
    CASE
        WHEN ir.euribor_12m > ir.euribor_6m
         AND ir.euribor_6m  > ir.euribor_3m
            THEN 'Normal (upward)'
        WHEN ir.euribor_12m < ir.euribor_6m
         AND ir.euribor_6m  < ir.euribor_3m
            THEN 'Inverted'
        ELSE 'Flat / Mixed'
    END                                               AS curve_shape
FROM fact_interest_rates ir
JOIN dim_date d ON ir.date_key = d.date_key
WHERE ir.euribor_3m IS NOT NULL
  AND ir.euribor_6m IS NOT NULL
  AND ir.euribor_12m IS NOT NULL
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- 4. RATE CHANGE MOMENTUM
--    Month-over-month changes in the ECB main refinancing rate.
--    Identifies tightening and easing cycles.
-- -----------------------------------------------------------------------------
WITH rate_changes AS (
    SELECT
        d.year,
        d.month,
        d.date_key,
        ir.ecb_main_refinancing_rate,
        LAG(ir.ecb_main_refinancing_rate, 1) OVER (ORDER BY d.year, d.month)
                                                      AS prev_month_rate,
        ir.ecb_main_refinancing_rate
            - LAG(ir.ecb_main_refinancing_rate, 1) OVER (ORDER BY d.year, d.month)
                                                      AS mom_change_pp,
        ir.ecb_main_refinancing_rate
            - LAG(ir.ecb_main_refinancing_rate, 12) OVER (ORDER BY d.year, d.month)
                                                      AS yoy_change_pp
    FROM fact_interest_rates ir
    JOIN dim_date d ON ir.date_key = d.date_key
    WHERE ir.ecb_main_refinancing_rate IS NOT NULL
)
SELECT
    year,
    month,
    date_key,
    ecb_main_refinancing_rate,
    ROUND(mom_change_pp, 3)                           AS mom_change_pp,
    ROUND(yoy_change_pp, 3)                           AS yoy_change_pp,
    CASE
        WHEN mom_change_pp > 0  THEN 'Tightening'
        WHEN mom_change_pp < 0  THEN 'Easing'
        ELSE                         'Unchanged'
    END                                               AS policy_direction,
    -- Cumulative change over trailing 6 months to identify cycles
    ROUND(
        SUM(mom_change_pp) OVER (
            ORDER BY year, month
            ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
        ), 3
    )                                                 AS cumulative_6m_change_pp
FROM rate_changes
WHERE prev_month_rate IS NOT NULL
ORDER BY year, month;


-- -----------------------------------------------------------------------------
-- 5. CRISIS PREMIUM
--    Compare bond yields during crisis periods vs normal periods.
-- -----------------------------------------------------------------------------
WITH period_rates AS (
    SELECT
        ir.portugal_10y_bond_yield,
        ir.ecb_main_refinancing_rate,
        ir.portugal_10y_bond_yield - ir.ecb_main_refinancing_rate
                                                      AS spread,
        CASE
            WHEN d.year BETWEEN 2010 AND 2011 THEN '1. Pre-crisis'
            WHEN d.year BETWEEN 2012 AND 2014 THEN '2. Troika'
            WHEN d.year BETWEEN 2015 AND 2019 THEN '3. Recovery'
            WHEN d.year = 2020                 THEN '4. COVID'
            WHEN d.year BETWEEN 2021 AND 2025  THEN '5. Post-COVID'
        END AS economic_period
    FROM fact_interest_rates ir
    JOIN dim_date d ON ir.date_key = d.date_key
    WHERE ir.portugal_10y_bond_yield IS NOT NULL
)
SELECT
    economic_period,
    COUNT(*)                                          AS month_count,
    ROUND(AVG(portugal_10y_bond_yield), 3)            AS avg_bond_yield_pct,
    ROUND(MAX(portugal_10y_bond_yield), 3)            AS peak_bond_yield_pct,
    ROUND(MIN(portugal_10y_bond_yield), 3)            AS min_bond_yield_pct,
    ROUND(AVG(ecb_main_refinancing_rate), 3)          AS avg_ecb_rate_pct,
    ROUND(AVG(spread), 3)                             AS avg_spread_pp,
    ROUND(MAX(spread), 3)                             AS max_spread_pp
FROM period_rates
WHERE economic_period IS NOT NULL
GROUP BY economic_period
ORDER BY economic_period;

-- =============================================================================
-- END OF INTEREST RATES ANALYSIS
-- =============================================================================
