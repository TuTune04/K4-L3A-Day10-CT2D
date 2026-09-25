from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from core.config import load_settings
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records

PROJECT_DIR = Path(__file__).resolve().parents[1]
RUN_DATE = datetime(2026, 9, 25, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    # Test khong goi LLM that: judge dung heuristic, khong ton phi API.
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock")
    monkeypatch.delenv("REFRESH_SOURCE", raising=False)
    monkeypatch.delenv("REFRESH_TEST_SET", raising=False)
    monkeypatch.delenv("RUN_RAGAS", raising=False)


@pytest.fixture
def project(tmp_path) -> Path:
    """Project tam chi co raw snapshot - moi test chay co lap, khong dung vao data/ that."""
    raw_dir = tmp_path / "project" / "data" / "raw"
    raw_dir.mkdir(parents=True)
    for name in ("crossref_response.json", "crossref_records.json"):
        shutil.copy(PROJECT_DIR / "data" / "raw" / name, raw_dir / name)
    return tmp_path / "project"


@pytest.fixture
def settings(project):
    return load_settings(project)


@pytest.fixture
def clean_df(settings) -> pd.DataFrame:
    return build_clean_dataframe(load_raw_records(settings.paths.raw_records_json), RUN_DATE)
