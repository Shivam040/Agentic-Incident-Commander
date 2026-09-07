from __future__ import annotations

import json

from incident_commander.config import get_settings, resolve_project_path
from incident_commander.tools.runbooks import build_runbook_vector_index


def main() -> None:
    settings = get_settings()
    index = build_runbook_vector_index(force=True)
    print(
        json.dumps(
            {
                "status": "ok",
                "retrieval_mode": index["retrieval_mode"],
                "embedding_model": index["embedding_model"],
                "chunk_count": index["chunk_count"],
                "index_path": str(
                    resolve_project_path(settings.runbook_vector_index_path)
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

