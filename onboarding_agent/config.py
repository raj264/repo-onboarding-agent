import os

DEFAULT_MODEL = "claude-sonnet-4-6"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
CHROMA_COLLECTION_NAME = "onboarding_docs"
CHROMA_DIR_NAME = ".onboarding_agent_index"


def get_anthropic_api_key() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and set your key, "
            "or export ANTHROPIC_API_KEY in your shell."
        )
    return api_key
