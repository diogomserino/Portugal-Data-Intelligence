-- =============================================================================
-- Portugal Data Intelligence - Fiscal Structure Analysis Queries
-- =============================================================================
-- Database : portugal_data_intelligence.db (SQLite)
-- Table    : fact_fiscal joined with dim_date
-- Period   : 2010 to 2025 (annual, YYYY-Q4 keys)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. FISCAL BALANCE TREND
--    Revenue vs expenditure and implied budget balance.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(f.total_revenue_pct_gdp, 1)          AS revenue_pct_gdp,
    ROUND(f.total_expenditure_pct_gdp, 1)      AS expenditure_pct_gdp,
    ROUND(
        f.total_revenue_pct_gdp -
        f.total_expenditure_pct_gdp, 1
    )                                          AS fiscal_balance_pct_gdp,
    CASE
        WHEN f.total_revenue_pct_gdp >= f.total_expenditure_pct_gdp
        THEN 'surplus' ELSE 'deficit'
    END                                        AS balance_type
FROM fact_fiscal f
JOIN dim_date d ON f.date_key = d.date_key
ORDER BY d.year;


-- -----------------------------------------------------------------------------
-- 2. EXPENDITURE COMPOSITION
--    How government spending is allocated across functions.
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(f.health_expenditure_pct, 1)         AS health_pct_gdp,
    ROUND(f.education_expenditure_pct, 1)      AS education_pct_gdp,
    ROUND(f.social_protection_pct, 1)          AS social_protection_pct_gdp,
    ROUND(f.interest_payments_pct, 1)          AS interest_payments_pct_gdp,
    ROUND(
        f.total_expenditure_pct_gdp
        - f.health_expenditure_pct
        - f.education_expenditure_pct
        - f.social_protection_pct
        - f.interest_payments_pct, 1
    )                                          AS other_expenditure_pct_gdp
FROM fact_fiscal f
JOIN dim_date d ON f.date_key = d.date_key
ORDER BY d.year;


-- -----------------------------------------------------------------------------
-- 3. INTEREST BURDEN EVOLUTION
--    Interest payments as share of revenue (fiscal sustainability indicator).
-- -----------------------------------------------------------------------------
SELECT
    d.year,
    ROUND(f.interest_payments_pct, 2)          AS interest_pct_gdp,
    ROUND(
        f.interest_payments_pct /
        NULLIF(f.total_revenue_pct_gdp, 0) * 100,
        1
    )                                          AS interest_as_pct_of_revenue
FROM fact_fiscal f
JOIN dim_date d ON f.date_key = d.date_key
WHERE f.interest_payments_pct IS NOT NULL
ORDER BY d.year;
