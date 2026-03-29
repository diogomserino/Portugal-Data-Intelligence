# Power BI Dashboard Specification

## Portugal Data Intelligence

**Version:** 1.0
**Date:** 17 March 2026
**Author:** Portugal Data Intelligence
**Status:** Ready for Implementation

---

## Table of Contents

1. [Data Model](#1-data-model)
2. [DAX Measures Overview](#2-dax-measures-overview)
3. [Dashboard Pages](#3-dashboard-pages)
4. [Formatting Standards](#4-formatting-standards)
5. [Slicer Configuration](#5-slicer-configuration)
6. [Implementation Notes](#6-implementation-notes)

---

## 1. Data Model

### 1.1 Data Source Connection

| Property | Value |
|----------|-------|
| Source Type | SQLite Database (via ODBC) |
| Database Path | `data/database/portugal_data_intelligence.db` |
| Refresh Schedule | Weekly (Monday 06:00 UTC) |
| Import Mode | Import (full dataset) |

### 1.2 Star Schema Overview

The data model follows a classic star schema with two shared dimension tables and six fact tables, one per analytical pillar. All fact tables connect to `dim_date` via `date_key`. The `dim_source` table provides metadata for data provenance.

```
                           ┌──────────────────────┐
                           │      dim_source       │
                           │──────────────────────│
                           │ source_key (PK)       │
                           │ source_name           │
                           │ source_url            │
                           │ description           │
                           └──────────────────────┘


                           ┌──────────────────────┐
                           │      dim_date         │
                           │──────────────────────│
                           │ date_key (PK)         │
                           │ full_date             │
                           │ year                  │
                           │ quarter               │
                           │ month                 │
                           │ month_name            │
                           │ is_quarter_end        │
                           └──────────┬───────────┘
                                      │
            ┌─────────┬───────────┬───┴───┬───────────┬──────────┐
            │         │           │       │           │          │
            ▼         ▼           ▼       ▼           ▼          ▼
   ┌────────────┐ ┌──────────┐ ┌──────┐ ┌──────────┐ ┌────────────┐ ┌──────────────────────┐
   │ fact_gdp   │ │fact_unem-│ │fact_ │ │fact_inte-│ │fact_       │ │fact_public_          │
   │            │ │ployment  │ │credit│ │rest_rates│ │inflation   │ │debt                  │
   │ date_key   │ │ date_key │ │date_ │ │ date_key │ │ date_key   │ │ date_key             │
   │ nominal_gdp│ │ rate     │ │key   │ │ ecb_rate │ │ hicp       │ │ total_debt           │
   │ real_gdp   │ │ youth_   │ │total │ │ euribor_ │ │ cpi_       │ │ debt_to_gdp          │
   │ growth_rate│ │ rate     │ │ nfc  │ │ 3m       │ │  estimated │ │ external_debt_share_ │
   │ gdp_per_   │ │ lfp_rate │ │house │ │ euribor_ │ │ core       │ │  estimated           │
   │ capita     │ │          │ │npl_  │ │ 6m       │ │ is_        │ │ budget_balance       │
   │ source_key │ │source_key│ │ratio │ │ euribor_ │ │  provision-│ │ budget_deficit_      │
   │ is_        │ │ is_      │ │source│ │ 12m      │ │  al        │ │  annual              │
   │  provision-│ │  provisi-│ │_key  │ │ bond_10y │ │ source_key │ │ is_provisional       │
   │  al        │ │  onal    │ │ is_  │ │ source_  │ │            │ │ source_key           │
   │            │ │          │ │ prov-│ │ key      │ │            │ │                      │
   │            │ │          │ │ isio-│ │ is_      │ │            │ │                      │
   │            │ │          │ │ nal  │ │  provisi-│ │            │ │                      │
   │            │ │          │ │      │ │  onal    │ │            │ │                      │
   └────────────┘ └──────────┘ └──────┘ └──────────┘ └────────────┘ └──────────────────────┘
```

### 1.3 Relationship Definitions

| # | From Table | From Column | To Table | To Column | Cardinality | Cross-Filter Direction | Active |
|---|-----------|-------------|----------|-----------|-------------|----------------------|--------|
| 1 | `dim_date` | `date_key` | `fact_gdp` | `date_key` | 1 : * | Single (Dim → Fact) | Yes |
| 2 | `dim_date` | `date_key` | `fact_unemployment` | `date_key` | 1 : * | Single (Dim → Fact) | Yes |
| 3 | `dim_date` | `date_key` | `fact_credit` | `date_key` | 1 : * | Single (Dim → Fact) | Yes |
| 4 | `dim_date` | `date_key` | `fact_interest_rates` | `date_key` | 1 : * | Single (Dim → Fact) | Yes |
| 5 | `dim_date` | `date_key` | `fact_inflation` | `date_key` | 1 : * | Single (Dim → Fact) | Yes |
| 6 | `dim_date` | `date_key` | `fact_public_debt` | `date_key` | 1 : * | Single (Dim → Fact) | Yes |
| 7 | `dim_source` | `source_key` | `fact_gdp` | `source_key` | 1 : * | Single (Dim → Fact) | Yes |
| 8 | `dim_source` | `source_key` | `fact_unemployment` | `source_key` | 1 : * | Single (Dim → Fact) | Yes |
| 9 | `dim_source` | `source_key` | `fact_credit` | `source_key` | 1 : * | Single (Dim → Fact) | Yes |
| 10 | `dim_source` | `source_key` | `fact_interest_rates` | `source_key` | 1 : * | Single (Dim → Fact) | Yes |
| 11 | `dim_source` | `source_key` | `fact_inflation` | `source_key` | 1 : * | Single (Dim → Fact) | Yes |
| 12 | `dim_source` | `source_key` | `fact_public_debt` | `source_key` | 1 : * | Single (Dim → Fact) | Yes |

### 1.4 Dimension Table Details

#### dim_date

| Column | Data Type | Description |
|--------|-----------|-------------|
| `date_key` | Integer (PK) | Surrogate key in YYYYMMDD format |
| `full_date` | Date | Calendar date |
| `year` | Integer | Calendar year (2010-2025) |
| `quarter` | Integer | Quarter number (1-4) |
| `month` | Integer | Month number (1-12) |
| `month_name` | Text | Month name (January-December) |
| `is_quarter_end` | Boolean | TRUE for March, June, September, December |

**Additional Calculated Columns (add in Power BI):**

| Column | Expression | Description |
|--------|-----------|-------------|
| `Year-Quarter` | `= dim_date[year] & "-Q" & dim_date[quarter]` | Display label for quarterly data |
| `Year-Month` | `= dim_date[year] & "-" & FORMAT(dim_date[full_date], "MM")` | Display label for monthly data |
| `Economic Period` | See Section 5.2 | Crisis period classification |

#### dim_source

| Column | Data Type | Description |
|--------|-----------|-------------|
| `source_key` | Integer (PK) | Surrogate key |
| `source_name` | Text | Source institution name |
| `source_url` | Text | Source website URL |
| `description` | Text | Source description |

### 1.5 Fact Table Details

#### fact_gdp (Quarterly)

| Column | Data Type | Unit | Description |
|--------|-----------|------|-------------|
| `date_key` | Integer (FK) | - | Foreign key to dim_date |
| `source_key` | Integer (FK) | - | Foreign key to dim_source |
| `nominal_gdp` | Decimal | EUR millions | Nominal GDP at current prices |
| `real_gdp` | Decimal | EUR millions | Real GDP at constant prices (2015 base) |
| `gdp_growth_yoy` | Decimal | % | Year-on-year GDP growth rate (derived from real_gdp) |
| `gdp_per_capita` | Decimal | EUR | GDP per capita |
| `is_provisional` | Boolean | - | TRUE if the data point is provisional/preliminary |

#### fact_unemployment (Monthly)

| Column | Data Type | Unit | Description |
|--------|-----------|------|-------------|
| `date_key` | Integer (FK) | - | Foreign key to dim_date |
| `source_key` | Integer (FK) | - | Foreign key to dim_source |
| `unemployment_rate` | Decimal | % | General unemployment rate |
| `youth_unemployment_rate` | Decimal | % | Youth unemployment rate (under 25) |
| `labour_force_participation_rate` | Decimal | % | Labour force participation rate |
| `is_provisional` | Boolean | - | TRUE if the data point is provisional/preliminary |

#### fact_credit (Monthly)

| Column | Data Type | Unit | Description |
|--------|-----------|------|-------------|
| `date_key` | Integer (FK) | - | Foreign key to dim_date |
| `source_key` | Integer (FK) | - | Foreign key to dim_source |
| `total_credit` | Decimal | EUR millions | Total credit to the economy |
| `nfc` | Decimal | EUR millions | Credit to non-financial corporations |
| `household` | Decimal | EUR millions | Credit to households |
| `npl_ratio` | Decimal | % | Non-performing loan ratio |
| `is_provisional` | Boolean | - | TRUE if the data point is provisional/preliminary |

#### fact_interest_rates (Monthly)

| Column | Data Type | Unit | Description |
|--------|-----------|------|-------------|
| `date_key` | Integer (FK) | - | Foreign key to dim_date |
| `source_key` | Integer (FK) | - | Foreign key to dim_source |
| `ecb_main_refinancing_rate` | Decimal | % | ECB main refinancing rate |
| `euribor_3m` | Decimal | % | Euribor 3-month rate |
| `euribor_6m` | Decimal | % | Euribor 6-month rate |
| `euribor_12m` | Decimal | % | Euribor 12-month rate |
| `portugal_10y_bond_yield` | Decimal | % | Portuguese 10-year government bond yield |
| `is_provisional` | Boolean | - | TRUE if the data point is provisional/preliminary |

#### fact_inflation (Monthly)

| Column | Data Type | Unit | Description |
|--------|-----------|------|-------------|
| `date_key` | Integer (FK) | - | Foreign key to dim_date |
| `source_key` | Integer (FK) | - | Foreign key to dim_source |
| `hicp` | Decimal | % | Harmonised Index of Consumer Prices (YoY) |
| `cpi_estimated` | Decimal | % | Consumer Price Index (YoY), estimated |
| `core` | Decimal | % | Core inflation (excluding energy and food) |
| `is_provisional` | Boolean | - | TRUE if the data point is provisional/preliminary |

#### fact_public_debt (Quarterly)

| Column | Data Type | Unit | Description |
|--------|-----------|------|-------------|
| `date_key` | Integer (FK) | - | Foreign key to dim_date |
| `source_key` | Integer (FK) | - | Foreign key to dim_source |
| `total_debt` | Decimal | EUR millions | General government gross debt |
| `debt_to_gdp_ratio` | Decimal | % | Debt-to-GDP ratio |
| `external_debt_share_estimated` | Decimal | % | Share of externally held debt, estimated |
| `budget_balance` | Decimal | % of GDP | Government budget balance |
| `budget_deficit_annual` | Decimal | % of GDP | Annual government budget deficit |
| `is_provisional` | Boolean | - | TRUE if the data point is provisional/preliminary |

### 1.6 Calculated Table: Economic Periods

Create the following calculated table in Power BI for the period slicer:

```
Economic Periods =
DATATABLE(
    "Period Name", STRING,
    "Period Order", INTEGER,
    "Start Year", INTEGER,
    "End Year", INTEGER,
    "Colour", STRING,
    {
        { "Pre-crisis",       1, 2010, 2011, "#D5F5E3" },
        { "Troika",           2, 2012, 2014, "#FADBD8" },
        { "Recovery",         3, 2015, 2019, "#D6EAF8" },
        { "COVID",            4, 2020, 2020, "#F9E79F" },
        { "Post-COVID",       5, 2021, 2025, "#E8DAEF" }
    }
)
```

---

## 2. DAX Measures Overview

All DAX measures are documented in full detail in the companion file `dax_measures.md`. Below is a summary categorisation.

### 2.1 Measure Categories

| Category | Count | Description |
|----------|-------|-------------|
| KPI Measures | 13 | Current/latest values for headline indicators |
| YoY Growth Measures | 6 | Year-on-year percentage change for each pillar |
| Moving Average Measures | 6 | 3-month and 12-month rolling averages |
| Derived/Calculated Measures | 5 | Sovereign spread, real interest rate, credit-to-GDP, etc. |
| Period Comparison Measures | 3 | Crisis vs recovery and period average comparisons |
| Formatting Measures | 6 | Traffic lights, trend arrows, conditional formatting |
| **Total** | **39** | |

### 2.2 Measure Table

All measures should be created within a dedicated Measures table (a disconnected table with a single blank row) to keep the model tidy. In the Model view, organise measures into Display Folders matching the categories above.

---

## 3. Dashboard Pages

### 3.0 Global Elements (Present on All Pages)

| Element | Type | Position | Details |
|---------|------|----------|---------|
| Report Title | Text Box | Top-left (0, 0) | "Portugal Data Intelligence" in Segoe UI Semibold 16pt, colour `#2B2D42` |
| Page Navigation | Buttons | Top-right | 6 page-navigation buttons, 90x30 px each |
| Date Range Display | Card | Top-centre | Shows selected date range from slicer |
| Logo Placeholder | Image | Top-left corner | 40x40 px placeholder |
| Last Refresh | Text Box | Bottom-right | "Data refreshed: " & `LASTREFRESHDATE` |

**Canvas Size:** 1280 x 720 px (16:9)

---

### 3.1 Page 1: Executive Overview

**Purpose:** Provide a single-glance summary of Portugal's macroeconomic health across all six pillars.

#### Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [Header: Portugal Data Intelligence - Executive Overview]              │
│  [Date Range Slicer] ─────────────  [Period Slicer] ──────────────     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                              │
│  │ GDP      │  │ Unemploy │  │ Credit   │                              │
│  │ Growth   │  │ Rate     │  │ Total    │                              │
│  │ +2.1%  ▲ │  │ 6.2%   ▼ │  │ €142.3B ►│                              │
│  │ ~~~~~~~~ │  │ ~~~~~~~~ │  │ ~~~~~~~~ │                              │
│  └──────────┘  └──────────┘  └──────────┘                              │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                              │
│  │ ECB Rate │  │ Inflation│  │ Debt/GDP │                              │
│  │ 3.50%  ► │  │ 2.3%   ▼ │  │ 112.4% ▼ │                              │
│  │ ~~~~~~~~ │  │ ~~~~~~~~ │  │ ~~~~~~~~ │                              │
│  └──────────┘  └──────────┘  └──────────┘                              │
│                                                                          │
│  ┌────────────────────────────────┐  ┌──────────────────────────────┐  │
│  │ Economic Health Scorecard      │  │ Pillar Summary Table         │  │
│  │ (Multi-row card / Matrix)      │  │ (Matrix with conditional     │  │
│  │                                │  │  formatting)                  │  │
│  └────────────────────────────────┘  └──────────────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Visual Specifications

| # | Visual Type | Title | Measures Used | Size (W x H) | Position (X, Y) |
|---|------------|-------|---------------|---------------|------------------|
| 1 | Date Slicer | - | `dim_date[full_date]` | 280 x 40 | (20, 50) |
| 2 | Dropdown Slicer | Economic Period | `Economic Periods[Period Name]` | 200 x 40 | (320, 50) |
| 3 | KPI Card | GDP Growth | `[Latest GDP Growth]`, `[GDP Growth Trend Arrow]` | 180 x 130 | (20, 110) |
| 4 | KPI Card | Unemployment | `[Latest Unemployment Rate]`, `[Unemployment Trend Arrow]` | 180 x 130 | (220, 110) |
| 5 | KPI Card | Credit | `[Latest Total Credit]`, `[Credit Trend Arrow]` | 180 x 130 | (420, 110) |
| 6 | KPI Card | ECB Rate | `[Latest ECB Rate]`, `[ECB Rate Trend Arrow]` | 180 x 130 | (20, 260) |
| 7 | KPI Card | Inflation | `[Latest HICP]`, `[Inflation Trend Arrow]` | 180 x 130 | (220, 260) |
| 8 | KPI Card | Debt-to-GDP | `[Latest Debt to GDP]`, `[Debt Trend Arrow]` | 180 x 130 | (420, 260) |
| 9 | Multi-row Card | Economic Health Scorecard | All 6 latest KPIs with traffic lights | 380 x 250 | (20, 410) |
| 10 | Matrix | Pillar Summary | Pillar names on rows; Latest Value, YoY Change, Traffic Light on columns | 400 x 250 | (420, 410) |

#### KPI Card Configuration

Each of the 6 KPI cards follows this template:

- **Title:** Pillar name (Segoe UI Semibold 11pt, colour `#2B2D42`)
- **Value:** Latest measure (Segoe UI Bold 24pt, colour `#2B2D42`)
- **Subtitle:** Trend arrow measure + YoY change (Segoe UI 10pt)
- **Sparkline:** Enabled, showing last 12 periods, colour `#9B2226`
- **Background:** White `#FFFFFF` with 1px border `#E5E5E5`
- **Corner Radius:** 4px

---

### 3.2 Page 2: GDP & Growth

**Purpose:** Deep dive into Portugal's GDP evolution, growth dynamics, and per-capita trends across economic periods.

#### Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [Header: GDP & Growth Analysis]                                         │
│  [Date Range Slicer] ─────────────  [Period Slicer] ──────────────     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  GDP Evolution (Line + Bar Combo Chart)                         │    │
│  │  Bars = Nominal GDP  |  Line = Real GDP Growth Rate             │    │
│  │  X-Axis: Year-Quarter  |  Primary Y: EUR M  |  Secondary Y: %  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  Growth Rate Waterfall   │  │  GDP Per Capita Trend            │    │
│  │  (Waterfall Chart)       │  │  (Line Chart)                    │    │
│  │  Shows QoQ contribution  │  │  X: Year  Y: EUR                 │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  Quarterly Seasonality   │  │  Period Comparison Table         │    │
│  │  (Matrix/Heatmap)        │  │  (Table Visual)                  │    │
│  │  Rows: Q1-Q4             │  │  Columns: Period, Avg Growth,    │    │
│  │  Cols: Years              │  │  Peak, Trough, Cumulative        │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Visual Specifications

| # | Visual Type | Title | Measures / Fields | Size (W x H) |
|---|------------|-------|-------------------|---------------|
| 1 | Combo Chart (Bar + Line) | GDP Evolution (2010-2025) | Bars: `fact_gdp[nominal_gdp]`, Line: `fact_gdp[growth_rate]`, Axis: `dim_date[Year-Quarter]` | 800 x 250 |
| 2 | Waterfall Chart | Quarterly Growth Contribution | Category: `dim_date[Year-Quarter]`, Values: `fact_gdp[growth_rate]` | 380 x 200 |
| 3 | Line Chart | GDP Per Capita Trend | X: `dim_date[year]`, Y: `[Avg GDP Per Capita]` | 380 x 200 |
| 4 | Matrix | Quarterly Seasonality | Rows: `dim_date[quarter]`, Columns: `dim_date[year]`, Values: `fact_gdp[growth_rate]` with conditional background colours | 380 x 200 |
| 5 | Table | Period Comparison | Columns: Period Name, Average Growth, Peak Growth, Trough Growth, Cumulative Growth | 380 x 200 |

#### Combo Chart Configuration

- **Bar colour:** `#9B2226` (Nominal GDP)
- **Line colour:** `#D4A373` (Growth Rate)
- **Primary Y-axis:** "EUR Millions" (left), format `#,##0`
- **Secondary Y-axis:** "Growth Rate %" (right), format `0.0%`
- **X-axis:** Rotated 45 degrees, show every 4th label
- **Data labels:** On line only, format `0.0%`
- **Reference line:** Horizontal at 0% on secondary axis, dashed, colour `#6C757D`
- **Period shading:** Use background bands to indicate economic periods (configurable via bookmarks)

---

### 3.3 Page 3: Labour Market

**Purpose:** Analyse unemployment dynamics, youth employment challenges, and labour force participation across economic cycles.

#### Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [Header: Labour Market Analysis]                                        │
│  [Date Range Slicer] ─────────────  [Period Slicer] ──────────────     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Unemployment Trend (Multi-Line Chart)                          │    │
│  │  Line 1 = General Rate  |  Line 2 = Youth Rate                  │    │
│  │  X-Axis: Year-Month  |  Y-Axis: %                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  Labour Force            │  │  Youth Gap Analysis              │    │
│  │  Participation Rate      │  │  (Area Chart)                    │    │
│  │  (Line Chart)            │  │  Area = Youth Rate - General     │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  Crisis Impact           │  │  Key Statistics Card             │    │
│  │  Comparison              │  │  Peak Unemployment, Lowest,      │    │
│  │  (Clustered Bar Chart)   │  │  Current, Youth Peak, Recovery   │    │
│  │  Periods on Y, Rate on X │  │  Months                          │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Visual Specifications

| # | Visual Type | Title | Measures / Fields | Size (W x H) |
|---|------------|-------|-------------------|---------------|
| 1 | Line Chart (Dual) | Unemployment Trend (2010-2025) | Lines: `fact_unemployment[rate]`, `fact_unemployment[youth_rate]`, Axis: `dim_date[full_date]` | 800 x 250 |
| 2 | Line Chart | Labour Force Participation | X: `dim_date[full_date]`, Y: `fact_unemployment[lfp_rate]` | 380 x 200 |
| 3 | Area Chart | Youth Unemployment Gap | X: `dim_date[full_date]`, Y: `[Youth Unemployment Gap]` (calculated measure: youth_rate - rate) | 380 x 200 |
| 4 | Clustered Bar Chart | Crisis Impact Comparison | Y: `Economic Periods[Period Name]`, X: `[Avg Unemployment by Period]` | 380 x 200 |
| 5 | Multi-row Card | Key Labour Statistics | `[Peak Unemployment]`, `[Lowest Unemployment]`, `[Latest Unemployment Rate]`, `[Peak Youth Unemployment]`, `[Recovery Duration Months]` | 380 x 200 |

#### Line Chart Configuration

- **General Rate line:** Solid, 2px, colour `#9B2226`
- **Youth Rate line:** Solid, 2px, colour `#9B2226`
- **Reference line:** EU average (horizontal, dashed, `#6C757D`)
- **Legend:** Top-right, Segoe UI 9pt
- **Y-axis:** Range 0-40%, format `0.0%`
- **Tooltips:** Show date, general rate, youth rate, gap, YoY change

---

### 3.4 Page 4: Financial Conditions

**Purpose:** Monitor the interest rate environment, sovereign risk, and credit conditions affecting Portugal's economy and banking sector.

#### Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [Header: Financial Conditions]                                          │
│  [Date Range Slicer] ─────────────  [Period Slicer] ──────────────     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Interest Rate Environment (Multi-Line Chart)                    │    │
│  │  Lines: ECB Rate, Euribor 3M, Euribor 12M, PT 10Y Bond         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  Sovereign Spread        │  │  Credit Evolution                │    │
│  │  (Area Chart)            │  │  (Stacked Area Chart)            │    │
│  │  PT 10Y - DE 10Y         │  │  Areas: NFC, Household           │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  NPL Ratio Gauge         │  │  Rate vs Credit Scatter          │    │
│  │  (Gauge Visual)           │  │  X: Euribor 12M                 │    │
│  │  Min: 0, Max: 20%        │  │  Y: Total Credit Growth          │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Visual Specifications

| # | Visual Type | Title | Measures / Fields | Size (W x H) |
|---|------------|-------|-------------------|---------------|
| 1 | Line Chart (Multi) | Interest Rate Environment | Lines: `ecb_rate`, `euribor_3m`, `euribor_12m`, `bond_10y`, Axis: `dim_date[full_date]` | 800 x 250 |
| 2 | Area Chart | Sovereign Spread (PT vs DE) | X: `dim_date[full_date]`, Y: `[Sovereign Spread]` | 380 x 200 |
| 3 | Stacked Area Chart | Credit to the Economy | X: `dim_date[full_date]`, Y: `fact_credit[nfc]`, `fact_credit[household]` | 380 x 200 |
| 4 | Gauge | NPL Ratio | Value: `[Latest NPL Ratio]`, Min: 0, Max: 20, Target: 3 | 180 x 180 |
| 5 | Scatter Chart | Rate vs Credit Relationship | X: `fact_interest_rates[euribor_12m]`, Y: `[Credit YoY Growth]`, Size: constant, Colour: `dim_date[year]` | 380 x 200 |

#### Multi-Line Chart Configuration

- **ECB Rate:** Solid 2.5px, `#2B2D42` (darkest, policy rate)
- **Euribor 3M:** Dashed 1.5px, `#9B2226`
- **Euribor 12M:** Solid 1.5px, `#9B2226`
- **PT 10Y Bond:** Solid 2px, `#9B2226`
- **Y-axis:** Range auto, format `0.00%`
- **Tooltips:** Date, all four rates, sovereign spread

#### Gauge Configuration

- **Colour bands:** Green (0-3%), Yellow (3-5%), Orange (5-10%), Red (10-20%)
- **Target needle:** At 3% (ECB supervisory benchmark)
- **Value format:** `0.0%`

---

### 3.5 Page 5: Prices & Fiscal

**Purpose:** Track inflation dynamics relative to ECB targets and examine Portugal's fiscal consolidation path including debt reduction and budget balance.

#### Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [Header: Prices & Fiscal Policy]                                        │
│  [Date Range Slicer] ─────────────  [Period Slicer] ──────────────     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Inflation Trend (Multi-Line Chart)                              │    │
│  │  Lines: HICP, Core Inflation  |  Reference: ECB 2% Target       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  Debt-to-GDP Evolution   │  │  Budget Balance Waterfall        │    │
│  │  (Area Chart with Zones) │  │  (Waterfall Chart)               │    │
│  │  Zones: <60%, 60-90%,    │  │  Annual budget balance by year   │    │
│  │  90-100%, >100%          │  │                                   │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  Real Interest Rate      │  │  Fiscal Consolidation Timeline   │    │
│  │  (Line Chart)            │  │  (Table / KPI cards)             │    │
│  │  Real = ECB Rate - HICP  │  │  Key milestones: Troika exit,    │    │
│  └──────────────────────────┘  │  EDP exit, etc.                  │    │
│                                 └──────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Visual Specifications

| # | Visual Type | Title | Measures / Fields | Size (W x H) |
|---|------------|-------|-------------------|---------------|
| 1 | Line Chart (Multi) | Inflation Trend (HICP & Core) | Lines: `fact_inflation[hicp]`, `fact_inflation[core]`, Reference line at 2%, Axis: `dim_date[full_date]` | 800 x 250 |
| 2 | Area Chart | Debt-to-GDP Ratio | X: `dim_date[Year-Quarter]`, Y: `fact_public_debt[debt_to_gdp]` | 380 x 200 |
| 3 | Waterfall Chart | Budget Balance by Year | Category: `dim_date[year]`, Values: `[Avg Budget Balance]` | 380 x 200 |
| 4 | Line Chart | Real Interest Rate | X: `dim_date[full_date]`, Y: `[Real Interest Rate]` (ECB Rate - HICP) | 380 x 200 |
| 5 | Table | Fiscal Consolidation Milestones | Columns: Year, Event, Debt-to-GDP, Budget Balance, Notes | 380 x 200 |

#### Inflation Chart Configuration

- **HICP line:** Solid 2px, `#9B2226`
- **Core Inflation line:** Dashed 1.5px, `#D4A373`
- **ECB Target reference:** Horizontal at 2.0%, dotted, `#386641`, label "ECB Target"
- **Y-axis:** Range -2% to 12%, format `0.0%`
- **Shading:** Highlight area above ECB target in light red `#F2D5D6`

#### Debt-to-GDP Zone Configuration

Use background colour bands:
- Green zone: 0-60% (`#E2F0D9`)
- Yellow zone: 60-90% (`#FFF2CC`)
- Orange zone: 90-100% (`#FCE4D6`)
- Red zone: 100%+ (`#FBE5D6`)

---

### 3.6 Page 6: Cross-Pillar Analysis

**Purpose:** Reveal inter-relationships between macroeconomic pillars and provide a unified view of Portugal's economic trajectory through structural analysis.

#### Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [Header: Cross-Pillar Analysis]                                         │
│  [Date Range Slicer] ─────────────  [Period Slicer] ──────────────     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  Correlation Heatmap     │  │  Phillips Curve                  │    │
│  │  (Matrix with conditional│  │  (Scatter Chart)                 │    │
│  │  formatting)              │  │  X: Unemployment Rate            │    │
│  │  GDP Growth, Unemployment│  │  Y: Inflation Rate (HICP)        │    │
│  │  Credit, Rates, Inflation│  │  Colour: Year                    │    │
│  │  Debt                    │  │  Size: GDP Growth                 │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Economic Dashboard - All Pillar Sparklines                      │    │
│  │  (Multi-row Card or Small Multiples)                             │    │
│  │  6 rows: GDP Growth, Unemployment, Credit Growth, Euribor 12M,  │    │
│  │  HICP, Debt-to-GDP  |  Each with sparkline and current value     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  Crisis Timeline         │  │  Key Insights                    │    │
│  │  (Normalised Line Chart) │  │  (Text Box - AI-Generated)       │    │
│  │  All pillars normalised  │  │  Top 5 cross-pillar findings     │    │
│  │  to 100 at period start  │  │  from AI analysis module         │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Visual Specifications

| # | Visual Type | Title | Measures / Fields | Size (W x H) |
|---|------------|-------|-------------------|---------------|
| 1 | Matrix | Correlation Heatmap | Rows & Columns: Pillar names, Values: `[Correlation Coefficient]` with conditional background (red negative, green positive) | 380 x 280 |
| 2 | Scatter Chart | Phillips Curve (Unemployment vs Inflation) | X: `[Avg Unemployment Rate]`, Y: `[Avg HICP]`, Detail: `dim_date[year]`, Size: `[Avg GDP Growth]`, Colour: `dim_date[year]` | 380 x 280 |
| 3 | Multi-row Card / Table | Economic Dashboard | 6 rows, each showing pillar name, sparkline, current value, YoY change, traffic light | 800 x 150 |
| 4 | Line Chart (Multi) | Crisis Timeline (Normalised to 100) | Lines: All 6 pillar indices normalised, X: `dim_date[full_date]` | 380 x 200 |
| 5 | Text Box | Key Insights | AI-generated text summarising top cross-pillar findings, updated on each refresh | 380 x 200 |

#### Correlation Heatmap Formatting

- **Background colour scale:** Diverging from `#9B2226` (strong negative, -1.0) through `#FFFFFF` (zero) to `#386641` (strong positive, +1.0)
- **Font:** Values displayed as `0.00`, Segoe UI 10pt
- **Diagonal:** Highlighted in `#E5E5E5` (self-correlation = 1.00)

#### Phillips Curve Configuration

- **Bubble colour:** Gradient by year (early years `#9B2226`, recent years `#9B2226`)
- **Data labels:** Year value on each bubble
- **Trend line:** Polynomial (order 2), dashed, `#6C757D`
- **Axes:** X = "Unemployment Rate (%)", Y = "Inflation Rate (HICP %)"

---

### 3.7 Page 7: Strategic Outlook

**Purpose:** Translate the data story into actionable strategic insights — what happened, why, and what comes next. This page bridges analytics and decision-making.

#### Layout

```
+------------------------------------------------------------------------+
|  [Header: Strategic Outlook - Portugal 2010-2025]                      |
+------------------------------------------------------------------------+
|                                                                          |
|  +----------------------------+  +-----------------------------------+  |
|  | The 3-Act Transformation   |  | PT vs EU Convergence              |  |
|  | (Timeline Visual)          |  | (Benchmark Radar Chart)           |  |
|  |                            |  |                                   |  |
|  | Crisis     Recovery  Now   |  | PT vs EU_AVG vs DE vs ES          |  |
|  | 2010-14    2015-19  2020+  |  | 5 indicators: GDP growth,        |  |
|  |                            |  | unemployment, inflation,          |  |
|  +----------------------------+  | debt/GDP, bond yield              |  |
|                                  +-----------------------------------+  |
|  +----------------------------+  +-----------------------------------+  |
|  | Scorecard: Then vs Now     |  | Risk & Outlook Matrix             |  |
|  | (Table / Matrix)           |  | (Matrix with traffic lights)      |  |
|  |                            |  |                                   |  |
|  | Metric     2013    2025    |  | Pillar   Risk    Trend   Outlook  |  |
|  | Unemp      17.2%   6.0%   |  | GDP      LOW     +5.8%   Stable   |  |
|  | Debt/GDP   133.6%  96.7%  |  | Unemp    LOW     -0.5pp  Stable   |  |
|  | Deficit    -5.3%   +2.5%  |  | Credit   MOD     +3.2%   Watch    |  |
|  | NPL        17.5%   2.3%   |  | Rates    MOD     -1.5pp  Easing   |  |
|  | Bond 10Y   6.3%    3.1%   |  | Inflat   LOW     -0.5pp  Target   |  |
|  +----------------------------+  | Debt     LOW     -8.6pp  Improv.  |  |
|                                  +-----------------------------------+  |
|  +------------------------------------------------------------------+  |
|  | Strategic Narrative (Text Box / Smart Narrative)                   |  |
|  |                                                                    |  |
|  | "Portugal completed a structural transformation: from bailout      |  |
|  |  (2012) to budget surplus (2019-2025). Debt/GDP fell below 100%   |  |
|  |  for the first time since 2011. Key risks: credit/GDP ratio       |  |
|  |  (397%), youth unemployment (19.4%), and productivity gap."        |  |
|  +------------------------------------------------------------------+  |
|                                                                          |
+------------------------------------------------------------------------+
```

#### Visual Specifications

| # | Visual Type | Title | Data | Size (W x H) |
|---|------------|-------|------|---------------|
| 1 | Grouped Bar Chart | The 3-Act Transformation | Key metrics by economic period (Pre-Crisis, Troika, Recovery, COVID, Post-COVID). Metrics: Avg unemployment, Avg GDP growth, Avg deficit | 380 x 250 |
| 2 | Radar Chart (or image) | PT vs EU Convergence | `fact_eu_benchmark` filtered to latest year. Axes: GDP growth, unemployment, inflation, debt/GDP, bond yield. Series: PT, EU_AVG, DE, ES | 380 x 250 |
| 3 | Matrix | Scorecard: Then vs Now | Row per metric; columns for Crisis Peak (2013), Pre-COVID (2019), Latest (2025), Change. Conditional formatting: green for improvement, red for deterioration | 380 x 200 |
| 4 | Matrix | Risk & Outlook | Row per pillar; columns: Current Value, YoY Change, Risk Level (traffic light), Trend Arrow, Outlook text | 380 x 200 |
| 5 | Smart Narrative / Text | Strategic Narrative | Auto-generated or static text summarising the 3-act story, key achievements, and forward risks | 780 x 100 |

#### Scorecard: Then vs Now — Data Points

| Metric | Crisis Peak (2013) | Pre-COVID (2019) | Latest (2025) |
|--------|-------------------|-------------------|---------------|
| Unemployment | 17.2% | 6.6% | 6.0% |
| Youth Unemployment | 38.7% | 18.4% | 19.4% |
| Debt/GDP | 133.6% | 119.1% | 96.7% |
| Budget Balance | -5.3% | +0.2% | +2.5% |
| NPL Ratio | 17.5% | 8.3% | 2.3% |
| Bond 10Y Yield | 6.3% | 0.8% | 3.1% |
| GDP per Capita | 16,300 EUR | 20,710 EUR | 28,390 EUR |

---

## 4. Formatting Standards

> **Source of truth:** All colours are defined in `src/reporting/shared_styles.py`.
> The values below are aligned with the project design system for Power BI compatibility.

### 4.1 Colour Palette

#### Primary Colours

| Name | Hex Code | Design System Constant | Usage |
|------|----------|----------------------|-------|
| Primary Red (Terracotta) | `#9B2226` | `CHART_PRIMARY` | Titles, headers, primary data series |
| Secondary Green (Forest) | `#386641` | `CHART_SECONDARY` | Secondary data series, area fills |
| Accent Gold (Stone) | `#D4A373` | `CHART_ACCENT` | Highlights, key insights, emphasis |
| Positive Green | `#386641` | `CHART_POSITIVE` | Positive values, recovery indicators |
| Light Red | `#C4494D` | `CHART_PURPLE` | Tertiary data, additional series |
| Neutral Grey | `#6C757D` | `CHART_NEUTRAL` | Reference lines, neutral elements |

#### Neutral Colours

| Name | Hex Code | Design System Constant | Usage |
|------|----------|----------------------|-------|
| White | `#FFFFFF` | — | Card backgrounds, chart plot area |
| Background | `#FAF9F6` | `CHART_BACKGROUND` | Page background |
| Grid / Border | `#E5E5E5` | `CHART_GRID` | Borders, gridlines |
| Light Text | `#6C757D` | `CHART_LIGHT_TEXT` | Secondary text, captions |
| Dark Text | `#2B2D42` | `CHART_DARK_TEXT` | Body text |

#### Traffic Light Colours

| Status | Hex Code | Design System Constant | Condition |
|--------|----------|----------------------|-----------|
| Green | `#386641` | `CHART_POSITIVE` | Positive / improving / on target |
| Amber | `#D4A373` | `CHART_ACCENT` | Neutral / stable / approaching threshold |
| Red | `#9B2226` | `CHART_NEGATIVE` | Negative / deteriorating / breached threshold |

#### Economic Period Colours

| Period | Hex Code | Design System Key | Years |
|--------|----------|------------------|-------|
| Pre-crisis | `#D5F5E3` | `PERIOD_COLORS["Pre-crisis"]` | 2010–2011 |
| Troika | `#FADBD8` | `PERIOD_COLORS["Troika"]` | 2012–2014 |
| Recovery | `#D6EAF8` | `PERIOD_COLORS["Recovery"]` | 2015–2019 |
| COVID | `#F9E79F` | `PERIOD_COLORS["COVID"]` | 2020 |
| Post-COVID | `#E8DAEF` | `PERIOD_COLORS["Post-COVID"]` | 2021–2025 |

### 4.2 Typography

| Element | Font | Size | Weight | Colour |
|---------|------|------|--------|--------|
| Report Title | Segoe UI | 16pt | Semibold | `#9B2226` |
| Page Title | Segoe UI | 14pt | Semibold | `#9B2226` |
| Visual Title | Segoe UI | 11pt | Semibold | `#9B2226` |
| Axis Labels | Segoe UI | 9pt | Regular | `#6C757D` |
| Data Labels | Segoe UI | 9pt | Regular | `#2B2D42` |
| Card Value | Segoe UI | 24pt | Bold | `#9B2226` |
| Card Subtitle | Segoe UI | 10pt | Regular | `#6C757D` |
| Tooltip Title | Segoe UI | 10pt | Semibold | `#2B2D42` |
| Tooltip Value | Segoe UI | 9pt | Regular | `#2B2D42` |
| Slicer Label | Segoe UI | 10pt | Regular | `#2B2D42` |

### 4.3 Card Formatting Rules

| Property | Value |
|----------|-------|
| Background | `#FFFFFF` |
| Border | 1px solid `#E5E5E5` |
| Corner Radius | 4px |
| Shadow | Subtle (2px offset, 4px blur, `#00000020`) |
| Padding | 12px |
| Value Alignment | Centre |
| Sparkline Height | 30px |
| Sparkline Colour | `#9B2226` (line), `#4472C420` (fill) |

### 4.4 Chart Formatting Standards

| Property | Value |
|----------|-------|
| Plot Area Background | `#FFFFFF` |
| Gridlines | Horizontal only, `#E5E5E5`, 0.5px |
| Axis Colour | `#6C757D` |
| Legend Position | Top-right (or bottom for wide charts) |
| Legend Font | Segoe UI 9pt, `#2B2D42` |
| Data Label Font | Segoe UI 9pt, `#2B2D42` |
| Line Width (primary) | 2.0px |
| Line Width (secondary) | 1.5px |
| Bar Gap | 50% |
| Category Gap | 30% |
| Tooltip Style | Default with custom background `#F1F1F1` |

### 4.5 Number Format Standards

| Measure Type | Format String | Example |
|-------------|---------------|---------|
| Percentage (rate) | `0.0%` | 6.2% |
| Percentage (growth) | `+0.0%;-0.0%;0.0%` | +2.1% |
| Currency (millions) | `#,##0 "M"` | 57,324 M |
| Currency (billions) | `#,##0.0 "B"` | 142.3 B |
| Currency (per capita) | `€#,##0` | €22,450 |
| Ratio | `0.00` | 0.85 |
| Index | `0.0` | 102.3 |
| Basis Points | `0 "bps"` | 150 bps |

---

## 5. Slicer Configuration

### 5.1 Date Range Slicer

| Property | Value |
|----------|-------|
| Field | `dim_date[full_date]` |
| Type | Between (date range slider) |
| Default | Full range: 01/01/2010 - 31/12/2025 |
| Format | DD/MM/YYYY |
| Position | Top of every page |
| Size | 280 x 40 px |
| Style | Slider with text inputs |

### 5.2 Economic Period Slicer

| Property | Value |
|----------|-------|
| Field | `dim_date[Economic Period]` |
| Type | Dropdown / List (multi-select) |
| Default | All selected |
| Position | Top of every page, next to date slicer |
| Size | 200 x 40 px |

**Calculated Column Definition** (add to `dim_date`):

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

**Sort Order Column** (add to `dim_date`):

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

Sort `Economic Period` column by `Period Sort Order` column.

### 5.3 Indicator Selection Slicer (Page 6 only)

| Property | Value |
|----------|-------|
| Field | Custom table `Indicators[Indicator Name]` |
| Type | Checkbox list |
| Default | All selected |
| Position | Left sidebar on Page 6 |
| Size | 180 x 300 px |

**Calculated Table:**

```dax
Indicators =
DATATABLE(
    "Indicator Name", STRING,
    "Indicator Key", STRING,
    "Pillar", STRING,
    "Unit", STRING,
    {
        { "GDP Growth", "gdp_growth", "GDP", "%" },
        { "GDP Per Capita", "gdp_per_capita", "GDP", "EUR" },
        { "Unemployment Rate", "unemployment_rate", "Labour", "%" },
        { "Youth Unemployment", "youth_unemployment", "Labour", "%" },
        { "Total Credit", "total_credit", "Credit", "EUR M" },
        { "NPL Ratio", "npl_ratio", "Credit", "%" },
        { "ECB Rate", "ecb_rate", "Rates", "%" },
        { "Euribor 12M", "euribor_12m", "Rates", "%" },
        { "PT 10Y Bond", "bond_10y", "Rates", "%" },
        { "HICP", "hicp", "Prices", "%" },
        { "Core Inflation", "core_inflation", "Prices", "%" },
        { "Debt-to-GDP", "debt_to_gdp", "Fiscal", "%" },
        { "Budget Balance", "budget_balance", "Fiscal", "% GDP" }
    }
)
```

---

## 6. Implementation Notes

### 6.1 Data Refresh

| Setting | Value |
|---------|-------|
| Connection Type | Import (full dataset) |
| Refresh Frequency | Weekly |
| Incremental Refresh | Not required (dataset < 50MB) |
| Gateway | Personal gateway or on-premises data gateway for SQLite |

### 6.2 Performance Optimisation

- Use **Import mode** for all tables (dataset is small enough to fit entirely in memory)
- Create a **Date table** using Power BI's auto date/time feature OR the existing `dim_date` (disable auto date/time in Options if using `dim_date`)
- Mark `dim_date` as the **Date table** with `full_date` as the date column
- Hide all foreign key columns from the Report view
- Hide the staging/raw columns not needed for reporting

### 6.3 Bookmarks & Navigation

Create the following bookmarks for economic period highlighting:

| Bookmark Name | Description |
|---------------|-------------|
| `BM_AllPeriods` | Default view, no period filter |
| `BM_PreCrisis` | Filter to 2010 only |
| `BM_SovereignCrisis` | Filter to 2011 |
| `BM_Troika` | Filter to 2012-2014 |
| `BM_Recovery` | Filter to 2015-2019 |
| `BM_COVID` | Filter to 2020-2021 |
| `BM_PostCOVID` | Filter to 2022-2025 |

### 6.4 Tooltip Pages

Create two custom tooltip pages:

**Tooltip: Indicator Detail**
- Size: 320 x 240 px
- Content: Indicator name, current value, YoY change, 12-month sparkline, economic period
- Trigger: Hover on any KPI card or chart data point

**Tooltip: Period Context**
- Size: 320 x 180 px
- Content: Period name, date range, key events description, average values for all pillars
- Trigger: Hover on period slicer items or period-coloured chart elements

### 6.5 Accessibility

- All visuals must have **Alt Text** descriptions
- Colour palette tested for colour-blindness compatibility (all critical information also conveyed via shape/pattern/label)
- Tab order set logically (left-to-right, top-to-bottom) on each page
- High-contrast mode support via conditional formatting themes

### 6.6 Row-Level Security

Not required for this project (all data is public macroeconomic data). If sharing via Power BI Service, publish to a dedicated workspace with viewer-only access for stakeholders.

---

## Appendix A: File Dependencies

| File | Description |
|------|-------------|
| `reports/powerbi/dashboard_specification.md` | This document |
| `reports/powerbi/dax_measures.md` | Complete DAX measure definitions |
| `data/database/portugal_data_intelligence.db` | Source database |
| `config/settings.py` | Project configuration and pillar definitions |
| `sql/ddl/` | Database schema definitions |

## Appendix B: Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 17 March 2026 | Portugal Data Intelligence | Initial specification |
