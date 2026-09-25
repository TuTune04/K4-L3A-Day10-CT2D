from __future__ import annotations

import math
import random
from typing import Any

import pandas as pd

from core.utils import now_utc, write_json
from ingestion.cleaning import refresh_derived_columns

SEED = 42
DROP_LATEST_RATIO = 0.20
BLANK_SUMMARY_ROWS = 3
NOISE_ROWS = 3
TRUNCATE_TITLE_ROWS = 3
TRUNCATED_TITLE_CHARS = 7
STALE_RATIO = 0.35
STALE_SHIFT_YEARS = 5
DUPLICATE_ROWS = 3
NOISE_TOKENS = ["#@!", "~~%", "¿¿", "0x7f", "&&*", "|||", "��"]


def _inject_noise(text: str, rng: random.Random) -> str:
    """Chen token rac sau moi 2 tu va xao tron vai ky tu - mo phong loi encoding/scraping."""
    words = text.split()
    noisy: list[str] = []
    for index, word in enumerate(words):
        if rng.random() < 0.3 and len(word) > 3:
            chars = list(word)
            rng.shuffle(chars)
            word = "".join(chars)
        noisy.append(word)
        if index % 2 == 1:
            noisy.append(rng.choice(NOISE_TOKENS))
    return " ".join(noisy)


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Tiem 6 dang loi du lieu vao ban sao cua clean dataframe va ghi corruption log.

    1. Drop 20% latest records   2. Blank summary        3. Inject noise vao summary
    4. Truncate title (< 10 ky tu) 5. Lui published 5 nam  6. Nhan ban dong
    Sau cung rebuild `text_for_embedding` de index phan anh du lieu hong.
    """
    rng = random.Random(SEED)
    corrupted = df.copy().reset_index(drop=True)
    rows_before = len(corrupted)
    events: list[dict[str, Any]] = []

    def log(kind: str, description: str, paper_ids: list[str]) -> None:
        events.append({"corruption": kind, "description": description, "affected_rows": len(paper_ids), "paper_ids": paper_ids})

    # 1. Drop latest records: mat du lieu tuoi moi nhat.
    drop_count = math.ceil(len(corrupted) * DROP_LATEST_RATIO)
    latest = corrupted.sort_values(["published", "paper_id"], ascending=[False, True]).head(drop_count)
    corrupted = corrupted.drop(index=latest.index).reset_index(drop=True)
    log("drop_latest_records", f"Dropped the {drop_count} most recently published papers ({DROP_LATEST_RATIO:.0%}).", latest["paper_id"].tolist())

    # 2-4: chon cac nhom dong khong trung nhau de moi loi tach biet ro rang trong log.
    order = list(corrupted.index)
    rng.shuffle(order)
    blank_idx = order[:BLANK_SUMMARY_ROWS]
    noise_idx = order[BLANK_SUMMARY_ROWS : BLANK_SUMMARY_ROWS + NOISE_ROWS]
    title_idx = order[BLANK_SUMMARY_ROWS + NOISE_ROWS : BLANK_SUMMARY_ROWS + NOISE_ROWS + TRUNCATE_TITLE_ROWS]

    corrupted.loc[blank_idx, "summary"] = ""
    log("blank_summary", "Summary replaced with an empty string.", corrupted.loc[blank_idx, "paper_id"].tolist())

    for idx in noise_idx:
        corrupted.at[idx, "summary"] = _inject_noise(corrupted.at[idx, "summary"], rng)
    log("inject_noise", "Garbage tokens and shuffled characters injected into the summary (propagates to text_for_embedding).", corrupted.loc[noise_idx, "paper_id"].tolist())

    corrupted.loc[title_idx, "title"] = corrupted.loc[title_idx, "title"].str[:TRUNCATED_TITLE_CHARS]
    log("truncate_title", f"Title truncated to {TRUNCATED_TITLE_CHARS} characters.", corrupted.loc[title_idx, "paper_id"].tolist())

    # 5. Stale date: lui ngay xuat ban de du lieu bi "moc".
    stale_idx = sorted(rng.sample(list(corrupted.index), math.ceil(len(corrupted) * STALE_RATIO)))
    original = pd.to_datetime(corrupted.loc[stale_idx, "published"])
    shifted = original - pd.DateOffset(years=STALE_SHIFT_YEARS)
    corrupted.loc[stale_idx, "published"] = shifted.dt.strftime("%Y-%m-%d")
    corrupted.loc[stale_idx, "age_days"] = corrupted.loc[stale_idx, "age_days"] + (original - shifted).dt.days
    log("stale_date", f"Published date shifted back {STALE_SHIFT_YEARS} years ({STALE_RATIO:.0%} of rows).", corrupted.loc[stale_idx, "paper_id"].tolist())

    # 6. Duplicate rows.
    dup_idx = sorted(rng.sample(list(corrupted.index), DUPLICATE_ROWS))
    corrupted = pd.concat([corrupted, corrupted.loc[dup_idx]], ignore_index=True)
    log("duplicate_rows", "Rows appended a second time (duplicate paper_id).", corrupted.loc[dup_idx, "paper_id"].tolist())

    # 7. Rebuild text_for_embedding tu cac cot da bi lam hong.
    corrupted = refresh_derived_columns(corrupted)

    write_json(
        output_log_path,
        {
            "generated_at": now_utc().isoformat(),
            "seed": SEED,
            "rows_before": rows_before,
            "rows_after": len(corrupted),
            "corruptions": events,
        },
    )
    return corrupted
