from pathlib import Path

from onboarding_agent.retriever import IndexNotFoundError, search_docs


def search_docs_tool(target_repo: Path, query: str, k: int = 5) -> str:
    try:
        results = search_docs(target_repo, query, k=k)
    except IndexNotFoundError as exc:
        return str(exc)

    if not results:
        return "No relevant documentation found."

    parts = []
    for i, result in enumerate(results, start=1):
        parts.append(f"[{i}] {result.source_path} (score={result.score:.4f})\n{result.text}")
    return "\n\n".join(parts)
