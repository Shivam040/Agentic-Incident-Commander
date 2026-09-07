from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from langsmith import traceable

from incident_commander.config import (
    get_data_root,
    get_settings,
    resolve_project_path,
)
from incident_commander.observability import log_event, observe_rag

DATA_ROOT = get_data_root()
RUNBOOK_ROOT = DATA_ROOT / "runbooks"


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_-]+", text.lower())
        if len(token) >= 3
    }


def _source_fingerprint() -> str:
    """Hash runbook names + contents so the vector index auto-refreshes."""
    digest = hashlib.sha256()
    for path in sorted(RUNBOOK_ROOT.glob("*.md")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _split_markdown_sections(path: Path) -> list[dict]:
    """Create small heading-aware chunks from one Markdown runbook."""
    text = path.read_text(encoding="utf-8")
    title = path.stem.replace("_", " ").title()

    chunks: list[dict] = []
    current_heading = title
    current_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if not body:
            return
        chunk_text = f"{current_heading}\n\n{body}".strip()
        chunks.append(
            {
                "id": f"{path.stem}:{len(chunks)}",
                "title": title,
                "path": path.name,
                "heading": current_heading,
                "content": chunk_text,
            }
        )

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("#"):
            flush()
            current_lines.clear()
            current_heading = line.lstrip("#").strip() or title
        else:
            current_lines.append(line)

    flush()
    return chunks


def _all_chunks() -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(RUNBOOK_ROOT.glob("*.md")):
        chunks.extend(_split_markdown_sections(path))
    return chunks


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def search_runbooks_lexical(query: str, top_k: int = 3) -> list[dict]:
    """Stage-2 lexical fallback retained for resilience and comparison."""
    query_tokens = _tokens(query)
    results: list[dict] = []

    for path in RUNBOOK_ROOT.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        doc_tokens = _tokens(text)
        overlap = len(query_tokens & doc_tokens)
        score = overlap / max(len(query_tokens), 1)
        results.append(
            {
                "title": path.stem.replace("_", " ").title(),
                "path": path.name,
                "heading": path.stem.replace("_", " ").title(),
                "score": round(score, 4),
                "retrieval_mode": "lexical",
                "content": text,
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def _get_embeddings():
    from langchain_ollama import OllamaEmbeddings

    settings = get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embedding_model,
        base_url=settings.ollama_base_url,
    )


def build_runbook_vector_index(force: bool = False) -> dict:
    """
    Build or refresh a small persistent dense-vector index.

    The project intentionally keeps the storage format transparent JSON for
    interview/demo purposes: Markdown chunks + embedding vectors + metadata.
    Semantic similarity is cosine similarity over Ollama embeddings.
    """
    settings = get_settings()
    index_path = resolve_project_path(settings.runbook_vector_index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    fingerprint = _source_fingerprint()

    if index_path.exists() and not force:
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            if (
                existing.get("source_fingerprint") == fingerprint
                and existing.get("embedding_model")
                == settings.ollama_embedding_model
                and existing.get("chunks")
            ):
                return existing
        except (json.JSONDecodeError, OSError):
            pass

    chunks = _all_chunks()
    if not chunks:
        raise RuntimeError("No Markdown runbooks found to index.")

    embeddings = _get_embeddings()
    vectors = embeddings.embed_documents(
        [chunk["content"] for chunk in chunks]
    )

    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector

    payload = {
        "version": 1,
        "retrieval_mode": "semantic_vector",
        "embedding_model": settings.ollama_embedding_model,
        "source_fingerprint": fingerprint,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }

    index_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def search_runbooks_semantic(query: str, top_k: int = 3) -> list[dict]:
    settings = get_settings()
    index = build_runbook_vector_index(force=False)
    query_vector = _get_embeddings().embed_query(query)

    ranked: list[dict] = []

    for chunk in index["chunks"]:
        score = _cosine_similarity(
            query_vector,
            chunk["embedding"],
        )

        ranked.append(
            {
                "title": chunk["title"],
                "path": chunk["path"],
                "heading": chunk["heading"],
                "score": round(score, 4),
                "retrieval_mode": "semantic_vector",
                "embedding_model": settings.ollama_embedding_model,
                "content": chunk["content"],
            }
        )

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    # Select the strongest distinct runbooks first.
    selected_paths: list[str] = []

    for item in ranked:
        if item["path"] not in selected_paths:
            selected_paths.append(item["path"])

        if len(selected_paths) >= 2:
            break

    selected: list[dict] = []

    # Sections that contain operational/safety guidance.
    guidance_headings = {
        "remediation guidance",
        "safe response",
        "safety",
        "approval",
    }

    for path in selected_paths:
        # Best semantic chunk from this runbook.
        best = next(
            item
            for item in ranked
            if item["path"] == path
        )

        selected.append(best)

        # Also retrieve explicit remediation/safety guidance
        # from the same runbook.
        guidance = next(
            (
                item
                for item in ranked
                if item["path"] == path
                and item["heading"].strip().lower()
                in guidance_headings
                and item["heading"] != best["heading"]
            ),
            None,
        )

        if guidance is not None:
            selected.append(guidance)

    # Fill remaining context with next-best unique chunks.
    target_size = max(top_k, len(selected))
    target_size = min(target_size, 6)

    seen = {
        (item["path"], item["heading"])
        for item in selected
    }

    for item in ranked:
        key = (
            item["path"],
            item["heading"],
        )

        if key in seen:
            continue

        selected.append(item)
        seen.add(key)

        if len(selected) >= target_size:
            break

    return selected[:target_size]


@traceable(run_type="retriever", name="runbook_retrieval")
def search_runbooks(query: str, top_k: int = 3) -> list[dict]:
    """
    Retrieve runbook chunks with observable semantic-to-lexical fallback.

    Default mode is semantic dense-vector retrieval. If the local embedding
    model is unavailable, the system returns lexical results with explicit
    fallback metadata rather than silently pretending vector search succeeded.
    """
    settings = get_settings()

    with observe_rag() as observation:
        if not settings.semantic_retrieval_enabled:
            results = search_runbooks_lexical(query, top_k=top_k)
            observation["mode"] = "lexical"
            log_event("runbook_retrieval", mode="lexical", top_k=top_k)
            return results

        try:
            results = search_runbooks_semantic(query, top_k=top_k)
            observation["mode"] = "semantic_vector"
            log_event("runbook_retrieval", mode="semantic_vector", top_k=top_k)
            return results
        except Exception as exc:
            fallback = search_runbooks_lexical(query, top_k=top_k)
            for item in fallback:
                item["retrieval_mode"] = "lexical_fallback"
                item["semantic_error"] = f"{type(exc).__name__}: {exc}"
            observation["mode"] = "lexical_fallback"
            log_event(
                "runbook_retrieval_fallback",
                mode="lexical_fallback",
                error_type=type(exc).__name__,
                top_k=top_k,
            )
            return fallback


