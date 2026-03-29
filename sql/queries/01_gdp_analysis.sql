-- =============================================================================
-- Portugal Data Intelligence - GDP Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_gdp joined with dim_date
-- Period   : 2010-Q1 to 2025-Q4
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. ANNUAL GDP SUMMARY
--    Aggregate quarterly GDP to annual totals and compute YoY growth.
-- -----------------------------------------------------------------------------
WITH annual_gdp AS (
    SELECT
        d.year,
        SUM(g.nominal_gdp)                          AS annual_nominal_gdp,
        SUM(g.real_gdp)                              AS annual_real_gdp,
        AVG(g.gdp_per_capita)                        AS avg_gdp_per_capita,
        COUNT(g.id)                                  AS quarters_reported
    FROM fact_gdp g
    JOIN dim_date d ON g.date_key = d.date_key
    GROUP BY d.year
)
SELECT
    a.year,
    a.quarters_reported,
    ROUND(a.annual_nominal_gdp, 2)                   AS annual_nominal_gdp_eur_m,
    ROUND(a.annual_real_gdp, 2)                       AS annual_real_gdp_eur_m,
    ROUND(a.avg_gdp_per_capita, 2)                    AS avg_gdp_per_capita_eur,
    ROUND(
        (a.annual_real_gdp - prev.annual_real_gdp)
        / prev.annual_real_gdp * 100.0, 2
    )                                                 AS real_gdp_yoy_growth_pct
FROM annual_gdp a
LEFT JOIN annual_gdp prev ON prev.year = a.year - 1
ORDER BY a.year;


-- -----------------------------------------------------------------------------
-- 2. GDP GROWTH RANKING
--    Rank years by real GDP growth rate (highest first).
-- -----------------------------------------------------------------------------
WITH annual_gdp AS (
    SELECT
        d.year,
        SUM(g.real_gdp) AS annual_real_gdp
    FROM fact_gdp g
    JOIN dim_date d ON g.date_key = d.date_key
    GROUP BY d.year
),
growth AS (
    SELECT
        a.year,
        ROUND(
            (a.annual_real_gdp - prev.annual_real_gdp)
            / prev.annual_real_gdp * 100.0, 2
        ) AS real_gdp_growth_pct
    FROM annual_gdp a
    JOIN annual_gdp prev ON prev.year = a.year - 1
)
SELECT
    RANK() OVER (ORDER BY real_gdp_growth_pct DESC)  AS growth_rank,
    year,
    real_gdp_growth_pct,
    CASE
        WHEN real_gdp_growth_pct > 3  THEN 'Strong expansion'
        WHEN real_gdp_growth_pct > 0  THEN 'Moderate growth'
        WHEN real_gdp_growth_pct > -1 THEN 'Stagnation'
        ELSE                               'Contraction'
    END                                               AS classification
FROM growth
ORDER BY growth_rank;


-- -----------------------------------------------------------------------------
-- 3. PRE/POST CRISIS COMPARISON
--    Compare average GDP metrics across five distinct economic periods.
-- -----------------------------------------------------------------------------
WITH period_mapping AS (
    SELECT
        d.year,
        g.nominal_gdp,
        g.real_gdp,
        g.gdp_growth_yoy,
        g.gdp_per_capita,
        CASE
            WHEN d.year BETWEEN 2010 AND 2011 THEN '1. Pre-crisis'
            WHEN d.year BETWEEN 2012 AND 2014 THEN '2. Troika'
            WHEN d.year BETWEEN 2015 AND 2019 THEN '3. Recovery'
            WHEN d.year = 2020                 THEN '4. COVID'
            WHEN d.year BETWEEN 2021 AND 2025  THEN '5. Post-COVID'
        END AS economic_period
    FROM fact_gdp g
    JOIN dim_date d ON g.date_key = d.date_key
)
SELECT
    economic_period,
    COUNT(*)                                          AS quarter_count,
    ROUND(AVG(nominal_gdp), 2)                        AS avg_nominal_gdp_eur_m,
    ROUND(AVG(real_gdp), 2)                            AS avg_real_gdp_eur_m,
    ROUND(AVG(gdp_growth_yoy), 2)                      AS avg_yoy_growth_pct,
    ROUND(AVG(gdp_per_capita), 2)                       AS avg_gdp_per_capita_eur,
    ROUND(MIN(gdp_growth_yoy), 2)                       AS worst_quarter_growth_pct,
    ROUND(MAX(gdp_growth_yoy), 2)                       AS best_quarter_growth_pct
FROM period_mapping
WHERE economic_period IS NOT NULL
GROUP BY economic_period
ORDER BY economic_period;


-- -----------------------------------------------------------------------------
-- 4. QUARTERLY SEASONALITY
--    Average GDP by calendar quarter to reveal seasonal patterns.
-- -----------------------------------------------------------------------------
SELECT
    d.quarter,
    'Q' || d.quarter                                  AS quarter_label,
    COUNT(*)                                          AS observations,
    ROUND(AVG(g.nominal_gdp), 2)                       AS avg_nominal_gdp_eur_m,
    ROUND(AVG(g.real_gdp), 2)                           AS avg_real_gdp_eur_m,
    ROUND(AVG(g.gdp_growth_qoq), 2)                     AS avg_qoq_growth_pct,
    ROUND(AVG(g.gdp_growth_yoy), 2)                      AS avg_yoy_growth_pct,
    ROUND(MIN(g.gdp_growth_qoq), 2)                      AS min_qoq_growth_pct,
    ROUND(MAX(g.gdp_growth_qoq), 2)                      AS max_qoq_growth_pct
FROM fact_gdp g
JOIN dim_date d ON g.date_key = d.date_key
GROUP BY d.quarter
ORDER BY d.quarter;


-- -----------------------------------------------------------------------------
-- 5. GDP PER CAPITA EVOLUTION
--    Year-over-year per capita change with cumulative growth from base year.
-- -----------------------------------------------------------------------------
WITH annual_per_capita AS (
    SELECT
        d.year,
        AVG(g.gdp_per_capita) AS avg_gdp_per_capita
    FROM fact_gdp g
    JOIN dim_date d ON g.date_key = d.date_key
    GROUP BY d.year
),
base_year AS (
    SELECT avg_gdp_per_capita AS base_value
    FROM annual_per_capita
    WHERE year = (SELECT MIN(year) FROM annual_per_capita)
)
SELECT
    a.year,
    ROUND(a.avg_gdp_per_capita, 2)                    AS gdp_per_capita_eur,
    ROUND(
        (a.avg_gdp_per_capita - prev.avg_gdp_per_capita)
        / prev.avg_gdp_per_capita * 100.0, 2
    )                                                 AS yoy_change_pct,
    ROUND(
        (a.avg_gdp_per_capita - b.base_value)
        / b.base_value * 100.0, 2
    )                                                 AS cumulative_growth_from_base_pct
FROM annual_per_capita a
LEFT JOIN annual_per_capita prev ON prev.year = a.year - 1
CROSS JOIN base_year b
ORDER BY a.year;

-- =============================================================================
-- END OF GDP ANALYSIS
-- =============================================================================
