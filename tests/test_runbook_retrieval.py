from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from incident_commander.tools import runbooks


def test_lexical_cpu_query_prefers_high_latency(monkeypatch):
    monkeypatch.setenv("RUNBOOK_RETRIEVAL", "lexical")

    results = runbooks.search_runbooks(
        "high CPU worker saturation latency 503",
        top_k=2,
    )

    assert results
    assert results[0]["path"] == "high_latency.md"
    assert results[0]["retrieval_mode"] == "lexical"


def test_lexical_database_query_returns_database_runbook(monkeypatch):
    monkeypatch.setenv("RUNBOOK_RETRIEVAL", "lexical")

    results = runbooks.search_runbooks(
        "database connection pool timeout 503",
        top_k=2,
    )

    assert results
    assert any(item["path"] == "database_pressure.md" for item in results)


def test_markdown_runbooks_are_split_by_heading(tmp_path):
    runbook = tmp_path / "service_failure.md"

    runbook.write_text(
        "# Signals\n"
        "CPU saturation\n"
        "503 responses\n\n"
        "# Remediation guidance\n"
        "Scale out safely\n",
        encoding="utf-8",
    )

    chunks = runbooks._split_markdown_sections(runbook)

    assert len(chunks) == 2
    assert chunks[0]["heading"] == "Signals"
    assert chunks[0]["path"] == "service_failure.md"
    assert "CPU saturation" in chunks[0]["content"]

    assert chunks[1]["heading"] == "Remediation guidance"
    assert "Scale out safely" in chunks[1]["content"]


def test_cosine_similarity_handles_normal_and_invalid_vectors():
    assert runbooks._cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    assert runbooks._cosine_similarity(
        [1.0, 0.0],
        [0.0, 1.0],
    ) == pytest.approx(0.0)

    assert runbooks._cosine_similarity([], []) == 0.0
    assert runbooks._cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert runbooks._cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_vector_index_builds_and_reuses_cached_index(tmp_path, monkeypatch):
    runbook_root = tmp_path / "runbooks"
    runbook_root.mkdir()

    (runbook_root / "high_latency.md").write_text(
        "# Signals\n"
        "CPU saturation and elevated latency\n\n"
        "# Remediation guidance\n"
        "Scale out before restarting\n",
        encoding="utf-8",
    )

    (runbook_root / "database_pressure.md").write_text(
        "# Signals\n"
        "Database connection timeout\n\n"
        "# Safe response\n"
        "Avoid destructive database operations\n",
        encoding="utf-8",
    )

    index_path = tmp_path / "vector_index" / "runbooks.json"

    settings = SimpleNamespace(
        runbook_vector_index_path=str(index_path),
        ollama_embedding_model="fake-embedding-model",
    )

    class FakeEmbeddings:
        def embed_documents(self, texts):
            return [
                [float(index + 1), 1.0]
                for index, _ in enumerate(texts)
            ]

    monkeypatch.setattr(runbooks, "RUNBOOK_ROOT", runbook_root)
    monkeypatch.setattr(runbooks, "get_settings", lambda: settings)
    monkeypatch.setattr(
        runbooks,
        "resolve_project_path",
        lambda value: Path(value),
    )
    monkeypatch.setattr(
        runbooks,
        "_get_embeddings",
        lambda: FakeEmbeddings(),
    )

    payload = runbooks.build_runbook_vector_index(force=True)

    assert payload["retrieval_mode"] == "semantic_vector"
    assert payload["embedding_model"] == "fake-embedding-model"
    assert payload["chunk_count"] == 4
    assert index_path.exists()
    assert all("embedding" in chunk for chunk in payload["chunks"])

    cached = runbooks.build_runbook_vector_index(force=False)

    assert cached["source_fingerprint"] == payload["source_fingerprint"]
    assert cached["chunks"] == payload["chunks"]


def test_vector_index_rejects_empty_runbook_directory(tmp_path, monkeypatch):
    runbook_root = tmp_path / "empty_runbooks"
    runbook_root.mkdir()

    settings = SimpleNamespace(
        runbook_vector_index_path=str(tmp_path / "index.json"),
        ollama_embedding_model="fake-embedding-model",
    )

    monkeypatch.setattr(runbooks, "RUNBOOK_ROOT", runbook_root)
    monkeypatch.setattr(runbooks, "get_settings", lambda: settings)
    monkeypatch.setattr(
        runbooks,
        "resolve_project_path",
        lambda value: Path(value),
    )

    with pytest.raises(RuntimeError, match="No Markdown runbooks found"):
        runbooks.build_runbook_vector_index(force=True)


