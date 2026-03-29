-- =============================================================================
-- Portugal Data Intelligence - Public Debt Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_public_debt joined with dim_date (and fact_gdp)
-- Period   : 2010-Q1 to 2025-Q4
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. DEBT SUSTAINABILITY METRICS
--    Debt-to-GDP trend with traffic light classification.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.quarter,
    d.date_key,
    ROUND(pd.total_debt, 2)                           AS total_debt_eur_m,
    ROUND(pd.debt_to_gdp_ratio, 2)                    AS debt_to_gdp_pct,
    CASE
        WHEN pd.debt_to_gdp_ratio < 60   THEN 'Green (< 60%)'
        WHEN pd.debt_to_gdp_ratio < 90   THEN 'Yellow (60-90%)'
        WHEN pd.debt_to_gdp_ratio < 120  THEN 'Orange (90-120%)'
        ELSE                                   'Red (>= 120%)'
    END                                               AS sustainability_traffic_light,
    -- Quarter-over-quarter change
    ROUND(
        pd.debt_to_gdp_ratio
        - LAG(pd.debt_to_gdp_ratio, 1) OVER (ORDER BY d.year, d.quarter), 2
    )                                                 AS qoq_change_pp,
    -- Year-over-year change
    ROUND(
        pd.debt_to_gdp_ratio
        - LAG(pd.debt_to_gdp_ratio, 4) OVER (ORDER BY d.year, d.quarter), 2
    )                                                 AS yoy_change_pp,
    -- Direction indicator
    CASE
        WHEN pd.debt_to_gdp_ratio < LAG(pd.debt_to_gdp_ratio, 4)
                OVER (ORDER BY d.year, d.quarter)
            THEN 'Improving'
        WHEN pd.debt_to_gdp_ratio > LAG(pd.debt_to_gdp_ratio, 4)
                OVER (ORDER BY d.year, d.quarter)
            THEN 'Deteriorating'
        ELSE 'Stable'
    END                                               AS trend_direction
FROM fact_public_debt pd
JOIN dim_date d ON pd.date_key = d.date_key
ORDER BY d.year, d.quarter;


-- -----------------------------------------------------------------------------
-- 2. FISCAL BALANCE TREND
--    Budget deficit/surplus evolution with annual aggregation.
-- -----------------------------------------------------------------------------
WITH annual_fiscal AS (
    SELECT
        d.year,
        AVG(pd.budget_deficit)     AS avg_budget_balance_pct,
        MIN(pd.budget_deficit)     AS worst_quarter_pct,
        MAX(pd.budget_deficit)     AS best_quarter_pct,
        COUNT(*)                   AS quarters_reported
    FROM fact_public_debt pd
    JOIN dim_date d ON pd.date_key = d.date_key
    GROUP BY d.year
)
SELECT
    year,
    quarters_reported,
    ROUND(avg_budget_balance_pct, 2)                  AS avg_budget_balance_pct_gdp,
    ROUND(worst_quarter_pct, 2)                       AS worst_quarter_pct_gdp,
    ROUND(best_quarter_pct, 2)                        AS best_quarter_pct_gdp,
    CASE
        WHEN avg_budget_balance_pct >= 0 THEN 'Surplus'
        WHEN avg_budget_balance_pct >= -3 THEN 'Moderate deficit'
        ELSE                                   'Excessive deficit'
    END                                               AS fiscal_status,
    -- Change vs previous year
    ROUND(
        avg_budget_balance_pct
        - LAG(avg_budget_balance_pct, 1) OVER (ORDER BY year), 2
    )                                                 AS yoy_change_pp
FROM annual_fiscal
ORDER BY year;


-- -----------------------------------------------------------------------------
-- 3. DEBT COMPOSITION
--    External vs domestic debt share over time.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    d.quarter,
    d.date_key,
    ROUND(pd.total_debt, 2)                           AS total_debt_eur_m,
    ROUND(pd.external_debt_share_estimated, 2)                  AS external_debt_share_pct,
    ROUND(100.0 - pd.external_debt_share_estimated, 2)          AS domestic_debt_share_pct,
    -- Absolute amounts (estimated from share)
    ROUND(pd.total_debt * pd.external_debt_share_estimated / 100.0, 2)
                                                      AS external_debt_eur_m,
    ROUND(pd.total_debt * (100.0 - pd.external_debt_share_estimated) / 100.0, 2)
                                                      AS domestic_debt_eur_m,
    -- YoY change in external share
    ROUND(
        pd.external_debt_share_estimated
        - LAG(pd.external_debt_share_estimated, 4) OVER (ORDER BY d.year, d.quarter), 2
    )                                                 AS external_share_yoy_change_pp
