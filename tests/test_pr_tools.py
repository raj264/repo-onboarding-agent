from unittest.mock import MagicMock, patch

import pytest

from onboarding_agent.tools.pr_tools import PrNotAllowedError, open_draft_pr


def test_open_draft_pr_blocked_when_not_allowed(tmp_path):
    with patch("onboarding_agent.tools.pr_tools.subprocess.run") as mock_run:
        with pytest.raises(PrNotAllowedError):
            open_draft_pr(tmp_path, "title", "body", "fix-branch", {"a.md": "content"}, allow_pr=False)
        mock_run.assert_not_called()


def test_open_draft_pr_rejects_unsafe_branch_name(tmp_path):
    with pytest.raises(ValueError):
        open_draft_pr(tmp_path, "title", "body", "fix; rm -rf /", {"a.md": "content"}, allow_pr=True)


def test_open_draft_pr_rejects_path_traversal_in_files(tmp_path):
    with pytest.raises(ValueError):
        open_draft_pr(tmp_path, "title", "body", "fix-branch", {"../escape.md": "content"}, allow_pr=True)


def test_open_draft_pr_runs_expected_command_sequence(tmp_path):
    (tmp_path / ".git").mkdir()

    def fake_run(command, **kwargs):
        if command[:2] == ["gh", "pr"]:
            return MagicMock(returncode=0, stdout="https://github.com/me/repo/pull/1\n", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("onboarding_agent.tools.pr_tools.subprocess.run", side_effect=fake_run) as mock_run:
        url = open_draft_pr(
            tmp_path, "Fix typo", "Fixes a typo in docs.", "fix-typo", {"docs/faq.md": "new content"}, allow_pr=True
        )

    assert url == "https://github.com/me/repo/pull/1"
    commands = [call.args[0] for call in mock_run.call_args_list]
    assert commands[0] == ["git", "checkout", "-b", "fix-typo"]
    assert commands[1] == ["git", "add", "docs/faq.md"]
    assert commands[2] == ["git", "commit", "-m", "Fix typo"]
    assert commands[3] == ["git", "push", "-u", "origin", "fix-typo"]
    assert commands[4][:3] == ["gh", "pr", "create"]
    assert (tmp_path / "docs" / "faq.md").read_text() == "new content"
