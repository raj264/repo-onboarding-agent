import pytest

from onboarding_agent.indexer import build_index
from onboarding_agent.retriever import IndexNotFoundError, search_docs


def test_search_docs_returns_relevant_chunk(fixture_docs_repo_path, tmp_path, mock_embedding_model):
    persist_dir = tmp_path / "index"
    build_index(fixture_docs_repo_path, persist_dir=persist_dir)

    results = search_docs(fixture_docs_repo_path, "what is the default timeout", k=3, persist_dir=persist_dir)

    assert len(results) > 0
    assert any("faq.md" in r.source_path for r in results)


def test_search_docs_raises_when_index_missing(fixture_docs_repo_path, tmp_path):
    with pytest.raises(IndexNotFoundError):
        search_docs(fixture_docs_repo_path, "anything", persist_dir=tmp_path / "missing")


def test_search_docs_raises_when_index_empty(tmp_path, mock_embedding_model):
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    persist_dir = tmp_path / "index"
    build_index(empty_repo, persist_dir=persist_dir)

    with pytest.raises(IndexNotFoundError):
        search_docs(empty_repo, "anything", persist_dir=persist_dir)
