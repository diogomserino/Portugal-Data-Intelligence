-- =============================================================================
-- Portugal Data Intelligence - Unemployment Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_unemployment joined with dim_date
-- Period   : January 2010 - December 2025
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. MONTHLY TREND WITH 12-MONTH MOVING AVERAGE
--    Show raw unemployment rate alongside a smoothed 12-month rolling average.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.date_key,
    u.unemployment_rate,
    ROUND(
        AVG(u.unemployment_rate) OVER (
            ORDER BY d.year, d.month
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ), 2
    )                                                 AS unemployment_rate_12m_ma,
    ROUND(
        u.unemployment_rate - AVG(u.unemployment_rate) OVER (
            ORDER BY d.year, d.month
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ), 2
    )                                                 AS deviation_from_ma
FROM fact_unemployment u
JOIN dim_date d ON u.date_key = d.date_key
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- 2. YOUTH VS GENERAL UNEMPLOYMENT GAP
--    Ratio of youth unemployment to general unemployment over time.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.month,
    d.date_key,
    u.unemployment_rate,
    u.youth_unemployment_rate,
    ROUND(u.youth_unemployment_rate - u.unemployment_rate, 2)
                                                      AS absolute_gap_pp,
    CASE
        WHEN u.unemployment_rate > 0 THEN
            ROUND(u.youth_unemployment_rate / u.unemployment_rate, 2)
        ELSE NULL
    END                                               AS youth_to_general_ratio,
    ROUND(
        AVG(
            CASE
                WHEN u.unemployment_rate > 0
                THEN u.youth_unemployment_rate / u.unemployment_rate
                ELSE NULL
            END
        ) OVER (
            ORDER BY d.year, d.month
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ), 2
    )                                                 AS ratio_12m_ma
FROM fact_unemployment u
JOIN dim_date d ON u.date_key = d.date_key
WHERE u.unemployment_rate IS NOT NULL
  AND u.youth_unemployment_rate IS NOT NULL
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- 3. ANNUAL STATISTICS
--    Min, max, average and standard deviation of unemployment by year.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    COUNT(*)                                          AS months_reported,
    ROUND(AVG(u.unemployment_rate), 2)                 AS avg_unemployment_pct,
    ROUND(MIN(u.unemployment_rate), 2)                 AS min_unemployment_pct,
    ROUND(MAX(u.unemployment_rate), 2)                 AS max_unemployment_pct,
    ROUND(MAX(u.unemployment_rate) - MIN(u.unemployment_rate), 2)
                                                      AS intra_year_range_pp,
    -- SQLite lacks STDDEV; compute manually via population formula
    ROUND(
        SQRT(
            AVG(u.unemployment_rate * u.unemployment_rate)
            - AVG(u.unemployment_rate) * AVG(u.unemployment_rate)
        ), 2
    )                                                 AS stddev_unemployment,
    ROUND(AVG(u.youth_unemployment_rate), 2)           AS avg_youth_unemployment_pct,
    ROUND(AVG(u.long_term_unemployment_rate), 2)       AS avg_long_term_unemployment_pct
FROM fact_unemployment u
JOIN dim_date d ON u.date_key = d.date_key
GROUP BY d.year
ORDER BY d.year;


-- -----------------------------------------------------------------------------
-- 4. CRISIS IMPACT PERIODS
--    Average unemployment by economic period.
-- -----------------------------------------------------------------------------
WITH period_data AS (
    SELECT
        u.unemployment_rate,
        u.youth_unemployment_rate,
        u.long_term_unemployment_rate,
        u.labour_force_participation_rate,
        CASE
            WHEN d.year BETWEEN 2010 AND 2011 THEN '1. Pre-crisis'
            WHEN d.year BETWEEN 2012 AND 2014 THEN '2. Troika'
            WHEN d.year BETWEEN 2015 AND 2019 THEN '3. Recovery'
            WHEN d.year = 2020                 THEN '4. COVID'
            WHEN d.year BETWEEN 2021 AND 2025  THEN '5. Post-COVID'
        END AS economic_period
    FROM fact_unemployment u
    JOIN dim_date d ON u.date_key = d.date_key
)
SELECT
    economic_period,
    COUNT(*)                                          AS month_count,
    ROUND(AVG(unemployment_rate), 2)                   AS avg_unemployment_pct,
    ROUND(MAX(unemployment_rate), 2)                   AS peak_unemployment_pct,
    ROUND(AVG(youth_unemployment_rate), 2)             AS avg_youth_unemployment_pct,
    ROUND(AVG(long_term_unemployment_rate), 2)         AS avg_long_term_unemployment_pct,
    ROUND(AVG(labour_force_participation_rate), 2)     AS avg_participation_rate_pct
FROM period_data
WHERE economic_period IS NOT NULL
GROUP BY economic_period
ORDER BY economic_period;


-- -----------------------------------------------------------------------------
-- 5. LABOUR MARKET HEALTH INDEX
--    Composite score (0-100) using unemployment rate and participation rate.
--    Lower unemployment and higher participation yield a higher score.
-- -----------------------------------------------------------------------------
WITH bounds AS (
    SELECT
        MIN(unemployment_rate)                AS min_unemp,
        MAX(unemployment_rate)                AS max_unemp,
        MIN(labour_force_participation_rate)  AS min_part,
        MAX(labour_force_participation_rate)  AS max_part
    FROM fact_unemployment
    WHERE unemployment_rate IS NOT NULL
      AND labour_force_participation_rate IS NOT NULL
),
scored AS (
    SELECT
        d.year,
        d.month,
        d.date_key,
        u.unemployment_rate,
        u.labour_force_participation_rate,
        -- Normalise unemployment: 0 = worst (highest), 100 = best (lowest)
        ROUND(
            (1.0 - (u.unemployment_rate - b.min_unemp)
                  / NULLIF(b.max_unemp - b.min_unemp, 0)) * 100.0, 2
        ) AS unemployment_score,
        -- Normalise participation: 0 = worst (lowest), 100 = best (highest)
        ROUND(
            (u.labour_force_participation_rate - b.min_part)
            / NULLIF(b.max_part - b.min_part, 0) * 100.0, 2
        ) AS participation_score
    FROM fact_unemployment u
    JOIN dim_date d ON u.date_key = d.date_key
    CROSS JOIN bounds b
    WHERE u.unemployment_rate IS NOT NULL
      AND u.labour_force_participation_rate IS NOT NULL
)
SELECT
    year,
    month,
    date_key,
    unemployment_rate,
    labour_force_participation_rate,
    unemployment_score,
    participation_score,
    -- Composite: 60% weight on unemployment, 40% on participation
    ROUND(0.60 * unemployment_score + 0.40 * participation_score, 2)
                                                      AS labour_market_health_index
FROM scored
ORDER BY year, month;

-- =============================================================================
-- END OF UNEMPLOYMENT ANALYSIS
-- =============================================================================
