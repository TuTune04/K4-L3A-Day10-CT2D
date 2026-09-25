from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord, strip_markup

CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "age_days",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "abs_url",
    "pdf_url",
    "comment",
    "text_for_embedding",
]


def compose_text_for_embedding(title: str, authors_joined: str, published: str, categories_joined: str, summary: str) -> str:
    """Ghep 5 phan ngu canh chuan de dua vao embedding model."""
    return "\n".join(
        [
            f"Title: {title}",
            f"Authors: {authors_joined}",
            f"Published: {published}",
            f"Categories: {categories_joined}",
            f"Summary: {summary}",
        ]
    )


def _join(values) -> str:
    # Doc lai tu CSV thi cot list da thanh chuoi -> giu nguyen.
    return values if isinstance(values, str) else compact_join(values or [])


def refresh_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Tinh lai cac cot helper tu cac cot goc (dung chung cho cleaning va corruption)."""
    df = df.copy()
    df["summary"] = df["summary"].fillna("").astype(str)
    df["authors_joined"] = df["authors"].apply(_join)
    df["categories_joined"] = df["categories"].apply(_join)
    df["summary_chars"] = df["summary"].str.len()
    df["text_for_embedding"] = [
        compose_text_for_embedding(row.title, row.authors_joined, row.published, row.categories_joined, row.summary)
        for row in df.itertuples(index=False)
    ]
    return df


def _clean_list(values) -> list[str]:
    cleaned: list[str] = []
    for value in values or []:
        text = normalize_whitespace(str(value))
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed.

    Buoc: normalize text -> parse date -> age_days -> cot helper -> dedup theo paper_id -> filter row xau -> sort.
    """
    df = pd.DataFrame([asdict(record) for record in records])
    if df.empty:
        return pd.DataFrame(columns=CLEAN_COLUMNS)

    df["paper_id"] = df["paper_id"].fillna("").map(lambda value: normalize_whitespace(value).lower())
    df["title"] = df["title"].fillna("").map(strip_markup)
    df["summary"] = df["summary"].fillna("").map(strip_markup)
    df["authors"] = df["authors"].map(_clean_list)
    df["categories"] = df["categories"].map(_clean_list)
    df["primary_category"] = [cats[0] if cats else "Uncategorized" for cats in df["categories"]]

    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    updated = pd.to_datetime(df["updated"], errors="coerce", utc=True).fillna(published)
    run_ts = pd.Timestamp(run_date).tz_convert("UTC") if pd.Timestamp(run_date).tzinfo else pd.Timestamp(run_date, tz="UTC")

    df["published"] = published.dt.strftime("%Y-%m-%d")
    df["updated"] = updated.dt.strftime("%Y-%m-%d")
    df["age_days"] = (run_ts.normalize() - published.dt.normalize()).dt.days

    # Filter row xau: thieu khoa, tieu de, tom tat hoac ngay xuat ban khong parse duoc.
    valid = (df["paper_id"] != "") & (df["title"] != "") & (df["summary"] != "") & published.notna()
    df = df[valid].copy()

    # Dedup theo paper_id: giu ban cap nhat moi nhat.
    df = df.sort_values(["paper_id", "updated"], ascending=[True, False]).drop_duplicates("paper_id", keep="first")

    df["age_days"] = df["age_days"].astype(int)
    df = refresh_derived_columns(df)
    df = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df[CLEAN_COLUMNS]
