from __future__ import annotations

import pytest

from core.utils import read_json, write_json
from ingestion.corruption import corrupt_clean_dataframe
from observability.dashboard import build_dashboard, detect_drift
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report, generate_phase1_report

METRICS = {"retrieval_hit_rate": 1.0, "mean_token_f1": 1.0, "judge_accuracy": 1.0, "mean_judge_score": 5, "samples": 10}
BAD_METRICS = {"retrieval_hit_rate": 0.8, "mean_token_f1": 0.7, "judge_accuracy": 0.5, "mean_judge_score": 3.7, "samples": 10}


@pytest.fixture
def corrupted_df(clean_df, settings):
    return corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)


# ---------- Great Expectations 1.x ----------

def test_quality_gate_passes_on_clean_data(clean_df, settings):
    report = run_data_quality_checks(clean_df, settings, "baseline")
    assert report["success"] is True and report["failed_expectations"] == []
    assert report["statistics"]["evaluated_expectations"] == 8
    assert report["engine"].startswith("great_expectations 1.")
    assert (settings.paths.quality_dir / "baseline_quality_report.json").exists()
    assert (settings.paths.gx_dir / "baseline_suite.json").exists()


def test_quality_gate_catches_corruptions(corrupted_df, settings):
    report = run_data_quality_checks(corrupted_df, settings, "corrupted")
    assert report["success"] is False
    assert set(report["failed_expectations"]) == {
        "expect_column_values_to_be_unique[paper_id]",
        "expect_column_value_lengths_to_be_between[title]",
        "expect_column_value_lengths_to_be_between[summary]",
        "expect_column_values_to_be_between[age_days]",
    }


def test_quality_gate_fails_on_too_few_rows(clean_df, settings):
    assert run_data_quality_checks(clean_df.head(3), settings, "tiny")["failed_expectations"] == [
        "expect_table_row_count_to_be_between"
    ]


# ---------- Freshness SLA ----------

def test_freshness_fresh_and_stale(clean_df, corrupted_df, settings, tmp_path):
    fresh = build_freshness_report(clean_df, settings, tmp_path / "fresh.json")
    assert fresh["is_fresh"] is True and fresh["stale_rows"] == 1
    assert fresh["latest_published"] == "2026-07-22" and read_json(tmp_path / "fresh.json") == fresh

    stale = build_freshness_report(corrupted_df, settings, tmp_path / "stale.json")
    assert stale["is_fresh"] is False and stale["stale_ratio"] > 0.25


def test_freshness_empty_dataset(clean_df, settings, tmp_path):
    report = build_freshness_report(clean_df.head(0), settings, tmp_path / "empty.json")
    assert report["is_fresh"] is False and report["total_rows"] == 0 and report["latest_published"] is None


# ---------- Markdown reports ----------

def _answers(state_hits: list[bool]):
    return [{"id": f"eval_{i:03d}", "question_type": "summary", "retrieval_hit": hit, "token_f1": 1.0 if hit else 0.2,
             "answer": "text"} for i, hit in enumerate(state_hits)]


def test_phase1_report(clean_df, settings, tmp_path):
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, tmp_path / "f.json")
    path = tmp_path / "phase1.md"
    generate_phase1_report(path, {"source_api": "Crossref"}, METRICS, quality, freshness, _answers([True, True]))
    text = path.read_text(encoding="utf-8")
    assert "Retrieval Hit Rate | 1.0000" in text and "Breakdown by question type" in text and "PASS" in text


def test_corruption_report(clean_df, corrupted_df, settings, tmp_path):
    base_q = run_data_quality_checks(clean_df, settings, "baseline")
    bad_q = run_data_quality_checks(corrupted_df, settings, "corrupted")
    base_f = build_freshness_report(clean_df, settings, tmp_path / "b.json")
    bad_f = build_freshness_report(corrupted_df, settings, tmp_path / "c.json")
    path = tmp_path / "corruption.md"
    generate_corruption_report(
        path, METRICS, BAD_METRICS, METRICS, bad_q, base_q, bad_f, base_f,
        corruption_log=read_json(settings.paths.corruption_log),
        answers_by_state={"baseline": _answers([True, True]), "corrupted": _answers([True, False]), "repaired": _answers([True, True])},
        baseline_quality=base_q, baseline_freshness=base_f,
    )
    text = path.read_text(encoding="utf-8")
    assert "| Retrieval Hit Rate | 1.0000 | 0.8000 | 1.0000 | -0.2000 | +0.0000 |" in text
    assert "drop_latest_records" in text and "Questions that regressed" in text
    assert "fully recovered" in text and "Silent failure" in text


# ---------- Dashboard & drift ----------

def test_dashboard_renders_all_sections(clean_df, corrupted_df, settings):
    paths = settings.paths
    write_json(paths.baseline_metrics, METRICS)
    write_json(paths.corrupted_metrics, BAD_METRICS)
    write_json(paths.repaired_metrics, METRICS)
    write_json(paths.clean_json, clean_df.to_dict(orient="records"))
    write_json(paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    write_json(paths.repaired_clean_json, clean_df.to_dict(orient="records"))
    run_data_quality_checks(clean_df, settings, "baseline")
    run_data_quality_checks(corrupted_df, settings, "corrupted")
    run_data_quality_checks(clean_df, settings, "repaired")
    build_freshness_report(clean_df, settings, paths.freshness_report)
    build_freshness_report(corrupted_df, settings, paths.quality_dir / "freshness_report_corrupted.json")
    build_freshness_report(clean_df, settings, paths.quality_dir / "freshness_report_repaired.json")
    write_json(paths.self_heal_log, {"runs": [{"timestamp": "2026-09-25T00:00:00", "dataset": "corrupted", "triggered": True,
                                               "strategy": "rollback_to_raw_snapshot", "rows_before": 22, "rows_after": 24,
                                               "healthy_after": True}]})

    html = build_dashboard(settings).read_text(encoding="utf-8")
    for fragment in ("Data Observability Dashboard", "Quality Gate FAIL", "Vùng stale", "rollback_to_raw_snapshot",
                     "expect_column_values_to_be_unique", "drop_latest_records", "<svg"):
        assert fragment in html


def test_dashboard_without_artifacts(settings):
    html = build_dashboard(settings).read_text(encoding="utf-8")
    assert "Chưa có metrics" in html and "Không phát hiện drift" in html


def test_detect_drift_flags_row_and_freshness_changes():
    data = {
        "quality": {"baseline": {"success": True, "row_count": 24}, "corrupted": {"success": True, "row_count": 20}, "repaired": None},
        "freshness": {"baseline": {"latest_published": "2026-07-22", "is_fresh": True},
                      "corrupted": {"latest_published": "2026-06-12", "is_fresh": True}, "repaired": None},
    }
    severities = [alert["severity"] for alert in detect_drift(data)]
    assert severities == ["serious", "warning"]
