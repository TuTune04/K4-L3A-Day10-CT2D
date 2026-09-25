from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex

METRIC_KEYS = ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score")


def _step(message: str) -> None:
    print(f"\n==> {message}")


def _save_dataset(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def main() -> None:
    """Corruption -> evaluate -> repair -> evaluate -> so sanh 3 trang thai tren cung mot test set."""
    settings = load_settings()
    paths = settings.paths
    required = [paths.baseline_metrics, paths.clean_json, paths.eval_testset, paths.raw_records_json]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Run `python script/run_phase1.py` first. Missing: {missing}")

    _step("1. Load baseline artifacts")
    baseline_metrics = read_json(paths.baseline_metrics)
    baseline_answers = read_json(paths.baseline_answers)
    baseline_quality = read_json(paths.baseline_quality_report)
    baseline_freshness = read_json(paths.freshness_report)
    clean_df = pd.DataFrame(read_json(paths.clean_json))
    print(f"Baseline rows: {len(clean_df)}")

    _step("2. Inject 6 corruptions")
    corrupted_df = corrupt_clean_dataframe(clean_df, paths.corruption_log)
    _save_dataset(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    corruption_log = read_json(paths.corruption_log)
    for event in corruption_log["corruptions"]:
        print(f"  {event['corruption']}: {event['affected_rows']} rows")

    _step("3. Observability on corrupted data (audit mode - gate reports but does not block)")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(corrupted_df, settings, paths.quality_dir / "freshness_report_corrupted.json")
    print(f"  Quality success={corrupted_quality['success']} | failed={corrupted_quality['failed_expectations']}")
    print(f"  Freshness is_fresh={corrupted_freshness['is_fresh']} | stale ratio={corrupted_freshness['stale_ratio']}")

    _step("4. Re-index & evaluate corrupted data")
    corrupted_index = LocalEmbeddingIndex.build(corrupted_df, settings, paths.corrupted_embeddings_json)
    corrupted = evaluate_pipeline(settings, corrupted_index, paths.eval_testset, paths.corrupted_metrics, paths.corrupted_answers)

    _step("5. Idempotent repair from raw snapshot")
    # Khong va lai bang hong: tai tao tu raw records + cung run_date logic -> ket qua xac dinh.
    repaired_df = build_clean_dataframe(load_raw_records(paths.raw_records_json), now_utc())
    _save_dataset(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)
    same_as_baseline = repaired_df["paper_id"].tolist() == clean_df["paper_id"].tolist() and (
        repaired_df["text_for_embedding"].tolist() == clean_df["text_for_embedding"].tolist()
    )
    print(f"  Repaired rows: {len(repaired_df)} | identical to baseline content: {same_as_baseline}")

    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(repaired_df, settings, paths.quality_dir / "freshness_report_repaired.json")
    if not repaired_quality["success"]:
        raise RuntimeError(f"Repair failed the Quality Gate: {repaired_quality['failed_expectations']}")

    _step("6. Re-index & evaluate repaired data")
    repaired_index = LocalEmbeddingIndex.build(repaired_df, settings, paths.repaired_embeddings_json)
    repaired = evaluate_pipeline(settings, repaired_index, paths.eval_testset, paths.repaired_metrics, paths.repaired_answers)

    _step("7. Comparison (same test set)")
    print(f"  {'metric':<22}{'baseline':>10}{'corrupted':>11}{'repaired':>10}")
    for key in METRIC_KEYS:
        print(f"  {key:<22}{baseline_metrics[key]:>10.4f}{corrupted.summary[key]:>11.4f}{repaired.summary[key]:>10.4f}")

    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted.summary,
        repaired.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
        corruption_log=corruption_log,
        answers_by_state={"baseline": baseline_answers, "corrupted": corrupted.answers, "repaired": repaired.answers},
        baseline_quality=baseline_quality,
        baseline_freshness=baseline_freshness,
    )
    print(f"\nReport -> {paths.comparison_report}")
