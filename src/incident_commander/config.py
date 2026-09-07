from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def get_data_root() -> Path:
    """
    Resolve runtime data independently of Python package installation path.

    Source/dev:
        <project>/data

    Docker:
        /app/data via INCIDENT_COMMANDER_DATA_DIR
    """
    configured = os.getenv("INCIDENT_COMMANDER_DATA_DIR")

    if configured:
        return Path(configured).expanduser().resolve()

    cwd_candidate = Path.cwd() / "data"

    if cwd_candidate.exists():
        return cwd_candidate.resolve()

    return (PROJECT_ROOT / "data").resolve()

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    ai_mode: str
    ai_provider: str
    ollama_model: str
    ollama_base_url: str
    openai_model: str

    # Stage 3: persistent checkpoints
    checkpoint_db_path: str

    # Stage 3: semantic vector RAG
    runbook_retrieval: str
    ollama_embedding_model: str
    runbook_vector_index_path: str

    # Stage 4: observability / tracing
    log_level: str
    langsmith_tracing: bool
    langsmith_project: str

    @property
    def llm_enabled(self) -> bool:
        return self.ai_mode.lower() == "llm"

    @property
    def semantic_retrieval_enabled(self) -> bool:
        return self.runbook_retrieval.lower() == "semantic"


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def get_settings() -> Settings:
    return Settings(
        ai_mode=os.getenv("AI_MODE", "llm").strip().lower(),
        ai_provider=os.getenv("AI_PROVIDER", "ollama").strip().lower(),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:4b").strip(),
        ollama_base_url=os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        ).strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini").strip(),
        checkpoint_db_path=os.getenv(
            "CHECKPOINT_DB_PATH",
            "data/checkpoints/incident_commander.sqlite",
        ).strip(),
        runbook_retrieval=os.getenv(
            "RUNBOOK_RETRIEVAL", "semantic"
        ).strip().lower(),
        ollama_embedding_model=os.getenv(
            "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
        ).strip(),
        runbook_vector_index_path=os.getenv(
            "RUNBOOK_VECTOR_INDEX_PATH", "data/vector_index/runbooks.json"
        ).strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        langsmith_tracing=_env_bool("LANGSMITH_TRACING", False),
        langsmith_project=os.getenv(
            "LANGSMITH_PROJECT", "agentic-incident-commander"
        ).strip(),
    )

