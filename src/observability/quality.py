from __future__ import annotations

from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

MIN_ROWS = 5
MAX_ROWS = 5000
MIN_SUMMARY_CHARS = 30
MIN_TITLE_CHARS = 8
MAX_STALE_RATIO = 0.25
REQUIRED_COLUMNS = ["paper_id", "title", "text_for_embedding"]


def _build_expectations(settings: Settings) -> list[gxe.Expectation]:
    expectations: list[gxe.Expectation] = [
        # 1. So dong nam trong nguong hop le.
        gxe.ExpectTableRowCountToBeBetween(min_value=MIN_ROWS, max_value=MAX_ROWS),
    ]
    # 2. Cac cot quan trong khong duoc null.
    expectations += [gxe.ExpectColumnValuesToNotBeNull(column=column) for column in REQUIRED_COLUMNS]
    expectations += [
        # 3. paper_id la khoa duy nhat.
        gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
        # 4. summary du dai de AI doc hieu.
        gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=MIN_SUMMARY_CHARS),
        # Bo sung: title khong bi cat cut.
        gxe.ExpectColumnValueLengthsToBeBetween(column="title", min_value=MIN_TITLE_CHARS),
        # Bo sung: freshness SLA - it nhat 75% bai bao co age_days <= nguong.
        gxe.ExpectColumnValuesToBeBetween(
            column="age_days",
            min_value=0,
            max_value=settings.freshness_threshold_days,
            mostly=1 - MAX_STALE_RATIO,
        ),
    ]
    return expectations


def _summarize_result(result: Any) -> dict[str, Any]:
    config = result.expectation_config
    raw = result.result or {}
    return {
        "expectation": config.type,
        "column": config.kwargs.get("column"),
        "kwargs": {key: value for key, value in config.kwargs.items() if key not in {"column", "batch_id"}},
        "success": bool(result.success),
        "observed_value": raw.get("observed_value"),
        "element_count": raw.get("element_count"),
        "unexpected_count": raw.get("unexpected_count"),
        "unexpected_percent": raw.get("unexpected_percent"),
        "partial_unexpected_list": raw.get("partial_unexpected_list", [])[:5],
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay Data Quality Gate bang Great Expectations 1.x va ghi ket qua vao `data/quality/`."""
    # GX chi can cac cot scalar; bo cot list (authors/categories) de tranh loi hash khi tinh unique.
    columns = [column for column in ["paper_id", "title", "summary", "text_for_embedding", "age_days"] if column in df]
    frame = df[columns].copy()

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": frame})

    suite = context.suites.add(gx.ExpectationSuite(name=f"papers_{report_name}_suite"))
    for expectation in _build_expectations(settings):
        suite.add_expectation(expectation)

    validation = batch.validate(suite)
    results = [_summarize_result(item) for item in validation.results]
    statistics = validation.statistics or {}

    report = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "engine": f"great_expectations {gx.__version__}",
        "row_count": int(len(df)),
        "success": bool(validation.success),
        "statistics": {
            "evaluated_expectations": statistics.get("evaluated_expectations"),
            "successful_expectations": statistics.get("successful_expectations"),
            "unsuccessful_expectations": statistics.get("unsuccessful_expectations"),
            "success_percent": statistics.get("success_percent"),
        },
        "failed_expectations": [item["expectation"] + (f"[{item['column']}]" if item["column"] else "") for item in results if not item["success"]],
        "results": results,
    }
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", report)
    write_json(settings.paths.gx_dir / f"{report_name}_suite.json", suite.to_json_dict())
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop Freshness SLA: ti le bai bao co age_days > nguong khong duoc vuot 25%."""
    threshold = settings.freshness_threshold_days
    total_rows = int(len(df))
    published = pd.to_datetime(df["published"], errors="coerce") if total_rows else pd.Series(dtype="datetime64[ns]")
    stale_mask = df["age_days"] > threshold if total_rows else pd.Series(dtype=bool)
    stale_rows = int(stale_mask.sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0

    payload = {
        "generated_at": now_utc().isoformat(),
        "threshold_days": threshold,
        "max_stale_ratio": MAX_STALE_RATIO,
        "total_rows": total_rows,
        "latest_published": published.max().strftime("%Y-%m-%d") if published.notna().any() else None,
        "oldest_published": published.min().strftime("%Y-%m-%d") if published.notna().any() else None,
        "min_age_days": int(df["age_days"].min()) if total_rows else None,
        "max_age_days": int(df["age_days"].max()) if total_rows else None,
        "stale_rows": stale_rows,
        "stale_ratio": round(stale_ratio, 4),
        "stale_paper_ids": sorted(set(df.loc[stale_mask, "paper_id"])) if total_rows else [],
        "is_fresh": bool(total_rows > 0 and stale_ratio <= MAX_STALE_RATIO),
    }
    write_json(report_path, payload)
    return payload
