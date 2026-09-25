from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
import requests

from core.config import load_settings, normalized_provider, require_llm_credentials
from core.utils import read_json
from ingestion import crossref
from ingestion.corruption import corrupt_clean_dataframe
from pipelines import corruption_flow, phase1, self_heal
from retrieval import agent as agent_module
from retrieval.llm import build_llm


@pytest.fixture
def run_in(monkeypatch, settings):
    """Tro 2 pipeline vao project tam thay vi data/ that."""
    monkeypatch.setattr(phase1, "load_settings", lambda: settings)
    monkeypatch.setattr(corruption_flow, "load_settings", lambda: settings)
    return settings


# ---------- end-to-end pipelines ----------

def test_phase1_then_corruption_flow_end_to_end(run_in):
    paths = run_in.paths
    phase1.main()
    for path in (paths.clean_csv, paths.clean_json, paths.test_set_json, paths.baseline_metrics, paths.baseline_report,
                 paths.freshness_report, paths.baseline_quality_report, paths.demo_answers, paths.dashboard_html):
        assert path.exists(), path
    assert read_json(paths.baseline_metrics)["retrieval_hit_rate"] == 1.0

    corruption_flow.main()
    baseline, corrupted, repaired = (read_json(p) for p in (paths.baseline_metrics, paths.corrupted_metrics, paths.repaired_metrics))
    assert corrupted["retrieval_hit_rate"] < baseline["retrieval_hit_rate"] == repaired["retrieval_hit_rate"]
    assert repaired["mean_token_f1"] == baseline["mean_token_f1"]
    assert read_json(paths.corrupted_quality_report)["success"] is False
    heal = read_json(paths.self_heal_log)["runs"][-1]
    assert heal["triggered"] and heal["strategy"] == "rollback_to_raw_snapshot" and heal["healthy_after"]
    assert "Baseline vs Corrupted vs Repaired" in paths.comparison_report.read_text(encoding="utf-8")

    # Idempotent: repair lan 2 cho dung du lieu nhu lan 1.
    first = paths.repaired_clean_json.read_text(encoding="utf-8")
    corruption_flow.main()
    assert paths.repaired_clean_json.read_text(encoding="utf-8") == first


def test_phase1_quality_gate_blocks_indexing(run_in, monkeypatch):
    monkeypatch.setattr(phase1, "run_data_quality_checks", lambda *a, **k: {"success": False, "failed_expectations": ["x"]})
    with pytest.raises(RuntimeError, match="Quality Gate blocked indexing"):
        phase1.main()
    assert not run_in.paths.embeddings_json.exists()


def test_corruption_flow_requires_phase1(run_in):
    with pytest.raises(FileNotFoundError, match="run_phase1"):
        corruption_flow.main()


# ---------- self-healing ----------

def test_self_heal_not_triggered_when_healthy(clean_df, settings):
    result = self_heal.self_heal(clean_df, settings, "baseline", settings.paths.freshness_report)
    assert result.triggered is False and result.df is clean_df
    assert read_json(settings.paths.self_heal_log)["runs"][-1]["triggered"] is False


def test_self_heal_rolls_back_to_raw(clean_df, settings):
    corrupted = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    result = self_heal.self_heal(corrupted, settings, "corrupted", settings.paths.quality_dir / "f.json")
    assert result.triggered and result.strategy == "rollback_to_raw_snapshot" and result.after.healthy
    assert len(result.df) == 24 and result.df["paper_id"].is_unique
    assert (settings.paths.quality_dir / "f_healed.json").exists()


