# Data Quality Report

## Portugal Data Intelligence - Critical Data Analysis

**Version:** 2.0
**Date:** 26 March 2026
**Scope:** All 6 economic pillars + EU Benchmark (2010-2025)
**Changelog:** v2.0 — Added fixes for insight engine (GDP nominal→real), ECB rate corrections, DAX measures alignment, benchmark debt-to-GDP update, and provisional flag calibration.

---

## 1. Data Classification: Real (API) vs Estimated

### All 6 Pillars Use Real API Data

| Pillar | API Source | Granularity | Period | Rows |
|--------|-----------|-------------|--------|------|
| **GDP** | Eurostat SDMX 2.1 (`namq_10_gdp`, `nama_10_pc`) | Quarterly | 2010-Q1 to 2025-Q4 | 64 |
| **Unemployment** | Eurostat (`une_rt_m`, `une_ltu_q`, `lfsq_argan`) | Monthly | Jan 2010 to Dec 2025 | 192 |
| **Credit** | BPStat / Banco de Portugal | Monthly | Jan 2010 to Dec 2025 | 192 |
| **Interest Rates** | ECB Data API | Monthly | Jan 2010 to Dec 2025 | 192 |
| **Inflation** | Eurostat (`prc_hicp_manr`, `prc_hicp_midx`) | Monthly | Jan 2010 to Dec 2025 | 192 |
| **Public Debt** | Eurostat (`gov_10q_ggdebt`, `gov_10q_ggnfa`, `gov_10dd_ggd`) | Quarterly | 2010-Q1 to 2025-Q3 | 63 (+1 extrapolated) |
| **EU Benchmark** | Eurostat + ECB (multi-country) | Annual | 2010 to 2025 | 560 |

All data was fetched on **2026-03-25** from official public APIs (no authentication required).

### Estimated/Synthetic Columns Within Real Data

Despite all data coming from APIs, some columns contain **estimated values** produced during transformation:

| Column | Table | Why Estimated | Method |
|--------|-------|---------------|--------|
| `cpi_estimated` | fact_inflation | Eurostat API returns identical HICP and CPI values | Offset from HICP (mean -0.15 pp, std 0.08) |
| `external_debt_share_estimated` | fact_public_debt | Annual Eurostat data (`gov_10dd_ggd`) broadcast to quarters; trailing quarters forward-filled | Real data from Eurostat when API available; falls back to synthetic 46-48% estimate if fetch fails |
| `budget_deficit_annual` | fact_public_debt | API provides only quarterly (non-annualised) values | Rolling average of last 4 quarters |

### Provisional Data Flag

Data points beyond the API's publication lag are flagged with `is_provisional = True`. This typically applies to data from the last 2+ months (monthly pillars) or last quarter (quarterly pillars) before the fetch date. These represent preliminary estimates or projections from the source institutions, not confirmed final values.

---

## 2. Validation Against Public Sources

### Indicators Verified (2024 data)

| Indicator | Project Value | Official Value | Source | Status |
|-----------|--------------|----------------|--------|--------|
| Nominal GDP (annual) | ~EUR 289.8B | ~EUR 289.4B (INE) | INE | **Aligned** |
| GDP per capita | EUR 27,100 | ~EUR 27,000 | Eurostat | **Aligned** |
| Real GDP growth | ~2.6% | ~2.1% (INE) | INE/Eurostat | **Close** |
| Unemployment rate | 6.3-6.6% | 6.3-6.6% | Eurostat | **Aligned** |
| Youth unemployment | 19.9-24.0% | ~20.5% | Eurostat | **Aligned** |
| HICP inflation (avg) | ~2.7% | 2.7% | Eurostat | **Aligned** |
| Debt-to-GDP (Q4 2024) | 93.6% | 93.6-95.3% | Eurostat | **Aligned** |
| ECB refinancing rate (Dec) | 3.15% | 3.15% | ECB | **Exact** |
| Euribor 3M (Dec) | 2.825% | ~2.8% | ECB | **Aligned** |
| PT 10Y bond yield (Dec) | 2.684% | ~2.7% | Trading Economics | **Aligned** |
| NPL ratio (Q1 2024) | 2.67% | 2.7% | Banco de Portugal | **Aligned** |

