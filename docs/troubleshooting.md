# Troubleshooting Guide

Common issues and solutions for the Portugal Data Intelligence ETL pipeline.

---

## Extract Phase

### `CSV schema validation failed — missing columns`

**Cause:** The raw CSV file does not contain the expected columns for the pillar.

**Solution:**

1. Check `data/raw/raw_<pillar>.csv` headers match the expected schema.
2. If using real data (`fetch_real_data.py`), the API response format may have changed — check the Eurostat/ECB/BPStat documentation.
3. Regenerate synthetic data: `python -c "from src.etl.generate_data import main; main()"`

### `Checksum mismatch for <file>`

**Cause:** The raw CSV has been modified since the `.sha256` sidecar file was written.

**Solution:** This is a warning — the pipeline continues. If the data is correct, delete the `.sha256` file and re-run.

### `File not found: data/raw/raw_<pillar>.csv`

**Cause:** Raw data has not been generated or fetched.

**Solution:**

```bash
# Generate synthetic data
python -c "from src.etl.generate_data import main; main()"

# Or fetch real data from APIs
python -m src.etl.fetch_real_data
```

---

## Transform Phase

### `Could not derive date_key`

**Cause:** The raw DataFrame is missing `date`, `year`, or `quarter` columns needed to create the `date_key`.

**Solution:** Check the raw CSV structure. Monthly pillars need a `date` column; quarterly pillars need `year` + `quarter` or `date`.

### `Clipped N extreme budget_deficit values`

**Cause:** Budget deficit values outside `[-15%, +5%]` were clipped to the valid range.

**Solution:** This is expected behaviour for noisy synthetic data. For real data, investigate the source — Portugal's worst deficit was ~-11.4% (2010).

### `Scaled N rows where NFC + Households exceeded Total`

**Cause:** Credit components (`credit_nfc + credit_households`) exceeded `total_credit`. This can happen with synthetic data or when series are interpolated independently.

**Solution:** Automatic — components are scaled proportionally. No action needed.

---

## Load Phase

### `Cannot resolve source_key`

**Cause:** The `dim_source` table does not contain the expected data source name for the pillar's `primary_sources` config.

**Solution:**

1. Check `config/settings.py` → `DATA_PILLARS[pillar]["primary_sources"]` matches entries in `sql/ddl/seed_dimensions.sql`.
2. Re-initialise the database: delete `data/database/portugal_data_intelligence.db` and re-run the pipeline.

### `Missing required columns: <columns>`

**Cause:** The processed DataFrame does not contain columns expected by the fact table schema.

**Solution:** This indicates a transform issue. Check `src/etl/transform.py` → `_PILLAR_CONFIGS[pillar]["keep_cols"]` matches the expected columns.

### `FOREIGN KEY constraint failed`

**Cause:** The `create_tables.sql` DDL uses `DROP TABLE IF EXISTS` which can fail when foreign key constraints reference existing data.

**Solution:** Delete the database file and re-run:

```bash
rm data/database/portugal_data_intelligence.db
python -m src.etl.pipeline
```

---

## Data Quality

### `DQ_FAIL_ON_ERROR` gate blocking the pipeline

**Cause:** One or more data quality checks returned `fail` status and `DQ_FAIL_ON_ERROR=true` is set.

**Solution:**

1. Check the DQ report in `reports/data_quality/dq_report_<run_id>.json`.
2. Fix the underlying data issue.
3. To bypass temporarily: `DQ_FAIL_ON_ERROR=false python -m src.etl.pipeline`

### `Distribution drift detected`

**Cause:** The current data distribution (mean/std) differs significantly from the saved baseline in `reports/data_quality/dq_baseline.json`.

**Solution:** This is a warning. It can be caused by:

- Legitimate data changes (e.g. new year of data).
- Data source issues (e.g. API returning different series).

If the new distribution is correct, the baseline updates automatically on each run.

### `N value(s) with |Z| > 3.0`

**Cause:** Statistical outliers detected. These may be genuine extreme events (e.g. COVID-era GDP drop).

**Solution:** Review the flagged values. If legitimate, no action needed — this is a warning, not a failure.

---

## API Fetch (`fetch_real_data.py`)

### `Rate limited (429) — waiting Ns`

**Cause:** The Eurostat/ECB API is rate-limiting requests.

**Solution:** Automatic — the fetcher respects `Retry-After` headers and uses exponential backoff with jitter. If persistent, increase `RETRY_DELAY` in `fetch_real_data.py`.

### `Attempt N/3 failed for <url>`

**Cause:** Network error or API downtime.

**Solution:** The fetcher retries up to 3 times with exponential backoff. If all retries fail, the pipeline falls back to synthetic data generation. Check network connectivity and API status pages:

- Eurostat: `https://ec.europa.eu/eurostat`
- ECB: `https://data-api.ecb.europa.eu`
- BPStat: `https://bpstat.bportugal.pt`

---

## Database

### General database corruption

**Solution:** Delete and rebuild:

```bash
rm data/database/portugal_data_intelligence.db
python -m src.etl.pipeline
```

### Missing `fact_eu_benchmark` table

**Cause:** The benchmark table is created during the load phase. If you ran an older version of the pipeline, it may not exist.

**Solution:** The table is now auto-created during schema initialisation. Re-run: `python -m src.etl.pipeline`

---

## Environment

### `ModuleNotFoundError: No module named 'src'`

**Solution:** Run from the project root directory, and ensure the project root is in your Python path:

```bash
# Option 1: set PYTHONPATH (recommended)
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Option 2: run modules with -m flag from the project root
python -m src.etl.pipeline
```

### Tests failing with `coverage` below threshold

**Cause:** `pyproject.toml` sets `fail_under = 75`. Some modules (AI insights, reporting) are excluded from coverage.

**Solution:** Run tests without coverage enforcement:

```bash
python -m pytest tests/ --no-cov
```