def test_self_heal_refetches_when_rollback_fails(clean_df, settings, monkeypatch):
    corrupted = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)

    def broken_rollback(_settings):
        raise FileNotFoundError("raw snapshot missing")

    def api_down(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(self_heal, "_rebuild_from_raw", broken_rollback)
    monkeypatch.setattr(crossref.requests, "get", api_down)
    monkeypatch.setattr(crossref.time, "sleep", lambda _: None)
    result = self_heal.self_heal(corrupted, settings, "corrupted", settings.paths.quality_dir / "f.json")
    assert result.strategy == "refetch_from_source" and result.after.healthy
    assert result.events[1] == {"step": "repair", "strategy": "rollback_to_raw_snapshot", "error": "raw snapshot missing"}


def test_self_heal_raises_when_every_strategy_fails(clean_df, settings, monkeypatch):
    corrupted = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    monkeypatch.setattr(self_heal, "_rebuild_from_raw", lambda _settings: corrupted)
    with pytest.raises(RuntimeError, match="Self-healing failed"):
        self_heal.self_heal(corrupted, settings, "corrupted", settings.paths.quality_dir / "f.json", allow_refetch=False)
    assert read_json(settings.paths.self_heal_log)["runs"][-1]["healthy_after"] is False


# ---------- config & LLM providers ----------

def test_settings_paths_are_project_relative(settings, project):
    assert settings.paths.project_dir == project.resolve()
    assert settings.paths.test_set_json == settings.paths.eval_testset
    assert settings.llm_provider == "mock" and settings.max_results == 24 and settings.freshness_threshold_days == 180


def test_env_flags(project, monkeypatch):
    monkeypatch.setenv("REFRESH_SOURCE", "yes")
    monkeypatch.setenv("REFRESH_TEST_SET", "1")
    loaded = load_settings(project)
    assert loaded.refresh_source and loaded.refresh_test_set


@pytest.mark.parametrize("provider, key_field, expected", [
    ("gemini", "google_api_key", "ChatGoogleGenerativeAI"),
    ("openai", "openai_api_key", "ChatOpenAI"),
    ("Anthorpic", "anthropic_api_key", "ChatAnthropic"),
    ("openrouter", "openrouter_api_key", "ChatOpenAI"),
    ("custom-llm", "custom_llm_base_url", "ChatOpenAI"),
    ("ollama", None, "ChatOllama"),
    ("mock", None, "FakeListChatModel"),
])
def test_build_llm_for_each_provider(settings, provider, key_field, expected):
    overrides = {"llm_provider": provider, "model_name": "test-model"}
    if key_field:
        overrides[key_field] = "http://localhost:1/v1" if key_field.endswith("base_url") else "test-key"
    assert type(build_llm(replace(settings, **overrides))).__name__ == expected


@pytest.mark.parametrize("provider", ["gemini", "openai", "anthropic", "openrouter", "custom", "unknown"])
def test_missing_credentials_raise(settings, provider):
    bare = replace(settings, llm_provider=provider, google_api_key=None, openai_api_key=None, anthropic_api_key=None,
                   openrouter_api_key=None, custom_llm_base_url=None)
    with pytest.raises(RuntimeError):
        require_llm_credentials(bare)
    assert normalized_provider(replace(settings, llm_provider="Custom LLM")) == "custom"


# ---------- agent tools ----------

def test_agent_tools_and_runner(settings, clean_df, monkeypatch):
    from retrieval.index import LocalEmbeddingIndex

    index = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)
    captured = {}
    monkeypatch.setattr(agent_module, "create_agent", lambda **kwargs: captured.update(kwargs) or "agent")
    assert agent_module.build_agent(settings, index) == "agent"

    search, lookup = captured["tools"]
    assert "paper_id: " in search.invoke({"query": "hybrid search BM25", "top_k": 2})
    assert "paper_id: 10.1145/3637528.3671801" in lookup.invoke({"paper_id_or_title": "10.1145/3637528.3671801"})
    assert lookup.invoke({"paper_id_or_title": "nope"}) == "No exact paper match found."

    fake = SimpleNamespace(invoke=lambda payload: {"messages": [SimpleNamespace(content="final answer")]})
    assert agent_module.run_agent_question(fake, "q") == "final answer"
    assert agent_module.run_agent_question(SimpleNamespace(invoke=lambda payload: {}), "q") == ""
