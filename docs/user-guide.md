# User Guide

## Pipeline Overview

The Portugal Data Intelligence pipeline processes macroeconomic data through six stages:

```
Data Sources → Extract → Transform → Load → Analyse → Report
```

Each stage is tracked with a unique `run_id` for full lineage traceability.

## Data Pillars

| Pillar | Granularity | Key Indicators |
|--------|------------|----------------|
| GDP | Quarterly | Nominal/real GDP, YoY/QoQ growth, per capita |
| Unemployment | Monthly | General, youth, long-term rates, participation |
| Credit | Monthly | Total, NFC, household credit, NPL ratio |
| Interest Rates | Monthly | ECB MRR, Euribor 3M/6M/12M, PT 10Y bond |
| Inflation | Monthly | HICP, CPI, core inflation |
| Public Debt | Quarterly | Total debt, debt-to-GDP, budget deficit |

## Data Quality

The pipeline includes an automated quality gate between the Transform and Load stages. The `DataQualityChecker` runs 15+ checks:

- **Schema validation** — expected columns and types
- **Range checks** — values within plausible bounds
- **Completeness** — no gaps in time series
- **Cross-pillar consistency** — logical relationships hold
- **Freshness** — data reaches the expected end date

Reports are saved to `reports/data_quality/dq_report_{run_id}.json`.

Set `DQ_FAIL_ON_ERROR=true` to halt the pipeline on critical failures.

## Forecasting

The forecasting module provides 3-year projections using:

- **SARIMAX** (primary) — automatic order selection via AIC, with Ljung-Box residual diagnostics
- **Log-linear trend** (fallback) — for GDP and credit aggregates
- **Mean-reversion** (fallback) — for rates, ratios, and bounded indicators

All forecasts include 68% and 95% confidence bands.

### Backtesting

Forecast accuracy is validated using expanding-window cross-validation. Metrics reported:

- MAE (Mean Absolute Error)
- RMSE (Root Mean Square Error)
- MAPE (Mean Absolute Percentage Error)
- Directional accuracy

Results are saved to `reports/backtesting_results.json`.

## Scenario Analysis

The `ScenarioEngine` supports four stress scenarios:

| Scenario | Key Parameter | Impacts Modelled |
|----------|--------------|-----------------|
| Interest Rate Shock | Rate increase (bps) | Debt servicing, mortgage costs, credit growth |
| GDP Slowdown | GDP contraction (%) | Unemployment (Okun's law), debt ratio, tax revenue |
| Inflation Spike | Inflation target (%) | Real rates, purchasing power, debt dynamics |
| Fiscal Consolidation | Deficit target (%) | GDP impact (fiscal multiplier), debt trajectory |

Coefficients are estimated from historical data where possible, with documented textbook fallbacks.

## Alert System

The alert engine monitors 6 key indicators against configurable thresholds:

| Indicator | Warning | Critical |
|-----------|---------|----------|
| GDP Growth (YoY) | < -1.0% | < -3.0% |
| Unemployment Rate | > 8.0% | > 12.0% |
| HICP Inflation | > 4.0% or < -0.5% | > 8.0% or < -1.0% |
| Debt-to-GDP | > 100% | > 130% |
| NPL Ratio | > 5.0% | > 10.0% |
| PT 10Y Bond Yield | > 4.0% | > 7.0% |

Thresholds are defined in `config/alert_thresholds.json` and can be modified without code changes.

Alerts are saved to `reports/alerts/alerts_{timestamp}.json`.

## EU Benchmarking

Portugal's indicators are compared against peer countries (Germany, Spain, France, Italy) and EU/Euro Area averages across 5 dimensions:

- GDP growth
- Unemployment rate
- Inflation
- Debt-to-GDP ratio
- 10-year bond yield

Convergence analysis tracks whether Portugal is converging toward or diverging from EU averages over time.
