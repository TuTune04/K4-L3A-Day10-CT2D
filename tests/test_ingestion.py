from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest
import requests

from core.utils import read_json
from ingestion import crossref
from ingestion.cleaning import CLEAN_COLUMNS, build_clean_dataframe, refresh_derived_columns
from ingestion.crossref import PaperRecord, fetch_source_records, load_raw_records, parse_crossref_payload

from conftest import RUN_DATE


def _item(**overrides):
    item = {
        "DOI": "10.1/ABC",
        "title": ["  A <i>Title</i>  "],
        "abstract": "<jats:p>Summary &amp; more   text.</jats:p>",
        "author": [{"given": "Minh", "family": "Nguyen"}, {"name": "Org Team"}, {}],
        "subject": ["AI", "IR"],
        "published": {"date-parts": [[2026, 5]]},
        "URL": "https://doi.org/10.1/abc",
        "link": [{"content-type": "application/pdf", "URL": "https://x/paper.pdf"}],
    }
    item.update(overrides)
    return item


# ---------- parse_crossref_payload ----------

def test_parse_normalizes_fields():
    [record] = parse_crossref_payload({"message": {"items": [_item()]}})
    assert record.paper_id == "10.1/abc"
    assert record.title == "A Title"
    assert record.summary == "Summary & more text."
    assert record.authors == ["Minh Nguyen", "Org Team"]
    assert record.categories == ["AI", "IR"] and record.primary_category == "AI"
    assert record.published == "2026-05-01"  # thieu ngay -> 01
    assert record.pdf_url == "https://x/paper.pdf"


def test_parse_skips_invalid_and_duplicate_records():
    payload = {"message": {"items": [
        _item(),
        _item(),  # trung DOI
        _item(DOI="10.1/no-title", title=[]),
        _item(DOI="10.1/no-abstract", abstract=""),
        _item(DOI=""),
    ]}}
    assert [record.paper_id for record in parse_crossref_payload(payload)] == ["10.1/abc"]


def test_parse_date_fallbacks_and_defaults():
    item = _item(published=None, subject=None, link=None, URL=None)
    item["published-online"] = {"date-parts": [[2025, 12, 3]]}
    [record] = parse_crossref_payload({"message": {"items": [item]}})
    assert record.published == "2025-12-03"
    assert record.primary_category == "Uncategorized"
    assert record.abs_url == record.pdf_url == "https://doi.org/10.1/abc"

    item = _item(published=None)
    item["created"] = {"date-parts": [[None]], "date-time": "2024-02-29T10:00:00Z"}
    assert parse_crossref_payload({"message": {"items": [item]}})[0].published == "2024-02-29"


# ---------- fetch_source_records / load_raw_records ----------

def test_fetch_offline_uses_snapshot_and_writes_records(settings):
    settings.paths.raw_records_json.unlink()
    records = fetch_source_records(settings)
    assert len(records) == 24
    assert len(read_json(settings.paths.raw_records_json)) == 24


def test_fetch_offline_without_snapshot_raises(settings):
    settings.paths.raw_api_response.unlink()
    with pytest.raises(FileNotFoundError):
        fetch_source_records(settings)


class _Response:
    def __init__(self, status: int, payload: dict | None = None, headers: dict | None = None):
        self.status_code, self._payload, self.headers = status, payload or {}, headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)

    def json(self):
        return self._payload


def test_fetch_live_retries_then_saves_response(settings, monkeypatch):
    payload = {"message": {"items": [_item()]}}
    responses = iter([_Response(429, headers={"Retry-After": "1"}), _Response(503), _Response(200, payload)])
    sleeps: list[float] = []
    monkeypatch.setattr(crossref.requests, "get", lambda *a, **k: next(responses))
    monkeypatch.setattr(crossref.time, "sleep", sleeps.append)

    records = fetch_source_records(replace(settings, refresh_source=True))
    assert [record.paper_id for record in records] == ["10.1/abc"]
    assert sleeps == [1.0, 2]  # Retry-After roi backoff 2^1
    assert read_json(settings.paths.raw_api_response) == payload


def test_fetch_live_falls_back_to_snapshot_when_api_down(settings, monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(crossref.requests, "get", boom)
    monkeypatch.setattr(crossref.time, "sleep", lambda _: None)
    assert len(fetch_source_records(replace(settings, refresh_source=True))) == 24


def test_load_raw_records_roundtrip(settings):
    records = load_raw_records(settings.paths.raw_records_json)
    assert len(records) == 24 and isinstance(records[0], PaperRecord)


# ---------- cleaning ----------

def test_clean_dataframe_schema_and_values(clean_df):
    assert list(clean_df.columns) == CLEAN_COLUMNS
    assert len(clean_df) == 24 and clean_df["paper_id"].is_unique
    assert not clean_df["summary"].str.contains("<jats", regex=False).any()
    assert clean_df["published"].is_monotonic_decreasing
    row = clean_df[clean_df["paper_id"] == "10.1145/3637528.3671801"].iloc[0]
    assert row["age_days"] == (pd.Timestamp("2026-09-25") - pd.Timestamp("2026-05-20")).days
    assert row["text_for_embedding"].splitlines()[0].startswith("Title: ")
    assert [line.split(":")[0] for line in row["text_for_embedding"].splitlines()] == ["Title", "Authors", "Published", "Categories", "Summary"]


def test_clean_dedups_keeping_latest_update_and_filters_bad_rows():
    base = dict(title="T", summary="S", authors=["A", "A", " "], categories=["C"], primary_category="C",
                abs_url="u", pdf_url="u", comment="")
    records = [
        PaperRecord(paper_id="10.1/X", published="2026-01-01", updated="2026-01-01", **{**base, "title": "old"}),
        PaperRecord(paper_id="10.1/x", published="2026-01-01", updated="2026-02-01", **{**base, "title": "new"}),
        PaperRecord(paper_id="10.1/bad-date", published="not a date", updated="", **base),
        PaperRecord(paper_id="10.1/empty", published="2026-01-01", updated="2026-01-01", **{**base, "summary": ""}),
    ]
    df = build_clean_dataframe(records, RUN_DATE)
    assert df["paper_id"].tolist() == ["10.1/x"]
    assert df.iloc[0]["title"] == "new" and df.iloc[0]["authors"] == ["A"]


def test_clean_empty_and_naive_run_date():
    assert build_clean_dataframe([], RUN_DATE).columns.tolist() == CLEAN_COLUMNS
    record = PaperRecord("10.1/a", "T", "S", [], [], "", "2026-09-20", "", "u", "u", "")
    df = build_clean_dataframe([record], RUN_DATE.replace(tzinfo=None))
    assert df.iloc[0]["age_days"] == 5 and df.iloc[0]["primary_category"] == "Uncategorized"


def test_refresh_derived_columns_handles_csv_strings(clean_df, tmp_path):
    path = tmp_path / "clean.csv"
    clean_df.to_csv(path, index=False)
    reloaded = refresh_derived_columns(pd.read_csv(path))
    # Doc tu CSV cot list thanh chuoi -> giu nguyen, khong bi tach thanh tung ky tu.
    assert reloaded["authors_joined"].tolist() == pd.read_csv(path)["authors"].astype(str).tolist()