FROM fact_public_debt pd
JOIN dim_date d ON pd.date_key = d.date_key
WHERE pd.external_debt_share_estimated IS NOT NULL
ORDER BY d.year, d.quarter;


-- -----------------------------------------------------------------------------
-- 4. DEBT VS GDP GROWTH
--    Side-by-side comparison of debt growth and GDP growth by quarter.
-- -----------------------------------------------------------------------------
WITH debt_growth AS (
    SELECT
        d.year,
        d.quarter,
        d.date_key,
        pd.total_debt,
        pd.debt_to_gdp_ratio,
        ROUND(
            (pd.total_debt - LAG(pd.total_debt, 4)
                OVER (ORDER BY d.year, d.quarter))
            / NULLIF(LAG(pd.total_debt, 4)
                OVER (ORDER BY d.year, d.quarter), 0) * 100.0, 2
        )                                             AS debt_yoy_growth_pct
    FROM fact_public_debt pd
    JOIN dim_date d ON pd.date_key = d.date_key
)
SELECT
    dg.year,
    dg.quarter,
    dg.date_key,
    ROUND(dg.total_debt, 2)                           AS total_debt_eur_m,
    dg.debt_yoy_growth_pct,
    ROUND(g.nominal_gdp, 2)                           AS nominal_gdp_eur_m,
    g.gdp_growth_yoy                                  AS gdp_yoy_growth_pct,
    -- Differential: if debt grows faster than GDP, ratio rises
    ROUND(
        COALESCE(dg.debt_yoy_growth_pct, 0)
        - COALESCE(g.gdp_growth_yoy, 0), 2
    )                                                 AS debt_gdp_growth_gap_pp,
    CASE
        WHEN dg.debt_yoy_growth_pct IS NOT NULL
         AND g.gdp_growth_yoy IS NOT NULL
         AND dg.debt_yoy_growth_pct > g.gdp_growth_yoy
            THEN 'Debt outpacing GDP'
        WHEN dg.debt_yoy_growth_pct IS NOT NULL
         AND g.gdp_growth_yoy IS NOT NULL
            THEN 'GDP outpacing debt'
        ELSE 'Insufficient data'
    END                                               AS dynamics
FROM debt_growth dg
LEFT JOIN fact_gdp g ON dg.date_key = g.date_key
ORDER BY dg.year, dg.quarter;


-- -----------------------------------------------------------------------------
-- 5. FISCAL CONSOLIDATION PERIODS
--    Identify periods of consecutive quarters with deficit reduction
--    (i.e., budget balance improving quarter over quarter).
-- -----------------------------------------------------------------------------
WITH deficit_change AS (
    SELECT
        d.year,
        d.quarter,
        d.date_key,
        pd.budget_deficit,
        LAG(pd.budget_deficit, 1) OVER (ORDER BY d.year, d.quarter)
                                                      AS prev_quarter_deficit,
        pd.budget_deficit - LAG(pd.budget_deficit, 1) OVER (ORDER BY d.year, d.quarter)
                                                      AS qoq_change,
        CASE
            WHEN pd.budget_deficit > LAG(pd.budget_deficit, 1)
                    OVER (ORDER BY d.year, d.quarter)
            THEN 1  -- Improving (deficit shrinking or surplus growing)
            ELSE 0
        END                                           AS is_improving
    FROM fact_public_debt pd
    JOIN dim_date d ON pd.date_key = d.date_key
    WHERE pd.budget_deficit IS NOT NULL
),
consolidation_groups AS (
    SELECT
        *,
        SUM(CASE WHEN is_improving = 0 THEN 1 ELSE 0 END) OVER (
            ORDER BY year, quarter
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS group_id
    FROM deficit_change
    WHERE prev_quarter_deficit IS NOT NULL
),
episodes AS (
    SELECT
        group_id,
        MIN(date_key)                                 AS episode_start,
        MAX(date_key)                                 AS episode_end,
        COUNT(*)                                      AS consecutive_quarters,
        ROUND(SUM(qoq_change), 2)                    AS total_improvement_pp,
        ROUND(MIN(budget_deficit), 2)                 AS starting_deficit_pct,
        ROUND(MAX(budget_deficit), 2)                 AS ending_deficit_pct
    FROM consolidation_groups
    WHERE is_improving = 1
    GROUP BY group_id
    HAVING consecutive_quarters >= 2  -- At least 2 consecutive improving quarters
)
SELECT
    episode_start,
    episode_end,
    consecutive_quarters,
    total_improvement_pp,
    starting_deficit_pct                              AS worst_balance_in_episode_pct,
    ending_deficit_pct                                AS best_balance_in_episode_pct
FROM episodes
ORDER BY consecutive_quarters DESC, episode_start;

-- =============================================================================
-- END OF PUBLIC DEBT ANALYSIS
-- =============================================================================
