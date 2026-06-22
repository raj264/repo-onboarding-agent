import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from onboarding_agent.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DIR_NAME,
    EMBEDDING_MODEL_NAME,
)

_SKIP_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    CHROMA_DIR_NAME,
}


@dataclass
class IndexStats:
    files_indexed: int
    chunks_indexed: int


@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return model.encode(texts).tolist()


def iter_doc_files(repo_path: Path) -> Iterator[Path]:
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".md", ".markdown"):
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(repo_path).parts):
            continue
        yield path


def chunk_markdown(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    sections = re.split(r"\n(?=#{1,6}\s)", text)
    chunks: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_chars:
            chunks.append(section)
            continue
        start = 0
        while start < len(section):
            end = start + max_chars
            chunks.append(section[start:end].strip())
            if end >= len(section):
                break
            start = end - overlap
    return [c for c in chunks if c]


def build_index(repo_path: Path, persist_dir: Path | None = None) -> IndexStats:
    import chromadb

    persist_dir = persist_dir or (repo_path / CHROMA_DIR_NAME)
    persist_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)

    files_indexed = 0
    all_chunks: list[str] = []
    all_ids: list[str] = []
    all_metadatas: list[dict] = []

    for path in iter_doc_files(repo_path):
        text = path.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_markdown(text)
        if not chunks:
            continue
        files_indexed += 1
        relative_path = path.relative_to(repo_path).as_posix()
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_ids.append(f"{relative_path}::{i}")
            all_metadatas.append({"source_path": relative_path})

    if all_chunks:
        embeddings = embed_texts(all_chunks)
        collection.upsert(
            ids=all_ids,
            documents=all_chunks,
            metadatas=all_metadatas,
            embeddings=embeddings,
        )

    return IndexStats(files_indexed=files_indexed, chunks_indexed=len(all_chunks))
