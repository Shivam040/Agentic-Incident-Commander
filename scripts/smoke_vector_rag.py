from __future__ import annotations

import json

from incident_commander.tools.runbooks import search_runbooks


def run_case(name: str, query: str, expected_path: str) -> dict:
    results = search_runbooks(query, top_k=2)
    if not results:
        raise RuntimeError(f"{name}: no retrieval results")

    top = results[0]
    semantic_verified = top.get("retrieval_mode") == "semantic_vector"
    expected_hit = any(item.get("path") == expected_path for item in results)

    return {
        "case": name,
        "query": query,
        "semantic_vector_verified": semantic_verified,
        "expected_runbook_in_top_2": expected_hit,
        "top_results": [
            {
                "path": item.get("path"),
                "heading": item.get("heading"),
                "score": item.get("score"),
                "retrieval_mode": item.get("retrieval_mode"),
                "embedding_model": item.get("embedding_model"),
                "semantic_error": item.get("semantic_error"),
            }
            for item in results
        ],
    }


def main() -> None:
    cases = [
        run_case(
            "cpu-saturation",
            "high CPU worker saturation increasing queue 503 latency",
            "high_latency.md",
        ),
        run_case(
            "database-pressure",
            "database connection pool timeout dependency 503",
            "database_pressure.md",
        ),
    ]

    print(json.dumps(cases, indent=2))

    if not all(case["semantic_vector_verified"] for case in cases):
        raise SystemExit(
            "Semantic vector retrieval was not verified. "
            "Ensure Ollama is running and `ollama pull nomic-embed-text` completed."
        )

    if not all(case["expected_runbook_in_top_2"] for case in cases):
        raise SystemExit("One or more expected runbooks were not retrieved in top 2.")

    print("\nStage 3B vector RAG smoke test: PASS")


if __name__ == "__main__":
    main()

