from __future__ import annotations
from incident_commander.config import get_settings

def get_chat_model():
    settings = get_settings()
    if settings.ai_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=settings.ollama_model, base_url=settings.ollama_base_url, temperature=0)
    if settings.ai_provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError('OpenAI provider selected. Install with: pip install -e ".[openai]"') from exc
        return ChatOpenAI(model=settings.openai_model, temperature=0)
    raise ValueError(f"Unsupported AI_PROVIDER={settings.ai_provider!r}. Use 'ollama' or 'openai'.")

