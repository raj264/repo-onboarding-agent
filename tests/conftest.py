import subprocess
from pathlib import Path

import numpy as np
import pytest

from onboarding_agent import indexer

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_EMBED_DIM = 32


def _fake_embed(texts: list[str]) -> np.ndarray:
    vectors = []
    for text in texts:
        vec = np.zeros(_EMBED_DIM)
        for word in text.lower().split():
            idx = hash(word) % _EMBED_DIM
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        vectors.append(vec)
    return np.array(vectors)


class _FakeEmbeddingModel:
    def encode(self, texts: list[str]) -> np.ndarray:
        return _fake_embed(texts)


@pytest.fixture
def mock_embedding_model(monkeypatch):
    fake_model = _FakeEmbeddingModel()
    monkeypatch.setattr(indexer, "get_embedding_model", lambda: fake_model)
    yield fake_model


@pytest.fixture
def fixture_docs_repo_path() -> Path:
    return FIXTURES_DIR / "docs_repo"


@pytest.fixture
def tmp_git_repo(tmp_path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, ["init", "-b", "main"])
    _git(repo, ["config", "user.email", "test@example.com"])
    _git(repo, ["config", "user.name", "Test User"])

    (repo / "a.txt").write_text("first version\n")
    _git(repo, ["add", "a.txt"])
    _git(repo, ["commit", "-m", "first commit"])

    (repo / "a.txt").write_text("second version\n")
    _git(repo, ["add", "a.txt"])
    _git(repo, ["commit", "-m", "second commit"])

    return repo


def _git(repo: Path, args: list[str]) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
