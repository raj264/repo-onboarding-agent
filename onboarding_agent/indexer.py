"""Builds the RAG index: walks a target repo's markdown files, splits them into
heading-aware chunks, embeds them locally, and upserts them into a persisted chromadb
collection at `<target_repo>/.onboarding_agent_index/`.
"""

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
    """Summary returned by `build_index`, printed by `onboarding-agent index`."""

    files_indexed: int
    chunks_indexed: int


@lru_cache(maxsize=1)
def get_embedding_model():
    """Lazily loads the sentence-transformers model and caches it for the process
    lifetime - the import and model load are slow, and every chunk/query embed call
    reuses this same instance. Tests monkeypatch this function to avoid the real
    (slow, network-dependent) model download.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeds a batch of strings with the cached local model."""
    model = get_embedding_model()
    return model.encode(texts).tolist()


def iter_doc_files(repo_path: Path) -> Iterator[Path]:
    """Yields every `.md`/`.markdown` file under `repo_path`, skipping VCS/dependency/
    cache directories (`_SKIP_DIRS`) and this tool's own index directory.
    """
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".md", ".markdown"):
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(repo_path).parts):
            continue
        yield path


def chunk_markdown(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    """Splits markdown into retrieval-sized chunks, heading-first.

    First splits on top-level-to-h6 headings (`# ... ` through `###### ...`) so each
    chunk is a coherent section. Sections still longer than `max_chars` are then
    sliding-windowed with `overlap` characters of context carried into the next chunk,
    so a sentence that straddles a window boundary still appears whole in at least one
    chunk.
    """
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
    """Indexes every markdown file under `repo_path` into a chromadb collection.

    `persist_dir` defaults to `<repo_path>/.onboarding_agent_index` but is overridable
    (tests use a `tmp_path` so they never touch a real repo's directory). Re-running this
    is safe: `upsert` replaces existing chunks by id (`<relative_path>::<chunk_index>`)
    rather than duplicating them.
    """
    import chromadb
    from chromadb.config import Settings

    persist_dir = persist_dir or (repo_path / CHROMA_DIR_NAME)
    persist_dir.mkdir(parents=True, exist_ok=True)

    # anonymized_telemetry=False avoids chromadb's default background telemetry calls,
    # which otherwise occasionally surface as noisy errors in offline/sandboxed environments.
    client = chromadb.PersistentClient(path=str(persist_dir), settings=Settings(anonymized_telemetry=False))
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
        # Embed once in a single batch rather than per-chunk - much faster, and
        # collection.upsert wants the embeddings precomputed anyway.
        embeddings = embed_texts(all_chunks)
        collection.upsert(
            ids=all_ids,
            documents=all_chunks,
            metadatas=all_metadatas,
            embeddings=embeddings,
        )

    return IndexStats(files_indexed=files_indexed, chunks_indexed=len(all_chunks))
