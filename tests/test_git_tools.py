from onboarding_agent.tools.git_tools import git_diff, git_log


def test_git_log_returns_commits(tmp_git_repo):
    output = git_log(tmp_git_repo, n=10)
    lines = [line for line in output.splitlines() if line.strip()]
    assert len(lines) == 2
    assert "second commit" in output
    assert "first commit" in output


def test_git_log_respects_n(tmp_git_repo):
    output = git_log(tmp_git_repo, n=1)
    lines = [line for line in output.splitlines() if line.strip()]
    assert len(lines) == 1
    assert "second commit" in output


def test_git_log_on_non_git_repo(tmp_path):
    result = git_log(tmp_path)
    assert result.startswith("ERROR:")


def test_git_diff_shows_changes(tmp_git_repo):
    output = git_diff(tmp_git_repo, ref="HEAD~1")
    assert "a.txt" in output
    assert "second version" in output


def test_git_diff_on_non_git_repo(tmp_path):
    result = git_diff(tmp_path)
    assert result.startswith("ERROR:")