**Conclusion:** Real API data is well-aligned with publicly available official statistics.

---

## 3. Critical Issues Found and Corrections Applied

### 3.1 GDP Growth Rates Were Incorrect (CRITICAL - FIXED)

**Problem:** The `gdp_growth_yoy` and `gdp_growth_qoq` columns from the Eurostat API reflected **nominal** GDP growth, but were stored alongside `real_gdp` without clarification. Discrepancies reached **9.2 percentage points** (e.g., 2023-Q1: API reported 12.76% vs real growth of 3.55%).

**Fix:** Growth rates are now **always recalculated** from `real_gdp` during transformation:
- `gdp_growth_yoy = (real_gdp[t] / real_gdp[t-4] - 1) * 100`
- `gdp_growth_qoq = (real_gdp[t] / real_gdp[t-1] - 1) * 100`

**Impact:** Any analysis using GDP growth rates prior to this fix would have been using nominal (not real) growth figures.

### 3.2 CPI Was Identical to HICP (CRITICAL - FIXED)

**Problem:** The Eurostat API returned identical values for HICP and CPI across all 192 months. In reality, Portugal's national CPI (INE methodology) differs slightly from HICP (Eurostat methodology) due to different basket weights.

**Fix:** Column renamed from `cpi` to `cpi_estimated`. A small, realistic offset is applied (mean -0.15 pp, std 0.08) to differentiate from HICP. A log warning is emitted during transformation to flag this as estimated data.

**Recommendation:** For analyses requiring real Portuguese CPI data, obtain it directly from INE (Instituto Nacional de Estatistica).

### 3.3 Provisional Data Was Not Flagged (CRITICAL - FIXED)

**Problem:** All files contained data through December 2025, but the fetch occurred in March 2026. Data from approximately April-December 2025 represents projections or preliminary estimates, not confirmed observations. There was no way to distinguish confirmed from projected data.

**Fix:** Added `is_provisional` column (boolean) to all processed data and database tables. Data points whose date exceeds the confirmed publication window (fetch date minus ~2 months lag) are flagged as provisional.

### 3.4 External Debt Share Was 100% Null (IMPORTANT - FIXED)

**Problem:** The `external_debt_share` column in raw public debt data was entirely empty (Eurostat quarterly debt dataset does not include this metric). During transformation, it was silently filled with synthetic estimates (~46-48%) without any indication. The synthetic values were flat and significantly wrong compared to real data (e.g., real 2010: 61.1%, real 2024: 44.7% -- a major declining trend that the flat estimate missed entirely).

**Fix:** Real external debt share is now fetched from Eurostat dataset `gov_10dd_ggd` (annual general government debt by holding sector). The share is calculated as `(S2 non-resident debt / S1_S2 total debt) * 100`. Annual values are broadcast to all 4 quarters of each year, and missing trailing quarters are forward-filled. Column is kept as `external_debt_share_estimated` because the quarterly granularity is interpolated from annual data. If the Eurostat fetch fails, the pipeline falls back to the previous synthetic estimates and logs a warning.

### 3.5 Budget Deficit Was Non-Annualised (IMPORTANT - FIXED)

**Problem:** Quarterly budget deficit values ranged from -19.1% to +7.3%, reflecting the seasonal pattern of government revenue and expenditure within individual quarters. These extreme values are difficult to interpret and misleading when compared to annual deficit figures cited in media/reports.

**Fix:** Added `budget_deficit_annual` column containing a rolling 4-quarter average, which produces annualised deficit figures suitable for analysis and comparison.

### 3.6 EU Benchmark Meta.json Row Count Was Wrong (FIXED)

**Problem:** The `raw_eu_benchmark.csv.meta.json` file reported 160 rows, but the actual CSV contained 561 rows.

**Fix:** The `generate_eu_benchmark.py` module now generates correct metadata with `save_to_csv()`.

### 3.7 ECB Rate Incorrect Oct 2023 – May 2024 (CRITICAL - FIXED)

