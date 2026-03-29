# Portugal Data Intelligence — Architecture Review (v2)

**Date:** 2026-03-25
**Scope:** Full codebase analysis — 143 tracked files, 10K+ lines of Python

---

## 1. Architecture Overview

The project follows a **layered pipeline architecture** with 9 distinct layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                        ENTRY POINTS                             │
│  main.py (CLI)  │  api/main.py (REST)  │  dashboard/app.py (UI)│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: CONFIGURATION          config/settings.py             │
│  Layer 2: DATA INGESTION         etl/fetch_real_data.py         │
│  Layer 3: DATA PROCESSING        etl/extract → transform        │
│  Layer 4: DATA QUALITY           etl/data_quality.py            │
│  Layer 5: DATA STORAGE           etl/load.py → SQLite           │
│  Layer 6: ANALYSIS               analysis/*.py (8 modules)      │
│  Layer 7: INSIGHTS               ai_insights/*.py               │
│  Layer 8: REPORTING              reporting/shared_styles.py       │
│  Layer 9: ALERTS                 alerts/alert_engine.py          │
│                                                                 │
│  Cross-cutting: utils/logger.py, etl/lineage.py, etl/api_cache │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
APIs (Eurostat, ECB, BdP)
    │ fallback
    ├──────────► Synthetic Generator
    ▼
data/raw/*.csv
    │
    ▼
[Extract] → [Transform] → [Data Quality Gate] → [Load] → SQLite DB
                                                              │
    ┌─────────────────────────────────────────────────────────┘
    │
    ├─► Statistical Analysis ─► Charts (PNG)
    ├─► Correlation Analysis
    ├─► Forecasting (SARIMAX + Ensemble)
    ├─► Scenario Analysis (Stress Tests)
    ├─► AI Insights (Rule-based + GPT-4)
    │       │
    │       ▼
    ├─► Streamlit Dashboard (4 pages)
    ├─► REST API (FastAPI, 7 endpoints)
    └─► Interactive Dashboard (Streamlit, 4 pages)
```

---

## 2. What Works Well

### Strengths

| Area | Assessment | Details |
|------|:---:|---------|
| **Dependency Graph** | Excellent | Zero circular dependencies. Clean acyclic module graph |
| **Configuration** | Excellent | Single source of truth in `config/settings.py`, used by 35+ modules |
| **Database Schema** | Excellent | Star schema aligned across DDL, Transform, and Load layers |
| **Naming Conventions** | Excellent | 100% snake_case consistency, PascalCase for classes |
| **Fallback Strategy** | Excellent | API → Synthetic data, SARIMAX → Log-linear, OpenAI → Rule-based |
| **Data Quality** | Excellent | 15+ checks with configurable fail/warn gates |
| **Documentation** | Excellent | Every module has comprehensive docstrings |
| **Test Coverage** | Good | 32 test files, 206+ test cases (ETL and Analysis well covered) |
| **Separation of Concerns** | Good | 9 layers with clear responsibilities |
| **Reproducibility** | Good | Fixed RNG seeds, lineage tracking with SHA-256 checksums |

### Database Safety Measures
- `PRAGMA foreign_keys = ON` enforced
- `INSERT OR REPLACE` for idempotency
- `UNIQUE (date_key, source_key)` prevents duplicates
- `CHECK` constraints on all numeric columns
- SQL injection prevention via whitelist in alert_engine.py

---

## 3. Issues Found

### CRITICAL: Database Connection Leaks

**10+ files** open `sqlite3.connect()` without closing or using context managers:

| File | Line | Pattern |
|------|------|---------|
| `src/analysis/correlation_analysis.py` | 189, 278, 372, 494 | `conn = sqlite3.connect()` — never closed |
| `src/analysis/statistical_analysis.py` | 616, 661 | Same pattern |
| `src/analysis/backtesting.py` | 169 | Same pattern |
| `src/analysis/decomposition.py` | 156 | Same pattern |
| `src/analysis/significance_tests.py` | 546 | Same pattern |
| `src/ai_insights/cross_pillar_insights.py` | 229 | Same pattern |
| `src/etl/generate_eu_benchmark.py` | 395, 419 | Same pattern |

**Impact:** Resource leaks under sustained usage (API/Dashboard scenarios).

**Recommendation:** Create a shared `get_connection()` context manager in `src/utils/db.py` and use it everywhere.

---

### HIGH: Duplicated Constants (4 locations)

**CRISIS_PERIODS** is defined in 4 different files with slightly different formats:

| File | Format |
|------|--------|
| `src/analysis/statistical_analysis.py:23` | `{key: (start, end)}` |
| `src/ai_insights/insight_engine.py:72` | `{key: {"years": (s,e), "label": "..."}}` |
| `src/analysis/significance_tests.py:124` | `{key: (start, end)}` |
| `src/analysis/visualisations.py:68` | `{key: ("start", "end")}` (strings!) |

**Impact:** Adding a new crisis period requires updating 4 files. Risk of inconsistency.

**Recommendation:** Define once in `config/settings.py` as:
```python
CRISIS_PERIODS = {
    "sovereign_debt_crisis": {"years": (2011, 2014), "label": "Sovereign Debt Crisis"},
    "covid_pandemic": {"years": (2020, 2021), "label": "COVID-19 Pandemic"},
    "energy_crisis": {"years": (2022, 2023), "label": "Energy and Inflation Crisis"},
}
```

---

### HIGH: Duplicate `get_connection()` Functions

Database connection functions are defined in 3+ places:

| File | Function | Notes |
|------|----------|-------|
| `src/etl/load.py:56` | `get_connection()` | Context manager with PRAGMAs |
| `api/main.py:73` | `get_connection()` | With row_factory |
| `src/ai_insights/insight_engine.py:195` | `_get_connection()` | Simple connect |
| `dashboard/app.py:63` | Inline `sqlite3.connect()` | In cached function |

**Recommendation:** Consolidate into `src/utils/db.py`.

---

### MEDIUM: Hardcoded Values Outside Config

| File | Line | Value | Should Be |
|------|------|-------|-----------|
| `src/etl/fetch_real_data.py` | 46-48 | `TIMEOUT=60, RETRY=2, MAX_RETRIES=3` | `config/settings.py` |
| `src/etl/data_quality.py` | 313 | `_ZSCORE_THRESHOLD = 3.0` | Config constant |
| `src/etl/data_quality.py` | 61-68 | `_EXPECTED_ROWS = {gdp: 64, ...}` | Derive from `START_YEAR`/`END_YEAR` |
| `src/etl/transform.py` | 77, 108 | `np.random.seed(42)`, `seed(43)` | `config/settings.py` |
| `src/analysis/scenario_analysis.py` | 478 | `avg_growth = 0.02` | Config or estimate from data |

---

### MEDIUM: Test Coverage Gaps

| Module | Has Tests? | Notes |
|--------|:---:|-------|
| `api/main.py` | No | No `test_api.py` — REST endpoints untested |
| `dashboard/app.py` | No | No `test_dashboard.py` |
| `main.py` (orchestrator) | No | No end-to-end mode testing |
| `config/settings.py` | No | No `test_config.py` |
| `src/etl/api_cache.py` | No | New module, needs tests |
| `src/analysis/ensemble_forecast.py` | No | New module, needs tests |

---

### LOW: Minor Issues

| Issue | Details |
|-------|---------|
| **Dead import** | `visualisations.py:52` — `import sys as _sys` only used for path hack |
| **Mixed English** | Mostly British (`visualisations`, `colour`) with occasional American (`analyze`) |
| **`index.html` root** | Removed from git but still on disk — can be deleted |

---

## 4. Architecture Diagram

### Module Dependency Graph (Simplified)

```
config/settings.py ◄──────────────────────────────────────────┐
       │                                                       │
       ▼                                                       │
src/utils/logger.py ◄─────────────────────────────────────────┤
       │                                                       │
       ▼                                                       │
src/etl/                                                       │
  ├── fetch_real_data.py ──► generate_data.py (fallback)       │
  ├── extract.py                                               │
  ├── transform.py                                             │
  ├── data_quality.py                                          │
  ├── load.py ──────────────► sql/ddl/*.sql                    │
  ├── lineage.py                                               │
  ├── generate_eu_benchmark.py                                 │
  └── api_cache.py (NEW)                                       │
       │                                                       │
       ▼ [SQLite Database]                                     │
       │                                                       │
src/analysis/                                                  │
  ├── statistical_analysis.py ◄─── significance_tests.py       │
  ├── correlation_analysis.py                                  │
  ├── forecasting.py ◄──────────── ensemble_forecast.py (NEW)  │
  ├── backtesting.py                                           │
  ├── decomposition.py                                         │
  ├── benchmarking.py                                          │
  ├── scenario_analysis.py                                     │
  └── visualisations.py ◄──── src/reporting/shared_styles.py ──┘
       │
src/ai_insights/
  ├── insight_engine.py (facade)
  ├── pillar_insights.py (rule-based)
  ├── cross_pillar_insights.py
  └── ai_narrator.py (GPT-4, optional)
       │
src/reporting/
  └── shared_styles.py (chart colours, fonts, matplotlib config)

src/alerts/
  └── alert_engine.py (standalone)

api/main.py (FastAPI, read-only)
dashboard/app.py (Streamlit, read-only)
```

---

## 5. Recommendations (Priority Order)

### Must Fix

1. **Create `src/utils/db.py`** — single connection manager used by all modules
2. **Consolidate CRISIS_PERIODS** — define once in `config/settings.py`
3. **Fix connection leaks** — use context managers in all 10+ affected files

### Should Fix

4. **Add test files** for `api/`, `dashboard/`, `ensemble_forecast.py`, `api_cache.py`
5. **Move hardcoded values** (timeouts, thresholds, seeds) to `config/settings.py`
6. **Consolidate `get_connection()`** functions into `src/utils/db.py`

### Nice to Have

7. **Add `convert_date_key()` utility** for quarterly/monthly conversion
8. **Standardise English** to British throughout (currently 95% British)
9. **Delete root `index.html`** from disk (already removed from git)

---

## 6. File Statistics

| Category | Count |
|----------|-------|
| Python modules (src/) | 41 |
| Test files | 32 |
| SQL files | 10 |
| Config files | 8 |
| Documentation files | 11 |
| **New v2 files** | **5** |
| Total tracked files | 123 (was 143, removed 20 generated) |

### Lines of Code by Layer

| Layer | Approx. Lines |
|-------|:---:|
| ETL | 2,500 |
| Analysis | 3,500 |
| AI Insights | 1,800 |
| Reporting | 1,500 |
| Alerts | 200 |
| API + Dashboard | 600 |
| Config + Utils | 450 |
| Tests | 3,000 |
| **Total** | **~13,500** |
