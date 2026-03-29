# =============================================================================
# Portugal Data Intelligence — Makefile
# =============================================================================
# Usage:
#   make install       Install production dependencies
#   make install-dev   Install dev + production dependencies
#   make etl           Run ETL pipeline only
#   make analysis      Run analysis + charts only
#   make reports       Generate reports + insights
#   make run           Run full pipeline (ETL → Analysis → Reports)
#   make test          Run test suite with coverage
#   make lint          Run code quality checks (black, isort, flake8)
#   make format        Auto-format code (black + isort)
#   make typecheck     Run mypy type checking
#   make clean         Remove generated files and caches
# =============================================================================

.PHONY: install install-dev etl analysis reports run test lint format typecheck clean help report-html

PYTHON ?= python

# ── Dependencies ─────────────────────────────────────────────────────────────

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# ── Pipeline ─────────────────────────────────────────────────────────────────

etl:
	$(PYTHON) main.py --mode etl

analysis:
	$(PYTHON) main.py --mode analysis

reports:
	$(PYTHON) main.py --mode reports

run:
	$(PYTHON) main.py --mode full

quick:
	$(PYTHON) main.py --mode quick

# ── Reports ──────────────────────────────────────────────────────────────────

report-html:
	$(PYTHON) dashboard/generate_report.py

# ── Documentation ─────────────────────────────────────────────────────────────

docs:
	mkdocs build

docs-serve:
	mkdocs serve

# ── Quality ──────────────────────────────────────────────────────────────────

test:
	pytest

lint:
	black --check --diff src/ tests/ main.py config/
	isort --check-only --diff src/ tests/ main.py config/
	flake8 src/ tests/ main.py config/ --max-line-length 100

format:
	black src/ tests/ main.py config/
	isort src/ tests/ main.py config/

typecheck:
	mypy src/ config/

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -f data/database/*.db
	rm -rf logs/*.log
	rm -rf reports/insights/*.json
	rm -rf htmlcov/ .coverage

# ── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Portugal Data Intelligence — Available targets:"
	@echo ""
	@echo "  install       Install production dependencies"
	@echo "  install-dev   Install dev + production dependencies"
	@echo "  etl           Run ETL pipeline only"
	@echo "  analysis      Run analysis + charts only"
	@echo "  reports       Generate reports + insights"
	@echo "  run           Run full pipeline"
	@echo "  quick         ETL + analysis (skip reports)"
	@echo "  test          Run test suite with coverage"
	@echo "  lint          Run code quality checks"
	@echo "  format        Auto-format code"
	@echo "  typecheck     Run mypy type checking"
	@echo "  clean         Remove generated files and caches"
	@echo ""
