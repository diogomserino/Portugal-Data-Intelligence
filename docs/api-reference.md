# API Reference

## ETL Pipeline

### PipelineTracker

Context manager for tracking pipeline runs with lineage.

```python
from src.etl.lineage import PipelineTracker

with PipelineTracker(mode="full") as tracker:
    tracker.record("gdp", "extract", rows_in=0, rows_out=64)
    tracker.record("gdp", "transform", rows_in=64, rows_out=64)
    tracker.record("gdp", "load", rows_in=64, rows_out=64)
```

**Attributes:**

- `run_id: str` — UUID-based correlation ID for the pipeline run
- `mode: str` — Pipeline mode (e.g., "full", "etl", "analysis")
- `records: List[LineageRecord]` — Collected lineage records

**Methods:**

- `record(pillar, stage, rows_in, rows_out, null_count, checksum)` — Append a lineage record
- Persists to `pipeline_runs` and `data_lineage` tables on context exit

---

### DataQualityChecker

Validates processed DataFrames before database loading.

```python
from src.etl.data_quality import DataQualityChecker

checker = DataQualityChecker(processed_data, run_id="abc123")
report = checker.run_all()
report.save()  # saves to reports/data_quality/
```

**Constructor:**

- `processed_data: Dict[str, pd.DataFrame]` — DataFrames keyed by pillar name
- `run_id: Optional[str]` — Pipeline correlation ID

**Methods:**

- `check_schema()` — Verify expected columns exist
- `check_not_null()` — Primary metrics must not be entirely null
- `check_ranges()` — Values within plausible bounds (configured in `settings.DATA_RANGES`)
- `check_completeness()` — No gaps in date sequences
- `check_consistency()` — Cross-pillar logical relationships hold
- `check_freshness()` — Latest data reaches expected end year
- `run_all() -> DQReport` — Execute all checks

**DQReport Properties:**

- `passed: int`, `warnings: int`, `failures: int`
- `has_critical_failure: bool`
- `save(directory) -> Path` — Write JSON report

---

## Analysis

### Forecaster

Generates 3-year forward projections for all pillars.

```python
from src.analysis.forecasting import Forecaster

fc = Forecaster(db_path="data/database/portugal_data_intelligence.db")
gdp_forecast = fc.forecast_gdp(horizon=12)
all_forecasts = fc.generate_all_forecasts()
fc.close()
```

**Constructor:**

- `db_path: Optional[str]` — Path to SQLite database (defaults to project database)

**Methods:**

- `forecast_gdp(horizon=12) -> dict` — SARIMAX (primary) or log-linear trend (fallback)
- `forecast_unemployment(horizon=36) -> dict` — Exponential smoothing + mean-reversion
- `forecast_inflation(horizon=36) -> dict` — SARIMAX (primary) or mean-reversion (fallback)
- `forecast_interest_rates(horizon=36) -> dict` — Mean-reversion model
- `forecast_credit(horizon=36) -> dict` — Log-linear trend on recent 3 years
- `forecast_public_debt(horizon=12) -> dict` — Debt dynamics equation
- `generate_all_forecasts() -> dict` — Run all pillar forecasts
- `close()` — Close the database connection

**Forecast output structure:**

```json
{
    "indicator": "Real GDP (EUR millions)",
    "method": "SARIMAX",
    "forecast": [
        {"period": "2026-Q1", "central": 55000, "lower_68": 53000, "upper_68": 57000, ...}
    ],
    "diagnostics": {"aic": 450.2, "bic": 465.1, "ljung_box_pvalue": 0.45}
}
```

---

### ScenarioEngine

Runs macroeconomic stress scenarios for Portugal.

```python
from src.analysis.scenario_analysis import ScenarioEngine

engine = ScenarioEngine(db_path="data/database/portugal_data_intelligence.db")
result = engine.rate_shock_scenario(rate_increase_bps=200)
```

**Constructor:**

- `db_path: Optional[str]` — Path to SQLite database

**Methods:**

- `rate_shock_scenario(rate_increase_bps=200) -> dict` — ECB rate increase impact
- `gdp_slowdown_scenario(gdp_shock_pct=-2.0) -> dict` — GDP contraction impact
- `inflation_spike_scenario(inflation_target=6.0) -> dict` — Inflation surge impact
- `fiscal_consolidation_scenario(deficit_target=-1.0) -> dict` — Fiscal adjustment path

**Calibration:**

Coefficients (Okun's law, fiscal multiplier, credit-rate elasticity) are estimated from the data where possible. Fallback values use documented academic sources (Blanchard 2017, IMF 2014, ECB 2023).

Access calibration sources via `engine.calibration_sources` dict.

---

## AI Insights

### InsightEngine

Generates executive-level narrative commentary.

```python
from src.ai_insights.insight_engine import InsightEngine

engine = InsightEngine(use_ai=False)  # rule-based mode
briefing = engine.generate_executive_briefing()
insight = engine.generate_pillar_insight("gdp")
```

**Constructor:**

- `db_path: Optional[str]` — Database path
- `use_ai: bool` — If `True` and `OPENAI_API_KEY` is set, uses GPT-4

**Methods:**

- `generate_pillar_insight(pillar) -> dict` — Single pillar narrative with headline, summary, findings, risk assessment, recommendations, outlook
- `generate_cross_pillar_insights() -> dict` — Relationship analysis (Okun's law, rate transmission, inflation-policy, debt-growth)
- `generate_executive_briefing() -> dict` — Complete briefing with all pillars, cross-pillar analysis, strategic recommendations, and risk matrix

---

## Alerts

### AlertEngine

Monitors indicators against configurable thresholds.

```python
from src.alerts.alert_engine import AlertEngine

engine = AlertEngine()
alerts = engine.check_all()
engine.save_alerts(alerts)
```

**Constructor:**

- `db_path: Optional[Path]` — Database path
- `thresholds_path: Optional[Path]` — Path to thresholds JSON

**Methods:**

- `check_all() -> List[Alert]` — Check all configured indicators, return triggered alerts (sorted by severity)
- `save_alerts(alerts, directory) -> Path` — Save alerts as timestamped JSON

**Alert dataclass:**

```python
@dataclass
class Alert:
    indicator: str      # e.g., "unemployment_rate"
    description: str    # e.g., "Unemployment Rate (%)"
    severity: str       # "warning" or "critical"
    value: float        # current value
    threshold: float    # breached threshold
    direction: str      # "above" or "below"
    period: str         # date_key of the observation
    timestamp: str      # ISO timestamp
```
