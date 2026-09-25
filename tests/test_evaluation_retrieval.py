from __future__ import annotations

from collections import Counter

import pandas as pd
import pytest

from core.utils import read_json, write_json
from evaluation.metrics import _token_f1, evaluate_pipeline
from evaluation.testset import QUESTION_TYPES, build_test_set, load_or_create_test_set
from ingestion.corruption import corrupt_clean_dataframe
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


# ---------- test set ----------

def test_test_set_has_10_questions_5_types(clean_df, settings):
    test_set = build_test_set(clean_df, settings.paths.test_set_json)
    assert len(test_set) == 10
    assert Counter(item["type"] for item in test_set) == {question_type: 2 for question_type in QUESTION_TYPES}
    required = {"id", "type", "question_type", "question", "ground_truth", "ground_truth_doc_ids"}
    assert all(required <= item.keys() for item in test_set)
    assert read_json(settings.paths.test_set_json) == test_set


def test_multi_hop_pairs_two_cross_topic_papers(clean_df, settings):
    by_id = clean_df.set_index("paper_id")
    for item in (q for q in build_test_set(clean_df, settings.paths.test_set_json) if q["type"] == "multi_hop"):
        first, second = item["ground_truth_doc_ids"]
        shared = set(by_id.loc[first, "categories"]) & set(by_id.loc[second, "categories"])
        assert shared and item["ground_truth"].split(", ")[0] in shared
        assert set(by_id.loc[first, "categories"]) != set(by_id.loc[second, "categories"])


def test_test_set_requires_enough_documents(clean_df, tmp_path):
    with pytest.raises(ValueError):
        build_test_set(clean_df.head(5), tmp_path / "t.json")
    quoted = clean_df.copy()
    quoted.loc[:20, "title"] = quoted.loc[:20, "title"] + "'s"
    with pytest.raises(ValueError):
        build_test_set(quoted, tmp_path / "t.json")


def test_multi_hop_without_partner_raises(clean_df, tmp_path):
    lonely = clean_df.copy()
    lonely["categories"] = [[f"Unique {i}"] for i in range(len(lonely))]
    with pytest.raises(ValueError):
        build_test_set(lonely, tmp_path / "t.json")


def test_load_or_create_reuses_existing_file(clean_df, settings):
    path = settings.paths.test_set_json
    first = load_or_create_test_set(clean_df, path)
    write_json(path, first.samples[:3])
    assert len(load_or_create_test_set(clean_df, path).samples) == 3
    assert len(load_or_create_test_set(clean_df, path, refresh=True).samples) == 10


# ---------- corruption ----------

def test_corruption_is_deterministic_and_logged(clean_df, settings, tmp_path):
    first = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    second = corrupt_clean_dataframe(clean_df, tmp_path / "log2.json")
    pd.testing.assert_frame_equal(first, second)

    log = read_json(settings.paths.corruption_log)
    assert [event["corruption"] for event in log["corruptions"]] == [
        "drop_latest_records", "blank_summary", "inject_noise", "truncate_title", "stale_date", "duplicate_rows"]
    assert log["rows_before"] == 24 and log["rows_after"] == len(first) == 22


def test_corruption_effects(clean_df, settings):
    corrupted = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    events = {event["corruption"]: event for event in read_json(settings.paths.corruption_log)["corruptions"]}
    assert not set(events["drop_latest_records"]["paper_ids"]) & set(corrupted["paper_id"])
    assert (corrupted["summary"] == "").sum() >= 3
    assert (corrupted["title"].str.len() < 10).sum() >= 3
    assert corrupted["paper_id"].duplicated().sum() == 3
    stale = corrupted[corrupted["paper_id"].isin(events["stale_date"]["paper_ids"])]
    assert (stale["age_days"] > 5 * 365).all()
    noisy = corrupted[corrupted["paper_id"].isin(events["inject_noise"]["paper_ids"])]
    assert noisy["text_for_embedding"].str.contains(r"#@!|~~%|0x7f|&&\*|\|\|\||¿¿|�", regex=True).all()
    assert len(clean_df) == 24  # khong sua df goc


