from pathlib import Path

import pytest

from onboarding_agent.cli import build_parser, cmd_index


def test_parses_index_command():
    args = build_parser().parse_args(["index", "/some/repo"])
    assert args.command == "index"
    assert args.target_repo == Path("/some/repo")


def test_parses_ask_command_with_flags():
    args = build_parser().parse_args(["ask", "/some/repo", "how does x work?", "--allow-pr", "--model", "foo"])
    assert args.command == "ask"
    assert args.question == "how does x work?"
    assert args.allow_pr is True
    assert args.model == "foo"


def test_parses_chat_command_defaults():
    args = build_parser().parse_args(["chat", "/some/repo"])
    assert args.command == "chat"
    assert args.allow_pr is False


def test_missing_required_positional_exits_nonzero():
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["ask"])
    assert exc_info.value.code != 0


def test_cmd_index_prints_summary(fixture_docs_repo_path, capsys, mock_embedding_model, tmp_path):
    import shutil

    repo_copy = tmp_path / "docs_repo"
    shutil.copytree(fixture_docs_repo_path, repo_copy)

    args = build_parser().parse_args(["index", str(repo_copy)])
    cmd_index(args)

    captured = capsys.readouterr()
    assert "Indexed 3 markdown files" in captured.out
