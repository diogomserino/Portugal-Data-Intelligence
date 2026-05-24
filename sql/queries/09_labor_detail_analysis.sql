-- =============================================================================
-- Portugal Data Intelligence - Labour Market Detail Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_labor_detail joined with dim_date, fact_unemployment
-- Period   : 2010 to 2025 (annual, YYYY-Q4 keys)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. SECTORAL EMPLOYMENT STRUCTURE
--    Services, industry, agriculture shares over time.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(l.employment_services_pct, 1)      AS services_pct,
    ROUND(l.employment_industry_pct, 1)      AS industry_pct,
    ROUND(l.employment_agriculture_pct, 1)   AS agriculture_pct,
    ROUND(
        l.employment_services_pct +
        l.employment_industry_pct +
        l.employment_agriculture_pct, 1
    )                                        AS total_check
FROM fact_labor_detail l
JOIN dim_date d ON l.date_key = d.date_key
ORDER BY d.year;


-- -----------------------------------------------------------------------------
-- 2. REAL WAGE AND PRODUCTIVITY DIVERGENCE
--    Gap between real wage growth and labour productivity growth.
--    Positive = wages rising faster than productivity (cost pressure).
-- -----------------------------------------------------------------------------
WITH trends AS (
    SELECT
        d.year,
        l.real_wage_index,
        l.labour_productivity_index,
        LAG(l.real_wage_index) OVER (ORDER BY d.year)              AS prev_wage,
        LAG(l.labour_productivity_index) OVER (ORDER BY d.year)    AS prev_prod
    FROM fact_labor_detail l
    JOIN dim_date d ON l.date_key = d.date_key
)
SELECT
    year,
    ROUND(real_wage_index, 1)                                    AS real_wage_idx,
    ROUND(labour_productivity_index, 1)                          AS productivity_idx,
    ROUND((real_wage_index / prev_wage - 1) * 100, 2)           AS wage_growth_yoy_pct,
    ROUND((labour_productivity_index / prev_prod - 1) * 100, 2) AS productivity_growth_yoy_pct,
    ROUND(
        (real_wage_index / prev_wage - 1) * 100 -
        (labour_productivity_index / prev_prod - 1) * 100,
        2
    )                                                            AS wage_productivity_gap_pp
FROM trends
WHERE prev_wage IS NOT NULL
ORDER BY year;


-- -----------------------------------------------------------------------------
-- 3. SERVICES SECTOR DOMINANCE TREND
--    Long-run shift from agriculture/industry to services.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(l.employment_services_pct, 1)    AS services_pct,
    ROUND(l.employment_industry_pct +
          l.employment_agriculture_pct, 1) AS goods_producing_pct
FROM fact_labor_detail l
JOIN dim_date d ON l.date_key = d.date_key
ORDER BY d.year;
