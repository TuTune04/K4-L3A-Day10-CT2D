from __future__ import annotations

from collections import defaultdict
from typing import Any

from core.utils import now_utc, write_text

METRIC_LABELS = [
    ("retrieval_hit_rate", "Retrieval Hit Rate"),
    ("mean_token_f1", "Mean Token F1"),
    ("judge_accuracy", "LLM Judge Accuracy"),
    ("mean_judge_score", "Mean Judge Score (1-5)"),
]


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return "-"
    return str(value)


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    lines += ["| " + " | ".join(_fmt(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def _quality_rows(quality: dict[str, Any]) -> list[list[Any]]:
    rows = []
    for item in quality.get("results", []):
        detail = item.get("observed_value")
        if detail is None and item.get("unexpected_count") is not None:
            detail = f"{item['unexpected_count']} unexpected / {item.get('element_count')}"
        rows.append([item["expectation"], item.get("column") or "(table)", detail, item["success"]])
    return rows


def _freshness_rows(freshness: dict[str, Any]) -> list[list[Any]]:
    keys = ["total_rows", "latest_published", "oldest_published", "stale_rows", "stale_ratio", "threshold_days", "is_fresh"]
    return [[key, freshness.get(key)] for key in keys]


def _per_type_hit_rate(answers: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in answers:
        grouped[item["question_type"]].append(item)
    return {
        question_type: (
            sum(1.0 for item in items if item["retrieval_hit"]) / len(items),
            sum(item["token_f1"] for item in items) / len(items),
        )
        for question_type, items in sorted(grouped.items())
    }


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
    answers: list[dict[str, Any]] | None = None,
) -> None:
    """Viet markdown report cho baseline phase tu artifact thuc te."""
    sections = [
        "# Phase 1 Report - Baseline Pipeline",
        f"_Generated at {now_utc().isoformat()} by `script/run_phase1.py`._",
        "## 1. Source & Lineage",
        _table(["Field", "Value"], [[key, value] for key, value in source_summary.items()]),
        "## 2. Retrieval & Answer Quality (Baseline)",
        _table(["Metric", "Value"], [[label, metrics.get(key)] for key, label in METRIC_LABELS] + [["Samples", metrics.get("samples")]]),
    ]
    if answers:
        per_type = _per_type_hit_rate(answers)
        sections += [
            "### Breakdown by question type",
            _table(["Question type", "Hit Rate", "Mean Token F1"], [[name, hit, f1] for name, (hit, f1) in per_type.items()]),
        ]
    sections += [
        "## 3. Data Quality Gate (Great Expectations 1.x)",
        f"Overall: **{_fmt(quality.get('success'))}** - "
        f"{quality.get('statistics', {}).get('successful_expectations')}/{quality.get('statistics', {}).get('evaluated_expectations')} expectations passed "
        f"({quality.get('engine')}).",
        _table(["Expectation", "Column", "Observed", "Result"], _quality_rows(quality)),
        "## 4. Freshness SLA",
        f"Rule: stale = `age_days > {freshness.get('threshold_days')}`; the dataset is fresh when stale ratio <= {freshness.get('max_stale_ratio')}.",
        _table(["Field", "Value"], _freshness_rows(freshness)),
    ]
    write_text(report_path, "\n\n".join(sections) + "\n")


def _delta(after: Any, before: Any) -> str:
    if isinstance(after, (int, float)) and isinstance(before, (int, float)):
        return f"{after - before:+.4f}"
    return "-"


def _analysis(baseline: dict, corrupted: dict, repaired: dict, corrupted_quality: dict, repaired_quality: dict,
              corrupted_freshness: dict, repaired_freshness: dict) -> list[str]:
    lines = []
    for key, label in METRIC_LABELS:
        base, bad, fixed = baseline.get(key), corrupted.get(key), repaired.get(key)
        if not all(isinstance(value, (int, float)) for value in (base, bad, fixed)):
            continue
        recovered = "fully recovered" if abs(fixed - base) < 1e-9 else f"recovered to {fixed:.4f} ({fixed - base:+.4f} vs baseline)"
        lines.append(f"- **{label}**: baseline {base:.4f} -> corrupted {bad:.4f} ({bad - base:+.4f}) -> repaired {fixed:.4f}; {recovered}.")

    failed = corrupted_quality.get("failed_expectations", [])
    lines.append(
        f"- **Quality Gate** on corrupted data: {_fmt(corrupted_quality.get('success'))} "
        f"({len(failed)} failed: {', '.join(failed) or 'none'}). After repair: {_fmt(repaired_quality.get('success'))}."
    )
    lines.append(
        f"- **Freshness SLA**: corrupted stale ratio {corrupted_freshness.get('stale_ratio')} "
        f"(is_fresh={corrupted_freshness.get('is_fresh')}, latest={corrupted_freshness.get('latest_published')}) vs repaired "
        f"{repaired_freshness.get('stale_ratio')} (is_fresh={repaired_freshness.get('is_fresh')}, latest={repaired_freshness.get('latest_published')})."
    )
    if corrupted_quality.get("success") is False:
        lines.append(
            "- **Silent failure**: the RAG layer raised no error on the corrupted index and still answered every question; "
            "only the Quality Gate and freshness monitor surfaced the problem. In production the gate must block indexing "
            "(Phase 1 does this) - here it runs in audit mode so the degradation can be measured."
        )
    return lines


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    corruption_log: dict[str, Any] | None = None,
    answers_by_state: dict[str, list[dict[str, Any]]] | None = None,
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
) -> None:
    """Viet markdown report so sanh 3 trang thai baseline/corrupted/repaired."""
    metric_rows = [
        [label, baseline_metrics.get(key), corrupted_metrics.get(key), repaired_metrics.get(key),
         _delta(corrupted_metrics.get(key), baseline_metrics.get(key)), _delta(repaired_metrics.get(key), baseline_metrics.get(key))]
        for key, label in METRIC_LABELS
    ]
    baseline_quality = baseline_quality or {}
    baseline_freshness = baseline_freshness or {}
    signal_rows = [
        ["Row count", baseline_quality.get("row_count"), corrupted_quality.get("row_count"), repaired_quality.get("row_count")],
        ["Quality Gate (GX)", baseline_quality.get("success"), corrupted_quality.get("success"), repaired_quality.get("success")],
        ["Failed expectations", len(baseline_quality.get("failed_expectations", [])) if baseline_quality else None,
         len(corrupted_quality.get("failed_expectations", [])), len(repaired_quality.get("failed_expectations", []))],
        ["Latest published", baseline_freshness.get("latest_published"), corrupted_freshness.get("latest_published"), repaired_freshness.get("latest_published")],
        ["Stale ratio", baseline_freshness.get("stale_ratio"), corrupted_freshness.get("stale_ratio"), repaired_freshness.get("stale_ratio")],
        ["Freshness is_fresh", baseline_freshness.get("is_fresh"), corrupted_freshness.get("is_fresh"), repaired_freshness.get("is_fresh")],
    ]

    sections = [
        "# Corruption Report - Baseline vs Corrupted vs Repaired",
        f"_Generated at {now_utc().isoformat()} by `script/run_corruption_flow.py`. All three states are evaluated on the same test set._",
        "## 1. RAG Metrics (3 states)",
        _table(["Metric", "Baseline", "Corrupted", "Repaired", "Delta corrupted", "Delta repaired"], metric_rows),
        "## 2. Observability Signals",
        _table(["Signal", "Baseline", "Corrupted", "Repaired"], signal_rows),
    ]

    if corruption_log:
        sections += [
            "## 3. Injected Corruptions",
            f"Seed `{corruption_log.get('seed')}` - rows {corruption_log.get('rows_before')} -> {corruption_log.get('rows_after')}.",
            _table(["Corruption", "Rows", "Description"],
                   [[event["corruption"], event["affected_rows"], event["description"]] for event in corruption_log.get("corruptions", [])]),
        ]

    if answers_by_state:
        per_state = {state: _per_type_hit_rate(answers) for state, answers in answers_by_state.items()}
        types = sorted({name for values in per_state.values() for name in values})
        sections += [
            "## 4. Impact by Question Type (Hit Rate / Token F1)",
            _table(["Question type", *answers_by_state.keys()],
                   [[name, *(f"{per_state[state][name][0]:.2f} / {per_state[state][name][1]:.2f}" if name in per_state[state] else "-"
                             for state in answers_by_state)] for name in types]),
        ]
        baseline_answers = {item["id"]: item for item in answers_by_state.get("baseline", [])}
        regressions = [
            [item["id"], item["question_type"], baseline_answers[item["id"]]["token_f1"], item["token_f1"], item["retrieval_hit"], item["answer"][:80]]
            for item in answers_by_state.get("corrupted", [])
            if item["id"] in baseline_answers and item["token_f1"] < baseline_answers[item["id"]]["token_f1"]
        ]
        if regressions:
            sections += [
                "### Questions that regressed on corrupted data",
                _table(["ID", "Type", "Baseline F1", "Corrupted F1", "Corrupted hit", "Corrupted answer (truncated)"], regressions),
            ]

    sections += [
        "## 5. Analysis",
        "\n".join(_analysis(baseline_metrics, corrupted_metrics, repaired_metrics, corrupted_quality, repaired_quality,
                            corrupted_freshness, repaired_freshness)),
        "## 6. Repair Strategy",
        "Repair is triggered automatically by `pipelines/self_heal.py` when the Quality Gate or the Freshness SLA fails "
        "(decisions logged in `data/results/self_heal_log.json`). It does not patch the corrupted table: it first rolls "
        "back to the preserved raw snapshot (`data/raw/crossref_records.json`) and re-runs the deterministic cleaning step, "
        "and only re-fetches from Crossref if the dataset is still unhealthy. The result is re-validated and indexed into a "
        "fresh Chroma collection (`papers-repaired`). Because input and transformation are deterministic, running repair any "
        "number of times yields the same clean dataset (idempotent), with no manual edits.",
    ]
    write_text(report_path, "\n\n".join(sections) + "\n")