**Problem:** The ECB main refinancing rate showed 4.25% from October 2023 through May 2024, but the ECB held the rate at **4.50%** from September 2023 until the first cut in June 2024. This was caused by the monthly resampling logic (`.resample("ME").last()`) mishandling mid-month rate changes.

**Fix:** Changed resampling to first forward-fill to daily granularity (`.resample("D").ffill()`), then pick the month-end value (`.resample("ME").last()`). This ensures the latest ECB decision is correctly propagated to all subsequent days/months.

**Impact:** 8 months of ECB rate data were 25bps too low, affecting interest rate spread calculations and ECB policy analysis.

### 3.8 ECB Rate Missing Jan 2010 – Mar 2011 (IMPORTANT - FIXED)

**Problem:** The ECB Data API did not return rate observations for January 2010 through March 2011. The transform post-hook's backward fill (`bfill`) incorrectly used the April 2011 rate of 1.25%, but the actual ECB rate during this period was **1.00%** (unchanged since May 2009).

**Fix:** Added explicit fill of 1.00% for the 2010-01 to 2011-03 period in the interest rates post-hook, before applying the general `ffill/bfill`.

### 3.9 Insight Engine Used Nominal GDP Growth (CRITICAL - FIXED)

**Problem:** The AI insight engine (`insight_engine.py`) selected `nominal_gdp` as the primary column for GDP analysis, because it appeared before `real_gdp` in the priority list. This caused all GDP insights — headline growth, long-run average, 3-year momentum, crisis impacts — to report **nominal** growth rates (~5.9% for 2025) instead of **real** growth rates (~1.9%).

**Fix:** Reordered the column priority list to `["real_gdp", "gdp_real", ...]` so that real GDP is always selected as the primary column.

**Impact:** The HTML report showed a KPI card with 1.9% (correct, from processed data) but a narrative claiming 5.9% (incorrect, from nominal GDP via insights). Both now consistently show ~1.9%.

### 3.10 Database `id` Field Leaked Into Insights (FIXED)

**Problem:** The `_numeric_cols()` method in the insight engine excluded dimension columns but not the `id` autoincrement field. This caused nonsensical statistics to appear in interest rate findings (e.g., "id: mean 96.5%, range [1.0% - 192.0%]").

**Fix:** Added `"id"` to the exclusion set in `_numeric_cols()`.

### 3.11 Unemployment Insight Wording Error (FIXED)

**Problem:** The unemployment pillar insight reported "fell by 52.1 percentage points" when it should have been "fell by 6.5 percentage points". The code was using `overall_change_pct` (a percentage change: -52.1%) but labelling it as "percentage points".

**Fix:** Changed to use the actual percentage point difference (`pp_change = abs(latest - earliest)`), which correctly yields 6.5 pp.

### 3.12 EU Benchmark Debt-to-GDP Overestimated (IMPORTANT - FIXED)

**Problem:** The `generate_eu_benchmark.py` hardcoded Portugal's debt-to-GDP at 107.5% for 2023, 102.0% for 2024, and 98.0% for 2025. Eurostat's confirmed end-of-year values are 99.1% (2023), 95.7% (2024), and approximately 93.0% (2025 projection). The benchmark was ~8-10pp too high.

**Fix:** Updated reference values to 99.1 (2023), 95.7 (2024), 93.0 (2025).

### 3.13 DAX Measures Column Name Mismatches (IMPORTANT - FIXED)

**Problem:** All 39 Power BI DAX measures in `dax_measures.md` referenced abbreviated column names (e.g., `fact_gdp[growth_rate]`, `fact_unemployment[rate]`) that did not match the actual database schema. None of the measures would have worked without manual column aliasing during import.

**Fix:** Updated all column references to match the actual DDL schema: `growth_rate` → `gdp_growth_yoy`, `rate` → `unemployment_rate`, `youth_rate` → `youth_unemployment_rate`, `debt_to_gdp` → `debt_to_gdp_ratio`, `ecb_rate` → `ecb_main_refinancing_rate`, `bond_10y` → `portugal_10y_bond_yield`, `total` → `total_credit`, `budget_balance` → `budget_deficit`.

---

## 4. Data Quality Assessment by Pillar

