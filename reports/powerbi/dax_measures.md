# DAX Measures Reference

## Portugal Data Intelligence - Power BI Dashboard

**Version:** 1.0
**Date:** 17 March 2026
**Total Measures:** 39

---

## Table of Contents

1. [KPI Measures (Latest Values)](#1-kpi-measures)
2. [Year-on-Year Growth Measures](#2-year-on-year-growth-measures)
3. [Moving Average Measures](#3-moving-average-measures)
4. [Derived / Calculated Measures](#4-derived--calculated-measures)
5. [Period Comparison Measures](#5-period-comparison-measures)
6. [Formatting Measures](#6-formatting-measures)

---

## Setup: Measures Table

Before creating measures, add a disconnected measures table to keep the model organised.

```dax
_Measures = ROW("Placeholder", BLANK())
```

All measures below should be created in this `_Measures` table and organised into Display Folders matching the section headings.

---

## 1. KPI Measures

### 1.1 Latest GDP (Nominal)

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest GDP` |
| **Display Folder** | KPI Measures |
| **Format String** | `#,##0 "M"` |
| **Used On** | Page 1 (Executive Overview), Page 2 (GDP & Growth) |
| **Description** | Returns the most recent nominal GDP value in EUR millions. |

```dax
Latest GDP =
VAR _LastDate =
    CALCULATE(
        MAX(fact_gdp[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_gdp[nominal_gdp]),
        fact_gdp[date_key] = _LastDate
    )
```

---

### 1.2 Latest GDP Growth

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest GDP Growth` |
| **Display Folder** | KPI Measures |
| **Format String** | `+0.0%;-0.0%;0.0%` |
| **Used On** | Page 1 (Executive Overview), Page 2 (GDP & Growth) |
| **Description** | Returns the most recent quarter-on-quarter GDP growth rate. |

```dax
Latest GDP Growth =
VAR _LastDate =
    CALCULATE(
        MAX(fact_gdp[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_gdp[gdp_growth_yoy]),
        fact_gdp[date_key] = _LastDate
    ) / 100
```

---

### 1.3 Latest GDP Per Capita

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest GDP Per Capita` |
| **Display Folder** | KPI Measures |
| **Format String** | `€#,##0` |
| **Used On** | Page 1 (Executive Overview), Page 2 (GDP & Growth) |
| **Description** | Returns the most recent GDP per capita value in EUR. |

```dax
Latest GDP Per Capita =
VAR _LastDate =
    CALCULATE(
        MAX(fact_gdp[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_gdp[gdp_per_capita]),
        fact_gdp[date_key] = _LastDate
    )
```

---

### 1.4 Latest Unemployment Rate

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest Unemployment Rate` |
| **Display Folder** | KPI Measures |
| **Format String** | `0.0%` |
| **Used On** | Page 1 (Executive Overview), Page 3 (Labour Market) |
| **Description** | Returns the most recent general unemployment rate. |

```dax
Latest Unemployment Rate =
VAR _LastDate =
    CALCULATE(
        MAX(fact_unemployment[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_unemployment[unemployment_rate]),
        fact_unemployment[date_key] = _LastDate
    ) / 100
```

---

### 1.5 Latest Youth Unemployment

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest Youth Unemployment` |
| **Display Folder** | KPI Measures |
| **Format String** | `0.0%` |
| **Used On** | Page 1 (Executive Overview), Page 3 (Labour Market) |
| **Description** | Returns the most recent youth unemployment rate (under 25). |

```dax
Latest Youth Unemployment =
VAR _LastDate =
    CALCULATE(
        MAX(fact_unemployment[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_unemployment[youth_unemployment_rate]),
        fact_unemployment[date_key] = _LastDate
    ) / 100
```

---

### 1.6 Latest HICP

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest HICP` |
| **Display Folder** | KPI Measures |
| **Format String** | `0.0%` |
| **Used On** | Page 1 (Executive Overview), Page 5 (Prices & Fiscal) |
| **Description** | Returns the most recent HICP inflation rate. |

```dax
Latest HICP =
VAR _LastDate =
    CALCULATE(
        MAX(fact_inflation[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_inflation[hicp]),
        fact_inflation[date_key] = _LastDate
    ) / 100
```

---

### 1.7 Latest Debt to GDP

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest Debt to GDP` |
| **Display Folder** | KPI Measures |
| **Format String** | `0.0%` |
| **Used On** | Page 1 (Executive Overview), Page 5 (Prices & Fiscal) |
| **Description** | Returns the most recent debt-to-GDP ratio. |

```dax
Latest Debt to GDP =
VAR _LastDate =
    CALCULATE(
        MAX(fact_public_debt[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_public_debt[debt_to_gdp_ratio]),
        fact_public_debt[date_key] = _LastDate
    ) / 100
```

---

### 1.8 Latest ECB Rate

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest ECB Rate` |
| **Display Folder** | KPI Measures |
| **Format String** | `0.00%` |
| **Used On** | Page 1 (Executive Overview), Page 4 (Financial Conditions) |
| **Description** | Returns the most recent ECB main refinancing rate. |

```dax
Latest ECB Rate =
VAR _LastDate =
    CALCULATE(
        MAX(fact_interest_rates[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_interest_rates[ecb_main_refinancing_rate]),
        fact_interest_rates[date_key] = _LastDate
    ) / 100
```

---

### 1.9 Latest Euribor 12M

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest Euribor 12M` |
| **Display Folder** | KPI Measures |
| **Format String** | `0.00%` |
| **Used On** | Page 1 (Executive Overview), Page 4 (Financial Conditions) |
| **Description** | Returns the most recent 12-month Euribor rate. |

```dax
Latest Euribor 12M =
VAR _LastDate =
    CALCULATE(
        MAX(fact_interest_rates[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_interest_rates[euribor_12m]),
        fact_interest_rates[date_key] = _LastDate
    ) / 100
```

---

### 1.10 Latest PT 10Y Bond Yield

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest PT 10Y Bond` |
| **Display Folder** | KPI Measures |
| **Format String** | `0.00%` |
| **Used On** | Page 4 (Financial Conditions) |
| **Description** | Returns the most recent Portuguese 10-year government bond yield. |

```dax
Latest PT 10Y Bond =
VAR _LastDate =
    CALCULATE(
        MAX(fact_interest_rates[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_interest_rates[portugal_10y_bond_yield]),
        fact_interest_rates[date_key] = _LastDate
    ) / 100
```

---

### 1.11 Latest Total Credit

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest Total Credit` |
| **Display Folder** | KPI Measures |
| **Format String** | `#,##0 "M"` |
| **Used On** | Page 1 (Executive Overview), Page 4 (Financial Conditions) |
| **Description** | Returns the most recent total credit to the economy in EUR millions. |

```dax
Latest Total Credit =
VAR _LastDate =
    CALCULATE(
        MAX(fact_credit[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_credit[total_credit]),
        fact_credit[date_key] = _LastDate
    )
```

---

### 1.12 Latest NPL Ratio

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest NPL Ratio` |
| **Display Folder** | KPI Measures |
| **Format String** | `0.0%` |
| **Used On** | Page 4 (Financial Conditions) |
| **Description** | Returns the most recent non-performing loan ratio. |

```dax
Latest NPL Ratio =
VAR _LastDate =
    CALCULATE(
        MAX(fact_credit[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_credit[npl_ratio]),
        fact_credit[date_key] = _LastDate
    ) / 100
```

---

### 1.13 Latest Budget Balance

| Property | Value |
|----------|-------|
| **Measure Name** | `Latest Budget Balance` |
| **Display Folder** | KPI Measures |
| **Format String** | `+0.0%;-0.0%;0.0%` |
| **Used On** | Page 5 (Prices & Fiscal) |
| **Description** | Returns the most recent government budget balance as a percentage of GDP. |

```dax
Latest Budget Balance =
VAR _LastDate =
    CALCULATE(
        MAX(fact_public_debt[date_key]),
        ALLSELECTED(dim_date)
    )
RETURN
    CALCULATE(
        SUM(fact_public_debt[budget_deficit]),
        fact_public_debt[date_key] = _LastDate
    ) / 100
```

---

## 2. Year-on-Year Growth Measures

### 2.1 GDP YoY Growth

| Property | Value |
|----------|-------|
| **Measure Name** | `GDP YoY Growth` |
| **Display Folder** | YoY Growth |
| **Format String** | `+0.0%;-0.0%;0.0%` |
| **Used On** | Page 1, Page 2, Page 6 |
| **Description** | Year-on-year growth in nominal GDP, comparing the current quarter to the same quarter of the previous year. |

```dax
GDP YoY Growth =
VAR _CurrentGDP =
    SUM(fact_gdp[nominal_gdp])
VAR _PriorYearGDP =
    CALCULATE(
        SUM(fact_gdp[nominal_gdp]),
        DATEADD(dim_date[full_date], -1, YEAR)
    )
RETURN
    IF(
        NOT ISBLANK(_PriorYearGDP) && _PriorYearGDP <> 0,
        DIVIDE(_CurrentGDP - _PriorYearGDP, _PriorYearGDP),
        BLANK()
    )
```

---

### 2.2 Unemployment YoY Change

| Property | Value |
|----------|-------|
| **Measure Name** | `Unemployment YoY Change` |
| **Display Folder** | YoY Growth |
| **Format String** | `+0.0;-0.0;0.0` (percentage points) |
| **Used On** | Page 1, Page 3, Page 6 |
| **Description** | Year-on-year change in unemployment rate in percentage points. A negative value indicates improvement. |

```dax
Unemployment YoY Change =
VAR _CurrentRate =
    AVERAGE(fact_unemployment[unemployment_rate])
VAR _PriorYearRate =
    CALCULATE(
        AVERAGE(fact_unemployment[unemployment_rate]),
        DATEADD(dim_date[full_date], -1, YEAR)
    )
RETURN
    IF(
        NOT ISBLANK(_PriorYearRate),
        _CurrentRate - _PriorYearRate,
        BLANK()
    )
```

---

### 2.3 Credit YoY Growth

| Property | Value |
|----------|-------|
| **Measure Name** | `Credit YoY Growth` |
| **Display Folder** | YoY Growth |
| **Format String** | `+0.0%;-0.0%;0.0%` |
| **Used On** | Page 1, Page 4, Page 6 |
| **Description** | Year-on-year percentage change in total credit to the economy. |

```dax
Credit YoY Growth =
VAR _CurrentCredit =
    SUM(fact_credit[total_credit])
VAR _PriorYearCredit =
    CALCULATE(
        SUM(fact_credit[total_credit]),
        DATEADD(dim_date[full_date], -1, YEAR)
    )
RETURN
    IF(
        NOT ISBLANK(_PriorYearCredit) && _PriorYearCredit <> 0,
        DIVIDE(_CurrentCredit - _PriorYearCredit, _PriorYearCredit),
        BLANK()
    )
```

---

### 2.4 Interest Rate YoY Change

| Property | Value |
|----------|-------|
| **Measure Name** | `Euribor 12M YoY Change` |
| **Display Folder** | YoY Growth |
| **Format String** | `+0.00;-0.00;0.00` (percentage points) |
| **Used On** | Page 1, Page 4, Page 6 |
| **Description** | Year-on-year change in the 12-month Euribor rate in percentage points. |

```dax
Euribor 12M YoY Change =
VAR _CurrentRate =
    AVERAGE(fact_interest_rates[euribor_12m])
VAR _PriorYearRate =
    CALCULATE(
        AVERAGE(fact_interest_rates[euribor_12m]),
        DATEADD(dim_date[full_date], -1, YEAR)
    )
RETURN
    IF(
        NOT ISBLANK(_PriorYearRate),
        _CurrentRate - _PriorYearRate,
        BLANK()
    )
```

---

### 2.5 Inflation YoY Change

| Property | Value |
|----------|-------|
| **Measure Name** | `HICP YoY Change` |
| **Display Folder** | YoY Growth |
| **Format String** | `+0.0;-0.0;0.0` (percentage points) |
| **Used On** | Page 1, Page 5, Page 6 |
| **Description** | Year-on-year change in HICP inflation rate in percentage points. |

```dax
HICP YoY Change =
VAR _CurrentHICP =
    AVERAGE(fact_inflation[hicp])
VAR _PriorYearHICP =
    CALCULATE(
        AVERAGE(fact_inflation[hicp]),
        DATEADD(dim_date[full_date], -1, YEAR)
    )
RETURN
    IF(
        NOT ISBLANK(_PriorYearHICP),
        _CurrentHICP - _PriorYearHICP,
        BLANK()
    )
```

---

### 2.6 Debt-to-GDP YoY Change

| Property | Value |
|----------|-------|
| **Measure Name** | `Debt to GDP YoY Change` |
| **Display Folder** | YoY Growth |
| **Format String** | `+0.0;-0.0;0.0` (percentage points) |
| **Used On** | Page 1, Page 5, Page 6 |
| **Description** | Year-on-year change in debt-to-GDP ratio in percentage points. A negative value indicates fiscal improvement. |

```dax
Debt to GDP YoY Change =
VAR _CurrentRatio =
    AVERAGE(fact_public_debt[debt_to_gdp_ratio])
VAR _PriorYearRatio =
    CALCULATE(
        AVERAGE(fact_public_debt[debt_to_gdp_ratio]),
        DATEADD(dim_date[full_date], -1, YEAR)
    )
RETURN
    IF(
        NOT ISBLANK(_PriorYearRatio),
        _CurrentRatio - _PriorYearRatio,
        BLANK()
    )
```

---

## 3. Moving Average Measures

### 3.1 Unemployment 3M Moving Average

| Property | Value |
|----------|-------|
| **Measure Name** | `Unemployment 3M MA` |
| **Display Folder** | Moving Averages |
| **Format String** | `0.0` |
| **Used On** | Page 3 (Labour Market) |
| **Description** | 3-month rolling average of the general unemployment rate, smoothing out short-term volatility. |

```dax
Unemployment 3M MA =
AVERAGEX(
    DATESINPERIOD(
        dim_date[full_date],
        MAX(dim_date[full_date]),
        -3,
        MONTH
    ),
    CALCULATE(AVERAGE(fact_unemployment[unemployment_rate]))
)
```

---

### 3.2 Unemployment 12M Moving Average

| Property | Value |
|----------|-------|
| **Measure Name** | `Unemployment 12M MA` |
| **Display Folder** | Moving Averages |
| **Format String** | `0.0` |
| **Used On** | Page 3 (Labour Market) |
| **Description** | 12-month rolling average of the general unemployment rate, revealing the underlying trend. |

```dax
Unemployment 12M MA =
AVERAGEX(
    DATESINPERIOD(
        dim_date[full_date],
        MAX(dim_date[full_date]),
        -12,
        MONTH
    ),
    CALCULATE(AVERAGE(fact_unemployment[unemployment_rate]))
)
```

---

### 3.3 HICP 3M Moving Average

| Property | Value |
|----------|-------|
| **Measure Name** | `HICP 3M MA` |
| **Display Folder** | Moving Averages |
| **Format String** | `0.0` |
| **Used On** | Page 5 (Prices & Fiscal) |
| **Description** | 3-month rolling average of HICP inflation. |

```dax
HICP 3M MA =
AVERAGEX(
    DATESINPERIOD(
        dim_date[full_date],
        MAX(dim_date[full_date]),
        -3,
        MONTH
    ),
    CALCULATE(AVERAGE(fact_inflation[hicp]))
)
```

---

### 3.4 HICP 12M Moving Average

| Property | Value |
|----------|-------|
| **Measure Name** | `HICP 12M MA` |
| **Display Folder** | Moving Averages |
| **Format String** | `0.0` |
| **Used On** | Page 5 (Prices & Fiscal) |
| **Description** | 12-month rolling average of HICP inflation, showing the underlying price trend. |

```dax
HICP 12M MA =
AVERAGEX(
    DATESINPERIOD(
        dim_date[full_date],
        MAX(dim_date[full_date]),
        -12,
        MONTH
    ),
    CALCULATE(AVERAGE(fact_inflation[hicp]))
)
```

---

### 3.5 Credit 3M Moving Average

| Property | Value |
|----------|-------|
| **Measure Name** | `Total Credit 3M MA` |
| **Display Folder** | Moving Averages |
| **Format String** | `#,##0 "M"` |
| **Used On** | Page 4 (Financial Conditions) |
| **Description** | 3-month rolling average of total credit to the economy. |

```dax
Total Credit 3M MA =
AVERAGEX(
    DATESINPERIOD(
        dim_date[full_date],
        MAX(dim_date[full_date]),
        -3,
        MONTH
    ),
    CALCULATE(SUM(fact_credit[total_credit]))
)
```

---

### 3.6 Euribor 12M 3-Month Moving Average

| Property | Value |
|----------|-------|
| **Measure Name** | `Euribor 12M 3M MA` |
| **Display Folder** | Moving Averages |
| **Format String** | `0.00` |
| **Used On** | Page 4 (Financial Conditions) |
| **Description** | 3-month rolling average of the 12-month Euribor rate. |

```dax
Euribor 12M 3M MA =
AVERAGEX(
    DATESINPERIOD(
        dim_date[full_date],
        MAX(dim_date[full_date]),
        -3,
        MONTH
    ),
    CALCULATE(AVERAGE(fact_interest_rates[euribor_12m]))
)
```

---

## 4. Derived / Calculated Measures

### 4.1 Sovereign Spread

| Property | Value |
|----------|-------|
| **Measure Name** | `Sovereign Spread` |
| **Display Folder** | Derived Measures |
| **Format String** | `0 "bps"` |
| **Used On** | Page 4 (Financial Conditions), Page 6 (Cross-Pillar) |
| **Description** | Spread between Portuguese 10-year government bond yield and the ECB rate, expressed in basis points. This serves as a proxy for sovereign risk premium. In a full implementation, the German Bund yield should be used as the benchmark; however, since Bund data is not available in the current data model, the ECB rate is used as an approximation. |

```dax
Sovereign Spread =
VAR _BondYield = AVERAGE(fact_interest_rates[portugal_10y_bond_yield])
VAR _ECBRate = AVERAGE(fact_interest_rates[ecb_main_refinancing_rate])
RETURN
    IF(
        NOT ISBLANK(_BondYield) && NOT ISBLANK(_ECBRate),
        (_BondYield - _ECBRate) * 100,
        BLANK()
    )
```

---

### 4.2 Real Interest Rate

| Property | Value |
|----------|-------|
| **Measure Name** | `Real Interest Rate` |
| **Display Folder** | Derived Measures |
| **Format String** | `+0.0%;-0.0%;0.0%` |
| **Used On** | Page 5 (Prices & Fiscal), Page 6 (Cross-Pillar) |
| **Description** | Real interest rate calculated as the ECB main refinancing rate minus the HICP inflation rate. Negative values indicate accommodative real monetary conditions. Uses the Fisher approximation. |

```dax
Real Interest Rate =
VAR _ECBRate = AVERAGE(fact_interest_rates[ecb_main_refinancing_rate])
VAR _HICP = AVERAGE(fact_inflation[hicp])
VAR _LastDateRates =
    CALCULATE(
        MAX(fact_interest_rates[date_key]),
        ALLSELECTED(dim_date)
    )
VAR _LastDateInflation =
    CALCULATE(
        MAX(fact_inflation[date_key]),
        ALLSELECTED(dim_date)
    )
VAR _LatestECB =
    CALCULATE(
        AVERAGE(fact_interest_rates[ecb_main_refinancing_rate]),
        fact_interest_rates[date_key] = _LastDateRates
    )
VAR _LatestHICP =
    CALCULATE(
        AVERAGE(fact_inflation[hicp]),
        fact_inflation[date_key] = _LastDateInflation
    )
RETURN
    IF(
        NOT ISBLANK(_ECBRate) && NOT ISBLANK(_HICP),
        (_ECBRate - _HICP) / 100,
        IF(
            NOT ISBLANK(_LatestECB) && NOT ISBLANK(_LatestHICP),
            (_LatestECB - _LatestHICP) / 100,
            BLANK()
        )
    )
```

---

### 4.3 Credit-to-GDP Ratio

| Property | Value |
|----------|-------|
| **Measure Name** | `Credit to GDP Ratio` |
| **Display Folder** | Derived Measures |
| **Format String** | `0.0%` |
| **Used On** | Page 4 (Financial Conditions), Page 6 (Cross-Pillar) |
| **Description** | Ratio of total credit to the economy relative to nominal GDP. This measure aligns the monthly credit data with the most recent quarterly GDP figure. A rising ratio may indicate credit-fuelled growth or financial deepening. |

```dax
Credit to GDP Ratio =
VAR _TotalCredit = SUM(fact_credit[total_credit])
VAR _LatestGDP =
    CALCULATE(
        SUM(fact_gdp[nominal_gdp]),
        LASTNONBLANK(dim_date[full_date], CALCULATE(SUM(fact_gdp[nominal_gdp])))
    )
VAR _AnnualisedGDP = _LatestGDP * 4
RETURN
    IF(
        NOT ISBLANK(_TotalCredit) && NOT ISBLANK(_AnnualisedGDP) && _AnnualisedGDP <> 0,
        DIVIDE(_TotalCredit, _AnnualisedGDP),
        BLANK()
    )
```

---

### 4.4 Youth Unemployment Gap

| Property | Value |
|----------|-------|
| **Measure Name** | `Youth Unemployment Gap` |
| **Display Folder** | Derived Measures |
| **Format String** | `0.0` (percentage points) |
| **Used On** | Page 3 (Labour Market), Page 6 (Cross-Pillar) |
| **Description** | Difference between the youth unemployment rate and the general unemployment rate in percentage points. A larger gap indicates disproportionate impact on young workers. |

```dax
Youth Unemployment Gap =
VAR _YouthRate = AVERAGE(fact_unemployment[youth_unemployment_rate])
VAR _GeneralRate = AVERAGE(fact_unemployment[unemployment_rate])
RETURN
    IF(
        NOT ISBLANK(_YouthRate) && NOT ISBLANK(_GeneralRate),
        _YouthRate - _GeneralRate,
        BLANK()
    )
```

---

### 4.5 Avg GDP Per Capita

| Property | Value |
|----------|-------|
| **Measure Name** | `Avg GDP Per Capita` |
| **Display Folder** | Derived Measures |
| **Format String** | `€#,##0` |
| **Used On** | Page 2 (GDP & Growth) |
| **Description** | Average GDP per capita for the selected period. Used in the per-capita trend chart. |

```dax
Avg GDP Per Capita =
AVERAGE(fact_gdp[gdp_per_capita])
```

---

## 5. Period Comparison Measures

### 5.1 Avg Unemployment by Period

| Property | Value |
|----------|-------|
| **Measure Name** | `Avg Unemployment by Period` |
| **Display Folder** | Period Comparisons |
| **Format String** | `0.0` |
| **Used On** | Page 3 (Labour Market), Page 6 (Cross-Pillar) |
| **Description** | Average unemployment rate within each economic period. Used in the crisis impact comparison bar chart and cross-pillar analysis. |

```dax
Avg Unemployment by Period =
AVERAGEX(
    FILTER(
        ALL(dim_date),
        dim_date[Economic Period] = SELECTEDVALUE(dim_date[Economic Period])
    ),
    CALCULATE(AVERAGE(fact_unemployment[unemployment_rate]))
)
```

---

### 5.2 Period GDP Growth

| Property | Value |
|----------|-------|
| **Measure Name** | `Period GDP Growth` |
| **Display Folder** | Period Comparisons |
| **Format String** | `+0.0%;-0.0%;0.0%` |
| **Used On** | Page 2 (GDP & Growth), Page 6 (Cross-Pillar) |
| **Description** | Average GDP growth rate for each economic period. Used in the period comparison table on the GDP page. |

```dax
Period GDP Growth =
AVERAGEX(
    FILTER(
        ALL(dim_date),
        dim_date[Economic Period] = SELECTEDVALUE(dim_date[Economic Period])
    ),
    CALCULATE(AVERAGE(fact_gdp[growth_rate]))
) / 100
```

---

### 5.3 Avg Budget Balance

| Property | Value |
|----------|-------|
| **Measure Name** | `Avg Budget Balance` |
| **Display Folder** | Period Comparisons |
| **Format String** | `+0.0%;-0.0%;0.0%` |
| **Used On** | Page 5 (Prices & Fiscal) |
| **Description** | Average government budget balance as a percentage of GDP. Used in the waterfall chart showing annual fiscal positions. |

```dax
Avg Budget Balance =
AVERAGE(fact_public_debt[budget_deficit]) / 100
```

---

## 6. Formatting Measures

### 6.1 GDP Growth Trend Arrow

| Property | Value |
|----------|-------|
| **Measure Name** | `GDP Growth Trend Arrow` |
| **Display Folder** | Formatting |
| **Format String** | (text) |
| **Used On** | Page 1 (Executive Overview) |
| **Description** | Returns a trend arrow (up, down, or flat) based on the direction of GDP growth compared to the prior year. Green up arrow for improvement, red down arrow for deterioration, amber flat arrow for stable (change within 0.5 pp). |

```dax
GDP Growth Trend Arrow =
VAR _Current = [Latest GDP Growth]
VAR _Prior =
    CALCULATE(
        SUM(fact_gdp[growth_rate]) / 100,
        DATEADD(dim_date[full_date], -1, YEAR)
    )
VAR _Change = _Current - _Prior
RETURN
    IF(
        ISBLANK(_Prior),
        "►",
        IF(
            _Change > 0.005, "▲",
            IF(_Change < -0.005, "▼", "►")
        )
    )
```

---

### 6.2 Unemployment Trend Arrow

| Property | Value |
|----------|-------|
| **Measure Name** | `Unemployment Trend Arrow` |
| **Display Folder** | Formatting |
| **Format String** | (text) |
| **Used On** | Page 1 (Executive Overview) |
| **Description** | Returns a trend arrow for unemployment. Note: for unemployment, DOWN is positive (improvement). Green down arrow = improving, red up arrow = worsening. |

```dax
Unemployment Trend Arrow =
VAR _Change = [Unemployment YoY Change]
RETURN
    IF(
        ISBLANK(_Change),
        "►",
        IF(
            _Change < -0.3, "▼",
            IF(_Change > 0.3, "▲", "►")
        )
    )
```

---

### 6.3 Inflation Trend Arrow

| Property | Value |
|----------|-------|
| **Measure Name** | `Inflation Trend Arrow` |
| **Display Folder** | Formatting |
| **Format String** | (text) |
| **Used On** | Page 1 (Executive Overview) |
| **Description** | Returns a trend arrow for inflation relative to the ECB 2% target. Converging towards target is positive. |

```dax
Inflation Trend Arrow =
VAR _CurrentHICP = [Latest HICP]
VAR _ECBTarget = 0.02
VAR _Change = [HICP YoY Change]
VAR _DistanceFromTarget = ABS(_CurrentHICP - _ECBTarget)
RETURN
    IF(
        ISBLANK(_CurrentHICP),
        "►",
        IF(
            _DistanceFromTarget <= 0.005, "►",
            IF(
                _CurrentHICP > _ECBTarget && _Change < 0, "▼",
                IF(
                    _CurrentHICP < _ECBTarget && _Change > 0, "▲",
                    IF(_Change > 0, "▲", "▼")
                )
            )
        )
    )
```

---

### 6.4 Credit Trend Arrow

| Property | Value |
|----------|-------|
| **Measure Name** | `Credit Trend Arrow` |
| **Display Folder** | Formatting |
| **Format String** | (text) |
| **Used On** | Page 1 (Executive Overview) |
| **Description** | Returns a trend arrow based on the direction of total credit growth. |

```dax
Credit Trend Arrow =
VAR _Growth = [Credit YoY Growth]
RETURN
    IF(
        ISBLANK(_Growth),
        "►",
        IF(
            _Growth > 0.01, "▲",
            IF(_Growth < -0.01, "▼", "►")
        )
    )
```

---

### 6.5 ECB Rate Trend Arrow

| Property | Value |
|----------|-------|
| **Measure Name** | `ECB Rate Trend Arrow` |
| **Display Folder** | Formatting |
| **Format String** | (text) |
| **Used On** | Page 1 (Executive Overview) |
| **Description** | Returns a trend arrow for the ECB rate based on year-on-year change. |

```dax
ECB Rate Trend Arrow =
VAR _CurrentRate =
    CALCULATE(
        AVERAGE(fact_interest_rates[ecb_main_refinancing_rate]),
        LASTNONBLANK(dim_date[full_date], CALCULATE(COUNTROWS(fact_interest_rates)))
    )
VAR _PriorYearRate =
    CALCULATE(
        AVERAGE(fact_interest_rates[ecb_main_refinancing_rate]),
        DATEADD(dim_date[full_date], -1, YEAR)
    )
VAR _Change = _CurrentRate - _PriorYearRate
RETURN
    IF(
        ISBLANK(_PriorYearRate),
        "►",
        IF(
            _Change > 0.1, "▲",
            IF(_Change < -0.1, "▼", "►")
        )
    )
```

---

### 6.6 Debt Trend Arrow

| Property | Value |
|----------|-------|
| **Measure Name** | `Debt Trend Arrow` |
| **Display Folder** | Formatting |
| **Format String** | (text) |
| **Used On** | Page 1 (Executive Overview) |
| **Description** | Returns a trend arrow for debt-to-GDP. Down arrow (green) indicates fiscal improvement (decreasing ratio). |

```dax
Debt Trend Arrow =
VAR _Change = [Debt to GDP YoY Change]
RETURN
    IF(
        ISBLANK(_Change),
        "►",
        IF(
            _Change < -1, "▼",
            IF(_Change > 1, "▲", "►")
        )
    )
```

---

## 7. Traffic Light Conditional Formatting Rules

These rules are applied via Conditional Formatting in Power BI visuals (Format pane > Conditional Formatting > Background colour / Font colour > Rules).

### 7.1 GDP Growth Traffic Light

| Condition | Colour | Hex |
|-----------|--------|-----|
| Growth > 2% | Green | `#386641` |
| Growth between 0% and 2% | Amber | `#D4A373` |
| Growth < 0% (recession) | Red | `#9B2226` |

### 7.2 Unemployment Traffic Light

| Condition | Colour | Hex |
|-----------|--------|-----|
| Rate < 7% | Green | `#386641` |
| Rate between 7% and 10% | Amber | `#D4A373` |
| Rate > 10% | Red | `#9B2226` |

### 7.3 Inflation Traffic Light

| Condition | Colour | Hex |
|-----------|--------|-----|
| HICP between 1% and 3% (near target) | Green | `#386641` |
| HICP between 0-1% or 3-5% | Amber | `#D4A373` |
| HICP < 0% (deflation) or > 5% | Red | `#9B2226` |

### 7.4 Debt-to-GDP Traffic Light

| Condition | Colour | Hex |
|-----------|--------|-----|
| Ratio < 60% (Maastricht compliant) | Green | `#386641` |
| Ratio between 60% and 100% | Amber | `#D4A373` |
| Ratio > 100% | Red | `#9B2226` |

### 7.5 NPL Ratio Traffic Light

| Condition | Colour | Hex |
|-----------|--------|-----|
| NPL < 3% | Green | `#386641` |
| NPL between 3% and 5% | Amber | `#D4A373` |
| NPL > 5% | Red | `#9B2226` |

### 7.6 Sovereign Spread Traffic Light

| Condition | Colour | Hex |
|-----------|--------|-----|
| Spread < 100 bps | Green | `#386641` |
| Spread between 100 and 300 bps | Amber | `#D4A373` |
| Spread > 300 bps | Red | `#9B2226` |

---

## 8. Calculated Columns Reference

These columns are created in Power BI's Data view (not measures).

### 8.1 dim_date: Economic Period

```dax
Economic Period =
SWITCH(
    TRUE(),
    dim_date[year] <= 2010, "Pre-Crisis",
    dim_date[year] = 2011, "Sovereign Crisis",
    dim_date[year] >= 2012 && dim_date[year] <= 2014, "Troika Programme",
    dim_date[year] >= 2015 && dim_date[year] <= 2019, "Recovery",
    dim_date[year] >= 2020 && dim_date[year] <= 2021, "COVID-19",
    dim_date[year] >= 2022, "Post-COVID"
)
```

### 8.2 dim_date: Period Sort Order

```dax
Period Sort Order =
SWITCH(
    dim_date[Economic Period],
    "Pre-Crisis", 1,
    "Sovereign Crisis", 2,
    "Troika Programme", 3,
    "Recovery", 4,
    "COVID-19", 5,
    "Post-COVID", 6
)
```

### 8.3 dim_date: Year-Quarter

```dax
Year-Quarter = dim_date[year] & "-Q" & dim_date[quarter]
```

### 8.4 dim_date: Year-Month

```dax
Year-Month = dim_date[year] & "-" & FORMAT(dim_date[full_date], "MM")
```

---

## 9. Measure Summary Table

| # | Measure Name | Category | Format | Pages |
|---|-------------|----------|--------|-------|
| 1 | Latest GDP | KPI | `#,##0 "M"` | 1, 2 |
| 2 | Latest GDP Growth | KPI | `+0.0%;-0.0%` | 1, 2 |
| 3 | Latest GDP Per Capita | KPI | `€#,##0` | 1, 2 |
| 4 | Latest Unemployment Rate | KPI | `0.0%` | 1, 3 |
| 5 | Latest Youth Unemployment | KPI | `0.0%` | 1, 3 |
| 6 | Latest HICP | KPI | `0.0%` | 1, 5 |
| 7 | Latest Debt to GDP | KPI | `0.0%` | 1, 5 |
| 8 | Latest ECB Rate | KPI | `0.00%` | 1, 4 |
| 9 | Latest Euribor 12M | KPI | `0.00%` | 1, 4 |
| 10 | Latest PT 10Y Bond | KPI | `0.00%` | 4 |
| 11 | Latest Total Credit | KPI | `#,##0 "M"` | 1, 4 |
| 12 | Latest NPL Ratio | KPI | `0.0%` | 4 |
| 13 | Latest Budget Balance | KPI | `+0.0%;-0.0%` | 5 |
| 14 | GDP YoY Growth | YoY Growth | `+0.0%;-0.0%` | 1, 2, 6 |
| 15 | Unemployment YoY Change | YoY Growth | `+0.0;-0.0` | 1, 3, 6 |
| 16 | Credit YoY Growth | YoY Growth | `+0.0%;-0.0%` | 1, 4, 6 |
| 17 | Euribor 12M YoY Change | YoY Growth | `+0.00;-0.00` | 1, 4, 6 |
| 18 | HICP YoY Change | YoY Growth | `+0.0;-0.0` | 1, 5, 6 |
| 19 | Debt to GDP YoY Change | YoY Growth | `+0.0;-0.0` | 1, 5, 6 |
| 20 | Unemployment 3M MA | Moving Avg | `0.0` | 3 |
| 21 | Unemployment 12M MA | Moving Avg | `0.0` | 3 |
| 22 | HICP 3M MA | Moving Avg | `0.0` | 5 |
| 23 | HICP 12M MA | Moving Avg | `0.0` | 5 |
| 24 | Total Credit 3M MA | Moving Avg | `#,##0 "M"` | 4 |
| 25 | Euribor 12M 3M MA | Moving Avg | `0.00` | 4 |
| 26 | Sovereign Spread | Derived | `0 "bps"` | 4, 6 |
| 27 | Real Interest Rate | Derived | `+0.0%;-0.0%` | 5, 6 |
| 28 | Credit to GDP Ratio | Derived | `0.0%` | 4, 6 |
| 29 | Youth Unemployment Gap | Derived | `0.0` | 3, 6 |
| 30 | Avg GDP Per Capita | Derived | `€#,##0` | 2 |
| 31 | Avg Unemployment by Period | Period | `0.0` | 3, 6 |
| 32 | Period GDP Growth | Period | `+0.0%;-0.0%` | 2, 6 |
| 33 | Avg Budget Balance | Period | `+0.0%;-0.0%` | 5 |
| 34 | GDP Growth Trend Arrow | Formatting | text | 1 |
| 35 | Unemployment Trend Arrow | Formatting | text | 1 |
| 36 | Inflation Trend Arrow | Formatting | text | 1 |
| 37 | Credit Trend Arrow | Formatting | text | 1 |
| 38 | ECB Rate Trend Arrow | Formatting | text | 1 |
| 39 | Debt Trend Arrow | Formatting | text | 1 |

---

## 10. Implementation Checklist

- [ ] Import all tables from SQLite database
- [ ] Create relationships as defined in dashboard_specification.md Section 1.3
- [ ] Add calculated columns to dim_date (Economic Period, Period Sort Order, Year-Quarter, Year-Month)
- [ ] Create `_Measures` table
- [ ] Create all 39 measures, organised into Display Folders
- [ ] Set format strings for each measure
- [ ] Mark dim_date as the Date table
- [ ] Disable Auto Date/Time in Options
- [ ] Hide foreign key columns from Report view
- [ ] Build Page 1: Executive Overview
- [ ] Build Page 2: GDP & Growth
- [ ] Build Page 3: Labour Market
- [ ] Build Page 4: Financial Conditions
- [ ] Build Page 5: Prices & Fiscal
- [ ] Build Page 6: Cross-Pillar Analysis
- [ ] Apply conditional formatting rules (Section 7)
- [ ] Create bookmarks for economic periods
- [ ] Create tooltip pages
- [ ] Set tab order for accessibility
- [ ] Add alt text to all visuals
- [ ] Test all slicers and cross-filtering
- [ ] Review on 1920x1080 and 1280x720 resolutions
- [ ] Publish to Power BI Service workspace
