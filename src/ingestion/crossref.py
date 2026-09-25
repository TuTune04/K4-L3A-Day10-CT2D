from __future__ import annotations

from dataclasses import asdict, dataclass
import html
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 4
REQUEST_TIMEOUT_SECONDS = 30

_TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def strip_markup(value: str) -> str:
    """Bo cac tag JATS/HTML (vd `<jats:p>`) va decode HTML entities."""
    return normalize_whitespace(html.unescape(_TAG_PATTERN.sub(" ", value or "")))


def _first(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _date_from_parts(block: dict | None) -> str:
    """Crossref date: {"date-parts": [[YYYY, MM, DD]]} -> "YYYY-MM-DD" (thieu thang/ngay thi = 01)."""
    if not block:
        return ""
    parts = (block.get("date-parts") or [[]])[0]
    if parts and parts[0]:
        year, month, day = (list(parts) + [1, 1])[:3]
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    date_time = block.get("date-time")
    return date_time[:10] if date_time else ""


def _author_name(author: dict) -> str:
    name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
    return normalize_whitespace(name or author.get("name", ""))


def _pdf_url(item: dict, fallback: str) -> str:
    for link in item.get("link") or []:
        if "pdf" in (link.get("content-type") or "").lower() and link.get("URL"):
            return link["URL"]
    return fallback


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref `/works` payload thanh list PaperRecord, bo record thieu DOI/title/abstract."""
    records: list[PaperRecord] = []
    seen: set[str] = set()
    for item in payload.get("message", {}).get("items", []):
        paper_id = normalize_whitespace(item.get("DOI", "")).lower()
        title = strip_markup(_first(item.get("title")))
        summary = strip_markup(item.get("abstract", ""))
        if not paper_id or not title or not summary or paper_id in seen:
            continue
        seen.add(paper_id)

        authors = [name for name in (_author_name(author) for author in item.get("author") or []) if name]
        categories = [normalize_whitespace(subject) for subject in item.get("subject") or [] if subject]
        published = (
            _date_from_parts(item.get("published"))
            or _date_from_parts(item.get("published-print"))
            or _date_from_parts(item.get("published-online"))
            or _date_from_parts(item.get("created"))
        )
        updated = _date_from_parts(item.get("updated")) or _date_from_parts(item.get("created")) or published
        abs_url = item.get("URL") or f"https://doi.org/{paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "Uncategorized",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=_pdf_url(item, abs_url),
                comment=f"Crossref record {paper_id}",
            )
        )
    return records


def _request_crossref(settings: Settings) -> dict:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "sort": "published",
        "order": "desc",
    }
    headers = {"User-Agent": "day10-data-observability-lab/0.1 (mailto:student@example.com)"}
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(CROSSREF_WORKS_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise requests.HTTPError(f"Crossref returned {response.status_code}", response=response)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            retry_after = getattr(getattr(exc, "response", None), "headers", {}).get("Retry-After")
            wait = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
            print(f"[ingestion] Crossref attempt {attempt + 1}/{MAX_RETRIES} failed: {exc}. Retry in {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"Crossref API unavailable after {MAX_RETRIES} attempts: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Lay records tu Crossref (live khi REFRESH_SOURCE=1) hoac snapshot offline, luu raw artifacts.

    - Live mode: goi API co retry 429/503, ghi de raw response snapshot.
    - Offline mode / API loi: doc `data/raw/crossref_response.json` co san.
    Trong ca 2 truong hop deu ghi lai `crossref_records.json` de giu lineage.
    """
    paths = settings.paths
    payload: dict | None = None

    if settings.refresh_source:
        try:
            payload = _request_crossref(settings)
            write_json(paths.raw_api_response, payload)
            print(f"[ingestion] Live mode: saved raw Crossref response -> {paths.raw_api_response}")
        except RuntimeError as exc:
            print(f"[ingestion] {exc}. Falling back to offline snapshot.")

    if payload is None:
        if not paths.raw_api_response.exists():
            raise FileNotFoundError(
                f"No offline snapshot at {paths.raw_api_response}. Set REFRESH_SOURCE=1 to fetch from Crossref."
            )
        payload = read_json(paths.raw_api_response)
        print(f"[ingestion] Offline mode: loaded snapshot {paths.raw_api_response}")

    records = parse_crossref_payload(payload)
    write_json(paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot `crossref_records.json` va map thanh `PaperRecord`."""
    fields = PaperRecord.__dataclass_fields__.keys()
    return [PaperRecord(**{key: row.get(key) for key in fields}) for row in read_json(Path(path))]
