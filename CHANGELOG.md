# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [2.5.0] - 2026-06-12

### Fixed
- **Inequality pillar now carries the official Eurostat EU-SILC series.**
  `fetch_inequality` queried the wrong dataset (`ilc_di12b`, the
  before-social-transfers variant) and silently fell back to a smoothed
  synthetic series that missed the official Gini spikes of 2021 (33.0) and
  2023 (33.7) by up to 2.8 points. It now fetches `ilc_di12` (Gini),
  `ilc_di11` (S80/S20) and `ilc_li02` (poverty risk) live, with the published
  official series embedded as the offline fallback — both paths produce the
  official values. The median income index remains an estimate and the
  `source` column says so.
- **Regional youth unemployment populated with official data.** The
  `youth_unemployment_rate` column was 100% null by construction; it now
  carries the official `lfst_r_lfu3rt` (15-24) series for the years Eurostat
  publishes (58 of 112 region-years — full for Norte; the islands and the
  discontinued pre-2024 NUTS codes have genuine gaps).
- **Report methodology corrected.** The HTML report claimed *"All data is
  sourced from authoritative national and European statistical institutions"*
  and a *"7-layer validation framework"*; it now distinguishes official from
  modelled/calibrated pillars and describes the actual 8-check framework.
- Documentation drift: SECURITY.md supported versions (was stuck at 2.2.x),
  README data note and provenance doc updated for the new pillar provenance.

### Added
- **Data-quality framework extended to all 12 pillars** (schema, expected
  rows, not-null and plausibility-range checks for housing, labour detail,
  external accounts, fiscal, inequality and regional — roughly 170 checks
  per full run, up from ~100; the extended pillars previously only had a
  freshness check). An all-null column like the old regional youth series
  now fails instead of passing silently.

### Changed
- Test suite no longer rewrites `data/processed/*.csv` or the data-quality
  drift baseline: artefact writes are redirected to a session temp directory.
- Docker container now runs as a non-root `appuser`, and `docker-compose up`
  works without a `.env` file (it is optional).
- Committed `raw_eu_benchmark.csv` realigned with the pipeline generator
  output (560 rows, 5 indicators, EU/EA averages). The previous snapshot was
  written by a separate fetch path (160 rows, 2 indicators) that the pipeline
  never read; that dead fetch path has been removed, leaving
  `generate_eu_benchmark.py` as the single producer of the benchmark dataset.

## [2.4.0] - 2026-06-11

### Changed
- **HTML report redesigned** as an editorial consulting publication: Source
  Serif 4 / Inter typography, a single electric-blue accent with green/red
  reserved for data semantics, editorial cover with KPI ticker, sticky
  numbered contents rail with scroll-spy, a numbered "Exhibit N" system for
  every chart, hairline KPI grid and tables, tinted risk badges, and an
  updated print stylesheet.
- **Matplotlib chart suite aligned** with the same design language via the
  central `shared_styles` palette (blue / deep navy / cyan series; Portugal
  carries the brand blue in benchmark charts; muted crisis-period shading).
- Streamlit dashboard imports the shared palette instead of duplicating hex
  values; its correlation heatmap now uses the standard blue-white-red
  diverging scale.
- Tutorial updated to describe snapshot-first data acquisition (real API
  data committed; synthetic generation only as offline fallback).

### Fixed
- Test suite no longer overwrites committed artefacts (STL chart PNGs and
  the raw data snapshot) when it runs.

## [2.3.0] - 2026-06-11

### Fixed
- **Regional pillar (NUTS2):** PT15/PT18 codes were swapped against their names
  (officially PT15 = Algarve, PT18 = Alentejo), which also mis-painted the report
  choropleth; regional GDP per capita (PPS), the EU27 index, and regional
  unemployment recalibrated to official Eurostat series (`nama_10r_2gdp`,
  `lfst_r_lfu3rt`), with the EU27 index now computed against the correct
  per-year EU27 average instead of a fixed 2020 denominator.
- **Housing pillar:** house price index aligned with the official Eurostat
  annual series (2010 was ~7% *above* the 2015 level; the 2024/2025 YoY profile
  now matches the official +9.1% / +17.6%); transactions, median price per m²,
  and new mortgage lending calibrated to INE / BdP figures (2025 mortgage
  record of EUR 23.3bn was previously missing).
- **Fiscal pillar:** revenue and expenditure (% GDP) replaced with the official
  Eurostat `gov_10a_main` series (recent years were overstated by ~2.5pp).
- **EU benchmark:** 2021-2025 reference points updated to the current official
  vintage (Spain's post-2021 boom, Germany's 2023-24 recession, France's 2025
  disinflation and bond-yield rise; Portugal's own values now match the core
  pillars).
- **Report narrative:** garbled interest-rate chronology sentence; quarterly
  budget figure presented as an annual "surplus of -3.0%"; "debt below 100%
  for the first time since 2011" (it first fell below 100% in 2023, now
  computed from the data); crisis-window peaks now use real observations
  (e.g. unemployment "peaked at 18.3%", not the 17.2% annual-average maximum);
  GDP per capita vs the EU stated in PPS (~82%) instead of the nominal ~70%.
- README correlation figures refreshed to match the data (0.71 / -0.48).

## [2.2.0] - 2026-06-08

### Added
- Expanded coverage to **12 macroeconomic pillars** plus NUTS2 regional analysis.
- VAR / Granger causality, GDP nowcasting, SARIMAX forecasting with model caching,
  and z-score / Isolation Forest anomaly detection.
- EU benchmarking (radar + small multiples) and cross-pillar correlation analysis.
- Self-contained interactive HTML report (Plotly) wired into the pipeline.
- FastAPI REST API, data-quality validation framework, and configurable alert engine.
- Deterministic, committed raw data snapshot — the pipeline rebuilds offline by
  default (`--refresh` re-fetches live data).
- CI security scanning (`bandit`, `pip-audit`), `mypy` type-checking, and a
  `SECURITY.md` policy.

### Changed
- HTML report generation is now a pipeline step (`--mode reports` / `--mode full`),
  so the executive briefing, KPI cards, and report always come from the same run.
- Unified the project version behind a single `config.settings.VERSION`.
- Recalibrated estimated series (housing, regional, sector employment, fiscal,
  wages, productivity) for realism; core macro series validated against
  INE / Eurostat / Banco de Portugal / ECB.

### Fixed
- Report data consistency (narrative vs KPI cards), regional GDP placeholder values,
  credit labelling, and HTML report typography / XSS hardening.
- Constant-time API-key comparison and more reliable "latest value" queries in the API.

### Removed
- Scheduled "weekly data refresh" workflow — the committed dataset is deterministic,
  so live re-fetching only introduced non-determinism.

## [1.0.0] - 2026-03-29

### Added
- Initial release: ETL pipeline (extract / transform / load to SQLite), statistical
  analysis, AI / rule-based insights, REST API, and Streamlit dashboard.
- Power BI dashboard with DAX measures and CI (lint / test / build) across
  Python 3.10–3.12.

[2.4.0]: https://github.com/diogomserino/Portugal-Data-Intelligence/releases/tag/v2.4.0
[2.3.0]: https://github.com/diogomserino/Portugal-Data-Intelligence/releases/tag/v2.3.0
[2.2.0]: https://github.com/diogomserino/Portugal-Data-Intelligence/releases/tag/v2.2.0
[1.0.0]: https://github.com/diogomserino/Portugal-Data-Intelligence/releases/tag/v1.0.0