# ---------- retrieval & QA ----------

@pytest.fixture(scope="module")
def built_index(tmp_path_factory):
    from core.config import load_settings
    from ingestion.cleaning import build_clean_dataframe
    from ingestion.crossref import load_raw_records
    import shutil
    from conftest import PROJECT_DIR, RUN_DATE

    project = tmp_path_factory.mktemp("idx") / "project"
    (project / "data" / "raw").mkdir(parents=True)
    for name in ("crossref_response.json", "crossref_records.json"):
        shutil.copy(PROJECT_DIR / "data" / "raw" / name, project / "data" / "raw" / name)
    settings = load_settings(project)
    df = build_clean_dataframe(load_raw_records(settings.paths.raw_records_json), RUN_DATE)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))
    return settings, df, LocalEmbeddingIndex.build(df, settings, settings.paths.embeddings_json)


def test_index_build_search_and_manifest(built_index):
    settings, df, index = built_index
    assert index.collection_name == "papers-baseline" and index.collection.count() == 24
    results = index.semantic_search("freshness SLA for LLM knowledge", top_k=2)
    assert len(results) == 2 and "Freshness" in results[0].title and 0 <= results[0].score <= 1
    manifest = read_json(settings.paths.embeddings_json)
    assert manifest["persist_path"] == "data/chroma"  # duong dan tuong doi, chay duoc tren may khac
    assert LocalEmbeddingIndex.load(settings).collection.count() == 24


def test_index_lookup_and_build_from_clean(built_index):
    settings, df, index = built_index
    assert index.lookup(df.iloc[0]["title"].upper())["paper_id"] == df.iloc[0]["paper_id"]
    assert index.lookup(df.iloc[0]["paper_id"])["title"] == df.iloc[0]["title"]
    assert index.lookup("does not exist") is None
    for name in ("papers-corrupted", "custom-name"):
        fresh = LocalEmbeddingIndex(settings, collection_name=name).build_from_clean()
        assert fresh.collection.count() == 24
    assert settings.paths.corrupted_embeddings_json.exists()
    assert (settings.paths.embeddings_json.parent / "custom-name.json").exists()
    other = LocalEmbeddingIndex.build(df.head(12), settings, settings.paths.project_dir / "data" / "embeddings" / "other.json")
    assert other.collection_name == "other"


def test_qa_answers_each_question_type(built_index):
    settings, df, index = built_index
    for item in build_test_set(df, settings.paths.test_set_json):
        result = answer_question(item["question"], settings=settings, index=index)
        assert result.answer == item["ground_truth"], item["id"]
        assert set(item["ground_truth_doc_ids"]) <= set(result.retrieved_doc_ids)


def test_qa_fallbacks(built_index):
    settings, df, index = built_index
    result = answer_question("Tell me about dense retrieval", settings=settings, index=index)
    assert result.answer and len(result.retrieved_doc_ids) == settings.top_k
    shared = answer_question("What categories do the papers 'Agentic Retrieval-Augmented Generation for Knowledge-Intensive Tasks' "
                             "and 'Semantic Layer Integration for Agentic Text-to-SQL Pipelines' have in common?", settings=settings, index=index)
    assert shared.answer == "No shared categories found."


def test_evaluate_pipeline_with_mock_judge(built_index):
    settings, df, index = built_index
    build_test_set(df, settings.paths.test_set_json)
    metrics_path = settings.paths.baseline_metrics
    bundle = evaluate_pipeline(settings, index, settings.paths.test_set_json, metrics_path, settings.paths.baseline_answers)
    assert bundle.summary["retrieval_hit_rate"] == 1.0 and bundle.summary["mean_token_f1"] == 1.0
    assert bundle.summary["ragas"] == {"skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."}
    assert read_json(metrics_path)["samples"] == 10


def test_token_f1():
    assert _token_f1("a b c", "a b c") == 1.0
    assert _token_f1("a b", "c d") == 0.0
    assert _token_f1("", "x") == 0.0
    assert 0 < _token_f1("a b c d", "a b") < 1
