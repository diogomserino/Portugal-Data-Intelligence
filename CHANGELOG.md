# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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

[2.2.0]: https://github.com/diogomserino/Portugal-Data-Intelligence/releases/tag/v2.2.0
[1.0.0]: https://github.com/diogomserino/Portugal-Data-Intelligence/releases/tag/v1.0.0
