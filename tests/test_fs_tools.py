from onboarding_agent.tools.fs_tools import list_files, read_file


def test_read_file_returns_content(tmp_path):
    (tmp_path / "hello.txt").write_text("hello world")
    assert read_file(tmp_path, "hello.txt") == "hello world"


def test_read_file_rejects_path_traversal(tmp_path):
    result = read_file(tmp_path, "../../etc/passwd")
    assert result.startswith("ERROR:")
    assert "escapes" in result


def test_read_file_missing_file(tmp_path):
    result = read_file(tmp_path, "does_not_exist.txt")
    assert result.startswith("ERROR:")


def test_read_file_truncates_large_file(tmp_path):
    (tmp_path / "big.txt").write_text("x" * 1000)
    result = read_file(tmp_path, "big.txt", max_bytes=100)
    assert "truncated" in result
    assert len(result) < 1000


def test_list_files_matches_glob(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.md").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.py").write_text("")

    found = sorted(list_files(tmp_path, "**/*.py"))
    assert found == ["a.py", "sub/c.py"]


def test_list_files_excludes_git_dir(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("")
    (tmp_path / "real.txt").write_text("")

    found = list_files(tmp_path, "**/*")
    assert found == ["real.txt"]
