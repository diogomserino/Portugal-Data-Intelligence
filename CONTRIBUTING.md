# Contributing to Portugal Data Intelligence

Thank you for your interest in contributing to this project.

## Prerequisites

- Python 3.10 or higher
- Git

## Development Setup

```bash
# Clone and enter the project
git clone https://github.com/dms1996/portugal-data-intelligence.git
cd portugal-data-intelligence

# Create a virtual environment
python -m venv venv
source venv/bin/activate    # Linux / macOS
venv\Scripts\activate       # Windows

# Install all dependencies (production + dev)
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Running Tests

```bash
# Run full test suite with coverage
pytest

# Run a specific test file
pytest tests/test_api.py -v

# Skip slow tests
pytest -m "not slow"
```

## Code Style

This project uses:

- **black** (line length: 100) for formatting
- **isort** (profile: black) for import ordering
- **flake8** for linting

```bash
# Auto-format
black --line-length 100 src/ tests/
isort --profile black --line-length 100 src/ tests/

# Check without modifying
black --check src/ tests/
flake8 src/ --max-line-length 120 --extend-ignore E501,W503,F401,F541,F841,E402,E203
```

## Branch Convention

- `main` — stable, production-ready code
- `feature/*` — new features
- `fix/*` — bug fixes

## Commit Messages

Use concise, imperative mood messages:

```
fix: guard against empty DataFrame in forecasting
feat: add ensemble forecasting with inverse-MAE weighting
docs: update README with Streamlit dashboard section
```

## Project Structure

See [README.md](README.md) for the full project structure and [docs/architecture_review_v2.md](docs/architecture_review_v2.md) for the architecture analysis.
