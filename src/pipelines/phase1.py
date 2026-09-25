from __future__ import annotations

from core.config import load_settings, normalized_provider
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def _step(message: str) -> None:
    print(f"\n==> {message}")


def main() -> None:
    """Baseline pipeline end-to-end: ingest -> clean -> quality gate -> index -> evaluate -> report."""
    settings = load_settings()
    paths = settings.paths
    run_date = now_utc()
    print(f"Run date: {run_date.isoformat()} | LLM provider: {normalized_provider(settings)}")

    _step("1. Ingestion (raw preservation)")
    records = fetch_source_records(settings)
    print(f"Loaded {len(records)} raw records -> {paths.raw_records_json}")

    _step("2. Cleaning & pre-embed modeling")
    clean_df = build_clean_dataframe(records, run_date)
    write_csv(clean_df, paths.clean_csv)
    write_json(paths.clean_json, clean_df.to_dict(orient="records"))
    print(f"Clean rows: {len(clean_df)} -> {paths.clean_csv}")

    _step("3. Data Quality Gate (GX 1.x) & Freshness SLA")
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, paths.freshness_report)
    print(f"Quality success={quality['success']} | failed={quality['failed_expectations']}")
    print(f"Freshness is_fresh={freshness['is_fresh']} | stale {freshness['stale_rows']}/{freshness['total_rows']}")
    if not quality["success"]:
        raise RuntimeError(f"Quality Gate blocked indexing: {quality['failed_expectations']}")

    _step("4. Embedding & ChromaDB index")
    index = LocalEmbeddingIndex.build(clean_df, settings, paths.embeddings_json)
    print(f"Indexed {index.collection.count()} documents into collection '{index.collection_name}'")

    _step("5. Evaluation set")
    existed = paths.test_set_json.exists() and not settings.refresh_test_set
    test_set = load_or_create_test_set(clean_df, paths.test_set_json, refresh=settings.refresh_test_set).samples
    print(f"{'Reusing' if existed else 'Built'} test set: {len(test_set)} questions -> {paths.test_set_json}"
          + (" (set REFRESH_TEST_SET=1 to rebuild)" if existed else ""))

    _step("6. Baseline evaluation")
    bundle = evaluate_pipeline(settings, index, paths.eval_testset, paths.baseline_metrics, paths.baseline_answers)
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        print(f"  {key}: {bundle.summary[key]:.4f}")

    _step("7. QA demo on sample questions")
    demo = []
    for item in test_set[:3]:
        result = answer_question(item["question"], settings=settings, index=index)
        demo.append({"question": item["question"], "answer": result.answer, "retrieved_titles": result.retrieved_titles})
        print(f"  Q: {item['question']}\n  A: {result.answer}")
    write_json(paths.demo_answers, demo)

    _step("8. Phase 1 report")
    source_summary = {
        "source_api": settings.source_api,
        "mode": "live" if settings.refresh_source else "offline snapshot",
        "query": settings.source_query,
        "filter": settings.source_filter,
        "raw_records": len(records),
        "clean_rows": len(clean_df),
        "run_date": run_date.strftime("%Y-%m-%d"),
        "embedding_model": settings.embedding_model,
        "collection": index.collection_name,
        "llm_provider": normalized_provider(settings),
        "top_k": settings.top_k,
    }
    generate_phase1_report(paths.baseline_report, source_summary, bundle.summary, quality, freshness, bundle.answers)
    print(f"Report -> {paths.baseline_report}")
