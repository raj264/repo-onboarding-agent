from onboarding_agent.indexer import build_index, chunk_markdown, iter_doc_files


def test_iter_doc_files_finds_markdown_and_skips_noise(fixture_docs_repo_path):
    found = sorted(
        p.relative_to(fixture_docs_repo_path).as_posix() for p in iter_doc_files(fixture_docs_repo_path)
    )
    assert found == ["README.md", "docs/architecture.md", "docs/faq.md"]


def test_iter_doc_files_skips_noise_dirs(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "keep.md").write_text("# Keep\ncontent")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "skip.md").write_text("# Skip\ncontent")

    found = sorted(p.relative_to(tmp_path).as_posix() for p in iter_doc_files(tmp_path))
    assert found == ["docs/keep.md"]


def test_chunk_markdown_splits_on_headings():
    text = (
        "# Title\n\nintro text\n\n"
        "## Section One\n\nfirst section body\n\n"
        "## Section Two\n\nsecond section body"
    )
    chunks = chunk_markdown(text)
    assert len(chunks) == 3
    assert chunks[0].startswith("# Title")
    assert chunks[1].startswith("## Section One")
    assert chunks[2].startswith("## Section Two")


def test_chunk_markdown_splits_oversized_section():
    body = "word " * 1000
    text = f"# Title\n\n{body}"
    chunks = chunk_markdown(text, max_chars=500, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)


def test_build_index_indexes_fixture_repo(fixture_docs_repo_path, tmp_path, mock_embedding_model):
    stats = build_index(fixture_docs_repo_path, persist_dir=tmp_path / "index")
    assert stats.files_indexed == 3
    assert stats.chunks_indexed > 0


def test_build_index_is_idempotent(fixture_docs_repo_path, tmp_path, mock_embedding_model):
    persist_dir = tmp_path / "index"
    first = build_index(fixture_docs_repo_path, persist_dir=persist_dir)
    second = build_index(fixture_docs_repo_path, persist_dir=persist_dir)
    assert first.chunks_indexed == second.chunks_indexed
