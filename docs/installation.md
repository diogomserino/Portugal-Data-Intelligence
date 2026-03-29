# Installation

## Requirements

- Python 3.10 or higher
- pip (Python package manager)
- Git (for version control)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/dms1996/portugal-data-intelligence.git
cd portugal-data-intelligence
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
.venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (includes testing, linting, docs)
pip install -r requirements-dev.txt
```

### 4. Run the pipeline

```bash
python main.py
```

This will:

1. Fetch real data from official APIs (Eurostat, ECB, Banco de Portugal)
2. Fall back to synthetic data generation if APIs are unavailable
3. Run the ETL pipeline (Extract, Transform, Load into SQLite)
4. Generate EU benchmark comparison data
5. Run statistical analysis and create charts
6. Generate AI-powered insights (rule-based by default)
7. Generate AI-powered executive briefing

## Docker (alternative)

```bash
docker-compose up
```

This builds and runs the full pipeline in a container, with data and reports mounted as volumes.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (none) | Optional. Enables GPT-4 narrative insights |
| `DQ_FAIL_ON_ERROR` | `false` | If `true`, pipeline halts on data quality failures |
| `LOG_FORMAT_JSON` | `false` | If `true`, log output uses structured JSON format |

Copy `.env.example` to `.env` to set these:

```bash
cp .env.example .env
```

### Pipeline Modes

| Mode | Command | Description |
|------|---------|-------------|
| Full | `python main.py` | All stages |
| ETL only | `python main.py --mode etl` | Data fetch + transform + load |
| Analysis | `python main.py --mode analysis` | Statistical analysis + charts |
| Reports | `python main.py --mode reports` | AI insights + executive briefing |
| Quick | `python main.py --mode quick` | ETL + analysis (skip reports) |

## Verify Installation

```bash
# Run tests
pytest

# Check code quality
make lint
```
