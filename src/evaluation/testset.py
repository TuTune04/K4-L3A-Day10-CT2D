from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json

NUM_QUESTIONS = 10
# 10 cau chia deu 5 dang (2 cau / dang), xoay vong theo thu tu duoi day.
QUESTION_TYPES = ["summary", "authors", "date", "categories", "multi_hop"]
_TITLE_PREFIX = "advanced perspectives on "


@dataclass(frozen=True)
class TestSet:
    samples: list[dict[str, Any]]
    path: Path


def _as_list(values) -> list[str]:
    if isinstance(values, str):
        return [item.strip() for item in values.split(",") if item.strip()]
    return list(values or [])


def _topic(title: str) -> str:
    # "Advanced Perspectives on X" va "X" cung mot chu de.
    lowered = title.lower()
    return lowered[len(_TITLE_PREFIX):] if lowered.startswith(_TITLE_PREFIX) else lowered


def _find_partner(row: pd.Series, candidates: pd.DataFrame) -> tuple[pd.Series, list[str]] | None:
    """Tim bai thuoc chu de KHAC nhung chia se it nhat 1 linh vuc -> cau hoi lien nganh."""
    categories = _as_list(row["categories"])
    for _, other in candidates.iterrows():
        if _topic(other["title"]) == _topic(row["title"]):
            continue
        other_categories = _as_list(other["categories"])
        shared = [category for category in categories if category in other_categories]
        # Bo cap trung het linh vuc - khong con la cau hoi ket hop 2 chu de.
        if shared and set(other_categories) != set(categories):
            return other, shared
    return None


def _make_question(question_type: str, row: pd.Series, candidates: pd.DataFrame) -> tuple[str, str, list[str]]:
    title = row["title"]
    if question_type == "summary":
        return f"What is the summary of the paper '{title}'?", first_sentence(row["summary"]), [row["paper_id"]]
    if question_type == "authors":
        return f"Who authored the paper '{title}'?", row["authors_joined"], [row["paper_id"]]
    if question_type == "date":
        return f"When was the paper '{title}' published?", row["published"], [row["paper_id"]]
    if question_type == "categories":
        return f"What categories does the paper '{title}' belong to?", row["categories_joined"], [row["paper_id"]]

    match = _find_partner(row, candidates)
    if match is None:
        raise ValueError(f"No cross-topic partner sharing a category with '{title}'.")
    partner, shared = match
    question = f"What categories do the papers '{title}' and '{partner['title']}' have in common?"
    return question, ", ".join(shared), [row["paper_id"], partner["paper_id"]]


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao bo evaluation set 10 cau (5 dang x 2) tu cleaned dataframe va ghi ra JSON.

    Chon paper trai deu tren truc thoi gian (tu moi nhat den cu nhat) de bo de
    bao phu ca nhung bai moi nhat - nhom bi anh huong khi corruption "drop latest records".
    """
    if len(df) < NUM_QUESTIONS:
        raise ValueError(f"Need at least {NUM_QUESTIONS} documents to build the test set, got {len(df)}.")

    # Tieu de co dau nhay don se pha cu phap '<title>' ma qa.py dung de exact lookup.
    candidates = df[~df["title"].str.contains("'", regex=False)]
    candidates = candidates.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    if len(candidates) < NUM_QUESTIONS:
        raise ValueError("Not enough papers with usable titles to build the test set.")

    step = (len(candidates) - 1) / (NUM_QUESTIONS - 1)
    picks = [candidates.iloc[round(i * step)] for i in range(NUM_QUESTIONS)]

    test_set: list[dict[str, Any]] = []
    for i, row in enumerate(picks):
        question_type = QUESTION_TYPES[i % len(QUESTION_TYPES)]
        question, ground_truth, doc_ids = _make_question(question_type, row, candidates)
        test_set.append(
            {
                "id": f"eval_{i + 1:03d}",
                "type": question_type,
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": doc_ids,
            }
        )

    write_json(output_path, test_set)
    return test_set


def load_or_create_test_set(df: pd.DataFrame, output_path, refresh: bool = False) -> TestSet:
    """Dung lai test set da co (giu co dinh cho ca 3 trang thai), chi sinh moi khi chua co hoac refresh=True."""
    path = Path(output_path)
    samples = build_test_set(df, path) if refresh or not path.exists() else read_json(path)
    return TestSet(samples=samples, path=path)