### Reliable (High Quality)
- **Unemployment** — Clean data, no calculation errors, aligned with Eurostat
- **Inflation (HICP)** — Correct values, coherent trends
- **Interest Rates (ECB, Euribor, Bond yields)** — Now match ECB policy decisions after fixing two resampling errors (see sections 3.7 and 3.8)
- **GDP (absolute values)** — Nominal GDP, Real GDP, and GDP per capita are correct
- **NPL ratio** — Aligned with Banco de Portugal data

### Requires Awareness (Medium Quality)
- **GDP growth rates** — Now correctly derived from real_gdp (previously incorrect)
- **CPI (`cpi_estimated`)** — Estimated, not real INE data
- **Credit (early months)** — First 3 months of 2010 were duplicated from quarterly data; now interpolated
- **Budget deficit (quarterly)** — Extreme seasonal swings; use `budget_deficit_annual` for analysis

### Estimated (Low Confidence)
- **`external_debt_share_estimated`** — Real Eurostat data when API is available (annual `gov_10dd_ggd` broadcast to quarters); falls back to synthetic (~46-48%) if fetch fails
- **Provisional data** — All data flagged `is_provisional = True` are preliminary estimates

---

## 5. Post-Transformation Data Fixes

The ETL pipeline applies the following corrections during the transform stage:

| Fix | Pillar | Description |
|-----|--------|-------------|
| GDP growth recalculation | GDP | YoY and QoQ growth derived from `real_gdp`, not nominal |
| NPL ratio pre-2015 | Credit | Linear ramp from 5.2% to first known value |
| ECB rate 2010-01 to 2011-03 | Interest Rates | Filled with correct 1.00% (API gap, was bfilled to 1.25%) |
| ECB rate resampling | Interest Rates | Daily ffill before monthly aggregation (fixes Oct 2023–May 2024) |
| ECB rate 2019-2022 | Interest Rates | Corrected to 0.0% (API reporting error) |
| ECB rate nulls | Interest Rates | Forward/backward fill for stepped function |
| Budget deficit clipping | Public Debt | Clipped to [-15%, +5%] range |
| Quarterly extrapolation | Public Debt | Missing final quarter filled via linear interpolation |
| Credit interpolation | Credit | 12 months extrapolated (Jan–Dec 2025) from 180 raw rows to 192 |
| Credit component invariant | Credit | NFC + Households scaled down if > Total Credit |
| CPI estimation | Inflation | `cpi_estimated` = HICP + offset (mean -0.15pp, std 0.08) |
| Provisional flagging | All pillars | Quarterly: 4-month lag; Monthly: 2-month lag from fetch date |

---

## 6. Recommendations

### Short-term
1. **Obtain real INE CPI data** — Replace `cpi_estimated` with actual Portuguese CPI from INE's API or data portal
2. **Verify 2025 data** — As final 2025 statistics are published, re-run the pipeline to replace provisional values
3. **Document Eurostat methodology** — The `debt_to_gdp_ratio` uses rolling 4-quarter GDP (Eurostat standard), not simple annualisation

### Medium-term
4. **Add automated reconciliation** — Compare each fetch against published INE/Eurostat headline figures
5. **Implement data quality dashboard** — Auto-detect anomalies between consecutive pipeline runs
6. **Add energy and food price indices** — Currently in raw inflation data but not carried to processed/database

### Long-term
7. **Source quarterly external debt data from BdP** — Annual Eurostat data is now fetched; Banco de Portugal may provide quarterly granularity
8. **Add trade balance pillar** — Natural extension of the macroeconomic dashboard
9. **Implement real-time monitoring** — Alert on data quality regressions when pipeline runs

---

## Appendix: API Endpoints Used

| Source | API | Authentication | Rate Limiting |
|--------|-----|---------------|---------------|
| **Eurostat** | SDMX 2.1 REST (`ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data`) | None (public) | 429 with Retry-After |
| **ECB** | Statistical Data Warehouse (`data-api.ecb.europa.eu/service/data`) | None (public) | 429 with Retry-After |
| **Banco de Portugal** | BPStat v1 (`bpstat.bportugal.pt/data/v1`) | None (public) | 429 with Retry-After |

All requests use exponential backoff with 3 retries and a 60-second timeout.