def test_semantic_search_ranks_and_enriches_guidance(monkeypatch):
    settings = SimpleNamespace(
        ollama_embedding_model="fake-embedding-model",
    )

    index = {
        "chunks": [
            {
                "title": "High Latency",
                "path": "high_latency.md",
                "heading": "Signals",
                "content": "CPU saturation and worker exhaustion",
                "embedding": [1.0, 0.0],
            },
            {
                "title": "High Latency",
                "path": "high_latency.md",
                "heading": "Remediation guidance",
                "content": "Scale out before restarting",
                "embedding": [0.95, 0.05],
            },
            {
                "title": "Database Pressure",
                "path": "database_pressure.md",
                "heading": "Signals",
                "content": "Database connection timeouts",
                "embedding": [0.0, 1.0],
            },
            {
                "title": "Database Pressure",
                "path": "database_pressure.md",
                "heading": "Safe response",
                "content": "Avoid destructive database operations",
                "embedding": [0.1, 0.9],
            },
        ]
    }

    class FakeEmbeddings:
        def embed_query(self, query):
            assert query
            return [1.0, 0.0]

    monkeypatch.setattr(runbooks, "get_settings", lambda: settings)
    monkeypatch.setattr(
        runbooks,
        "build_runbook_vector_index",
        lambda force=False: index,
    )
    monkeypatch.setattr(
        runbooks,
        "_get_embeddings",
        lambda: FakeEmbeddings(),
    )

    results = runbooks.search_runbooks_semantic(
        "high CPU worker saturation",
        top_k=2,
    )

    assert results
    assert results[0]["path"] == "high_latency.md"
    assert results[0]["heading"] == "Signals"
    assert results[0]["retrieval_mode"] == "semantic_vector"

    assert any(
        item["heading"] == "Remediation guidance"
        for item in results
    )

    assert any(
        item["path"] == "database_pressure.md"
        for item in results
    )


def test_search_runbooks_semantic_success_path(monkeypatch):
    settings = SimpleNamespace(
        semantic_retrieval_enabled=True,
    )

    semantic_result = [
        {
            "path": "high_latency.md",
            "heading": "Signals",
            "retrieval_mode": "semantic_vector",
        }
    ]

    observations = []

    @contextmanager
    def fake_observe_rag():
        observation = {}
        observations.append(observation)
        yield observation

    monkeypatch.setattr(runbooks, "get_settings", lambda: settings)
    monkeypatch.setattr(runbooks, "observe_rag", fake_observe_rag)
    monkeypatch.setattr(
        runbooks,
        "search_runbooks_semantic",
        lambda query, top_k: semantic_result,
    )
    monkeypatch.setattr(runbooks, "log_event", lambda *args, **kwargs: None)

    results = runbooks.search_runbooks(
        "worker saturation",
        top_k=2,
    )

    assert results == semantic_result
    assert observations[-1]["mode"] == "semantic_vector"


def test_search_runbooks_falls_back_when_semantic_retrieval_fails(monkeypatch):
    settings = SimpleNamespace(
        semantic_retrieval_enabled=True,
    )

    observations = []

    @contextmanager
    def fake_observe_rag():
        observation = {}
        observations.append(observation)
        yield observation

    def fail_semantic(query, top_k):
        raise RuntimeError("embedding provider unavailable")

    lexical_result = [
        {
            "title": "High Latency",
            "path": "high_latency.md",
            "heading": "High Latency",
            "score": 1.0,
            "retrieval_mode": "lexical",
            "content": "CPU saturation",
        }
    ]

    monkeypatch.setattr(runbooks, "get_settings", lambda: settings)
    monkeypatch.setattr(runbooks, "observe_rag", fake_observe_rag)
    monkeypatch.setattr(
        runbooks,
        "search_runbooks_semantic",
        fail_semantic,
    )
    monkeypatch.setattr(
        runbooks,
        "search_runbooks_lexical",
        lambda query, top_k: [dict(item) for item in lexical_result],
    )
    monkeypatch.setattr(runbooks, "log_event", lambda *args, **kwargs: None)

    results = runbooks.search_runbooks(
        "worker saturation",
        top_k=2,
    )

    assert results[0]["retrieval_mode"] == "lexical_fallback"
    assert "RuntimeError" in results[0]["semantic_error"]
    assert "embedding provider unavailable" in results[0]["semantic_error"]
    assert observations[-1]["mode"] == "lexical_fallback"