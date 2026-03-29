-- =============================================================================
-- Portugal Data Intelligence - Inflation Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_inflation joined with dim_date (and fact_interest_rates)
-- Period   : January 2010 - December 2025
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. INFLATION REGIME CLASSIFICATION
--    Categorise each month into an inflation regime based on HICP YoY rate.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.date_key,
    inf.hicp,
    CASE
        WHEN inf.hicp < 0    THEN 'Deflation'
        WHEN inf.hicp < 1.0  THEN 'Low inflation'
        WHEN inf.hicp < 2.5  THEN 'Target range'
        WHEN inf.hicp < 5.0  THEN 'High inflation'
        ELSE                       'Very high inflation'
    END                                               AS inflation_regime,
    ROUND(
        AVG(inf.hicp) OVER (
            ORDER BY d.year, d.month
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ), 2
    )                                                 AS hicp_12m_ma
FROM fact_inflation inf
JOIN dim_date d ON inf.date_key = d.date_key
WHERE inf.hicp IS NOT NULL
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- 2. CORE VS HEADLINE SPREAD
--    Difference between HICP and core inflation to measure energy/food impact.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.date_key,
    inf.hicp                                          AS headline_hicp_pct,
    inf.core_inflation                                AS core_inflation_pct,
    ROUND(inf.hicp - inf.core_inflation, 2)           AS headline_core_spread_pp,
    CASE
        WHEN (inf.hicp - inf.core_inflation) > 1.0
            THEN 'Energy/food driving inflation up'
        WHEN (inf.hicp - inf.core_inflation) < -1.0
            THEN 'Energy/food pulling inflation down'
        ELSE 'Aligned'
    END                                               AS energy_food_impact,
    ROUND(
        AVG(inf.hicp - inf.core_inflation) OVER (
            ORDER BY d.year, d.month
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ), 2
    )                                                 AS spread_12m_ma
FROM fact_inflation inf
JOIN dim_date d ON inf.date_key = d.date_key
WHERE inf.hicp IS NOT NULL
  AND inf.core_inflation IS NOT NULL
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- 3. ANNUAL INFLATION SUMMARY
--    Yearly averages with cumulative price level index (base year = 100).
-- -----------------------------------------------------------------------------
WITH annual_inflation AS (
    SELECT
        d.year,
        AVG(inf.hicp)           AS avg_hicp,
        AVG(inf.cpi_estimated)  AS avg_cpi_estimated,
        AVG(inf.core_inflation) AS avg_core_inflation,
        COUNT(*)                AS months_reported
    FROM fact_inflation inf
    JOIN dim_date d ON inf.date_key = d.date_key
    GROUP BY d.year
),
-- Build cumulative price level: start at 100, compound each year's average HICP
price_level AS (
    SELECT
        year,
        avg_hicp,
        avg_cpi_estimated,
        avg_core_inflation,
        months_reported,
        -- Cumulative product via running sum of logs is not native in SQLite,
        -- so we use a recursive approach with the EXP/LN workaround.
        -- Instead, use a running sum of annual inflation contributions.
        SUM(LN(1.0 + avg_hicp / 100.0)) OVER (
            ORDER BY year
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS log_cumulative
    FROM annual_inflation
    WHERE avg_hicp IS NOT NULL
)
SELECT
    year,
    months_reported,
    ROUND(avg_hicp, 2)                                AS avg_hicp_pct,
    ROUND(avg_cpi_estimated, 2)                        AS avg_cpi_estimated_pct,
    ROUND(avg_core_inflation, 2)                      AS avg_core_inflation_pct,
    -- Cumulative price level index (base year = 100)
    ROUND(100.0 * EXP(log_cumulative), 2)             AS cumulative_price_index
FROM price_level
ORDER BY year;


-- -----------------------------------------------------------------------------
-- 4. REAL INTEREST RATE
--    ECB rate minus HICP inflation (Fisher approximation).
--    Join fact_inflation with fact_interest_rates on date_key.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.date_key,
    ir.ecb_main_refinancing_rate                      AS ecb_rate_pct,
    inf.hicp                                          AS inflation_pct,
    ROUND(
        ir.ecb_main_refinancing_rate - inf.hicp, 2
    )                                                 AS real_interest_rate_pct,
    CASE
        WHEN (ir.ecb_main_refinancing_rate - inf.hicp) < -1.0
            THEN 'Very accommodative'
        WHEN (ir.ecb_main_refinancing_rate - inf.hicp) < 0
            THEN 'Accommodative'
        WHEN (ir.ecb_main_refinancing_rate - inf.hicp) < 1.0
            THEN 'Neutral'
        ELSE 'Restrictive'
    END                                               AS monetary_stance,
    ROUND(
        AVG(ir.ecb_main_refinancing_rate - inf.hicp) OVER (
            ORDER BY d.year, d.month
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ), 2
    )                                                 AS real_rate_12m_ma
FROM fact_inflation inf
JOIN fact_interest_rates ir ON inf.date_key = ir.date_key
JOIN dim_date d ON inf.date_key = d.date_key
WHERE inf.hicp IS NOT NULL
  AND ir.ecb_main_refinancing_rate IS NOT NULL
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- 5. INFLATION ACCELERATION
--    Month-over-month change in the HICP inflation rate.
--    Positive = accelerating, negative = decelerating.
-- -----------------------------------------------------------------------------
WITH inflation_momentum AS (
    SELECT
        d.year,
        d.month,
        d.date_key,
        inf.hicp,
        LAG(inf.hicp, 1)  OVER (ORDER BY d.year, d.month) AS hicp_prev_month,
        LAG(inf.hicp, 12) OVER (ORDER BY d.year, d.month) AS hicp_12m_ago
    FROM fact_inflation inf
    JOIN dim_date d ON inf.date_key = d.date_key
    WHERE inf.hicp IS NOT NULL
)
SELECT
    year,
    month,
    date_key,
    hicp                                              AS hicp_pct,
    ROUND(hicp - hicp_prev_month, 2)                  AS mom_acceleration_pp,
    ROUND(hicp - hicp_12m_ago, 2)                     AS yoy_acceleration_pp,
    CASE
        WHEN (hicp - hicp_prev_month) > 0.3  THEN 'Rapid acceleration'
        WHEN (hicp - hicp_prev_month) > 0    THEN 'Mild acceleration'
        WHEN (hicp - hicp_prev_month) > -0.3 THEN 'Mild deceleration'
        ELSE                                       'Rapid deceleration'
    END                                               AS momentum_classification,
    -- 3-month change for smoother signal
    ROUND(
        hicp - LAG(hicp, 3) OVER (ORDER BY year, month), 2
    )                                                 AS acceleration_3m_pp
FROM inflation_momentum
WHERE hicp_prev_month IS NOT NULL
ORDER BY year, month;

-- =============================================================================
-- END OF INFLATION ANALYSIS
-- =============================================================================
