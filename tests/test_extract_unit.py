"""Unit tests for src/etl/extract.py — file validation and extraction logic."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

# Realistic CSV headers matching what generate_data.py produces.
_REALISTIC_HEADERS = {
    "raw_gdp.csv": "date,year,quarter,nominal_gdp_eur_millions,real_gdp_eur_millions,gdp_growth_rate_yoy,gdp_growth_rate_qoq,gdp_per_capita_eur,source,country_code",
    "raw_unemployment.csv": "date,year,month,unemployment_rate,youth_unemployment_rate,long_term_unemployment_rate,labour_force_participation_rate,source,country_code",
    "raw_credit.csv": "date,year,month,total_credit_eur_millions,nfc_credit_eur_millions,household_credit_eur_millions,npl_ratio,credit_growth_rate_yoy,source,country_code",
    "raw_interest_rates.csv": "date,year,month,ecb_main_refinancing_rate,euribor_3m,euribor_6m,euribor_12m,portugal_10y_bond_yield,source,country_code",
    "raw_inflation.csv": "date,year,month,hicp_annual_rate,cpi_annual_rate,core_inflation_rate,energy_price_index,food_price_index,source,country_code",
    "raw_public_debt.csv": "date,year,quarter,total_debt_eur_millions,debt_to_gdp_ratio,budget_balance_pct_gdp,external_debt_share,source,country_code",
}

_GDP_ROW = "2020-03-31,2020,1,50000,48000,1.5,0.3,22000,INE,PT"
_UNEMPLOYMENT_ROW = "2020-01-01,2020,1,7.0,22.0,3.5,60.0,INE,PT"
_CREDIT_ROW = "2020-01-01,2020,1,600000,200000,300000,5.0,1.2,BdP,PT"
_INTEREST_RATES_ROW = "2020-01-01,2020,1,0.0,-0.3,-0.2,-0.1,0.4,BdP,PT"
_INFLATION_ROW = "2020-01-01,2020,1,1.2,1.0,0.8,105.0,102.0,INE,PT"
_PUBLIC_DEBT_ROW = "2020-03-31,2020,1,260000,120.0,-3.0,48.0,BdP,PT"

_SAMPLE_ROWS = {
    "raw_gdp.csv": _GDP_ROW,
    "raw_unemployment.csv": _UNEMPLOYMENT_ROW,
    "raw_credit.csv": _CREDIT_ROW,
    "raw_interest_rates.csv": _INTEREST_RATES_ROW,
    "raw_inflation.csv": _INFLATION_ROW,
    "raw_public_debt.csv": _PUBLIC_DEBT_ROW,
}


# ── _validate_file tests ─────────────────────────────────────────────


class TestValidateFile:
    def test_valid_file(self, tmp_path):
        from src.etl.extract import _validate_file

        p = tmp_path / "data.csv"
        p.write_text("col1,col2\n1,2\n", encoding="utf-8")
        assert _validate_file(p) is True

    def test_missing_file(self, tmp_path):
        from src.etl.extract import _validate_file

        p = tmp_path / "no_such_file.csv"
        assert _validate_file(p) is False

    def test_empty_file(self, tmp_path):
        from src.etl.extract import _validate_file

        p = tmp_path / "empty.csv"
        p.write_text("", encoding="utf-8")
        assert _validate_file(p) is False


# ── extract_pillar tests ─────────────────────────────────────────────


class TestExtractPillar:
    def test_extract_valid_csv(self, tmp_path):
        from src.etl.extract import extract_pillar

        csv_content = f"{_REALISTIC_HEADERS['raw_gdp.csv']}\n{_GDP_ROW}\n"
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "raw_gdp.csv").write_text(csv_content, encoding="utf-8")

        with patch("src.etl.extract.RAW_DATA_DIR", raw_dir):
            df = extract_pillar("gdp")

        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "date" in df.columns
        assert "nominal_gdp_eur_millions" in df.columns

    def test_extract_rejects_invalid_schema(self, tmp_path):
        """CSV with wrong columns should be rejected at extract time."""
        from src.etl.extract import extract_pillar

        csv_content = "wrong_col1,wrong_col2\n1,2\n"
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "raw_gdp.csv").write_text(csv_content, encoding="utf-8")

        with patch("src.etl.extract.RAW_DATA_DIR", raw_dir):
            df = extract_pillar("gdp")

        assert df is None

    def test_extract_unknown_pillar(self):
        from src.etl.extract import extract_pillar

        assert extract_pillar("nonexistent_pillar") is None

    def test_extract_missing_csv(self, tmp_path):
        from src.etl.extract import extract_pillar

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        with patch("src.etl.extract.RAW_DATA_DIR", raw_dir):
            assert extract_pillar("gdp") is None


# ── extract_all tests ────────────────────────────────────────────────


class TestExtractAll:
    def test_extract_all_returns_dict(self, tmp_path):
        from src.etl.extract import extract_all

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for name, header in _REALISTIC_HEADERS.items():
            row = _SAMPLE_ROWS[name]
            (raw_dir / name).write_text(f"{header}\n{row}\n", encoding="utf-8")

        with patch("src.etl.extract.RAW_DATA_DIR", raw_dir):
            result = extract_all()

        assert isinstance(result, dict)
        assert len(result) == 6
        for key, df in result.items():
            assert isinstance(df, pd.DataFrame)

    def test_extract_all_partial(self, tmp_path):
        from src.etl.extract import extract_all

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        # Only GDP with valid schema; the rest are missing
        csv_content = f"{_REALISTIC_HEADERS['raw_gdp.csv']}\n{_GDP_ROW}\n"
        (raw_dir / "raw_gdp.csv").write_text(csv_content, encoding="utf-8")

        with patch("src.etl.extract.RAW_DATA_DIR", raw_dir):
            result = extract_all()

        assert "gdp" in result
        assert len(result) == 1

    def test_extract_all_rejects_bad_schema(self, tmp_path):
        """CSVs with wrong columns should be excluded from results."""
        from src.etl.extract import extract_all

        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        # Bad schema for all pillars
        for name in _REALISTIC_HEADERS:
            (raw_dir / name).write_text("bad_col\n1\n", encoding="utf-8")

        with patch("src.etl.extract.RAW_DATA_DIR", raw_dir):
            result = extract_all()

        assert len(result) == 0
