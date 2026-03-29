# Data Provenance

This document records the results of real data ingestion from official APIs.

## Last Successful Fetch

**Date:** 2026-03-18
**Status:** All 7 data sources successfully fetched
**Total execution time:** ~170 seconds

## API Results

| Pillar | Source | API | Rows | Period | Status |
|--------|--------|-----|------|--------|--------|
| GDP | Eurostat | SDMX 2.1 (`namq_10_gdp`, `nama_10_pc`) | 64 | 2010 Q1 - 2025 Q4 | OK |
| Unemployment | Eurostat | SDMX 2.1 (`une_rt_m`, `une_ltu_q`, `lfsq_argan`) | 192 | 2010-01 - 2025-12 | OK |
| Interest Rates | ECB | Data API (`FM/B.U2.EUR.4F.KR.MRR_FR.LEV`, etc.) | 192 | 2010-01 - 2025-12 | OK |
| Inflation | Eurostat | SDMX 2.1 (`prc_hicp_manr`, `prc_hicp_midx`) | 192 | 2010-01 - 2025-12 | OK |
| Credit | Banco de Portugal | BPStat API (`12457932`, `12559924`, `12457924`, `12504544`) | 180 | 2010-01 - 2024-12 | OK |
| Public Debt | Eurostat | SDMX 2.1 (`gov_10q_ggdebt`, `gov_10q_ggnfa`, `gov_10dd_ggd`) | 63 | 2010 Q1 - 2025 Q3 | OK |
| EU Benchmark | Eurostat + ECB | Synthetic benchmark, 7 countries | 560 | 2010 - 2025 | OK |

## Data Integrity

Each raw CSV file has two sidecar files for integrity verification:

- **`.sha256`** — SHA-256 checksum of the CSV file
- **`.meta.json`** — Provenance metadata (filename, row count, columns, fetch timestamp, checksum)

### Checksums

| File | SHA-256 (first 16 chars) | Rows |
|------|-------------------------|------|
| `raw_gdp.csv` | `36d6d290ee62eeef` | 64 |
| `raw_unemployment.csv` | `6e312fe9461e8435` | 192 |
| `raw_interest_rates.csv` | `cf7814a2c4b9a169` | 192 |
| `raw_inflation.csv` | `7dfc43e8167537c9` | 192 |
| `raw_credit.csv` | `697ebd4eff33bf0b` | 180 |
| `raw_public_debt.csv` | `aad771683852720a` | 63 |
| `raw_eu_benchmark.csv` | `1c1f3ff6773a5fbd` | 560 |

## API Endpoints

### Eurostat (SDMX 2.1)
- **Base URL:** `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1`
- **Format:** JSON
- **Authentication:** None (public API)
- **Rate limiting:** Polite delay of 0.3s between requests

### ECB Data API
- **Base URL:** `https://data-api.ecb.europa.eu/service/data`
- **Format:** CSV
- **Authentication:** None (public API)
- **Rate limiting:** Polite delay of 0.5s between requests

### Banco de Portugal (BPStat)
- **Base URL:** `https://bpstat.bportugal.pt/data/v1`
- **Format:** JSON
- **Authentication:** None (public API)
- **Rate limiting:** Polite delay of 0.3s between requests

## Notes

- Credit data ends at 2024-12 (BPStat publishes with a lag)
- Public debt data has 63 rows instead of 64 (2025 Q4 not yet published)
- All APIs use retry logic with exponential backoff (3 retries, 2s base delay)
- The pipeline falls back to synthetic data generation if any API fetch fails

## Transformation Notes (raw → processed)

The following modifications occur during the transform phase:

| Pillar | Raw Rows | Processed Rows | Notes |
|--------|----------|---------------|-------|
| GDP | 64 | 64 | YoY/QoQ growth recalculated from `real_gdp` (not nominal) |
| Unemployment | 192 | 192 | Quarterly indicators interpolated to monthly |
| Credit | 180 | 192 | **12 months extrapolated** via linear interpolation (Jan-Dec 2025, BPStat lag) |
| Interest Rates | 192 | 192 | ECB rate forward-filled for 21 missing months (Jan 2010 - Mar 2011, Jul-Dec 2025) |
| Inflation | 192 | 192 | `cpi_estimated` derived from HICP with offset (-0.15pp mean) |
| Public Debt | 63 | 64 | **1 quarter extrapolated** (2025-Q4 via forward-fill); `budget_deficit_annual` added as rolling 4-quarter average |
| EU Benchmark | 560 | 560 | Synthetic benchmark with realistic reference values + noise (seed=43) |
