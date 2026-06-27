from dataclasses import dataclass
from pathlib import Path

from onboarding_agent.config import CHROMA_COLLECTION_NAME, CHROMA_DIR_NAME
from onboarding_agent.indexer import embed_texts


class IndexNotFoundError(Exception):
    pass


@dataclass
class DocResult:
    text: str
    source_path: str
    score: float


def get_chroma_collection(persist_dir: Path):
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(path=str(persist_dir), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)


def search_docs(repo_path: Path, query: str, k: int = 5, persist_dir: Path | None = None) -> list[DocResult]:
    persist_dir = persist_dir or (repo_path / CHROMA_DIR_NAME)
    if not persist_dir.exists():
        raise IndexNotFoundError(
            f"No index found at {persist_dir}. Run 'onboarding-agent index {repo_path}' first."
        )

    collection = get_chroma_collection(persist_dir)
    if collection.count() == 0:
        raise IndexNotFoundError(
            f"Index at {persist_dir} is empty. Run 'onboarding-agent index {repo_path}' first."
        )

    query_embedding = embed_texts([query])
    results = collection.query(query_embeddings=query_embedding, n_results=k)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    return [
        DocResult(text=doc, source_path=meta.get("source_path", "unknown"), score=dist)
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]
