from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import onboarding_agent.cli as cli_module
from onboarding_agent.cli import build_parser, cmd_ask, cmd_chat, cmd_index


class _FakeMcpClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


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


@pytest.mark.asyncio
async def test_cmd_ask_prints_answer(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(cli_module, "McpToolClient", _FakeMcpClient)
    monkeypatch.setattr(cli_module, "AsyncAnthropic", MagicMock())

    fake_agent = MagicMock()
    fake_agent.ask = AsyncMock(return_value="the answer")
    monkeypatch.setattr(cli_module, "Agent", MagicMock(return_value=fake_agent))

    args = build_parser().parse_args(["ask", str(tmp_path), "how does x work?"])
    result = await cmd_ask(args)

    assert result == 0
    fake_agent.ask.assert_called_once_with("how does x work?")
    assert "the answer" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_cmd_ask_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    args = build_parser().parse_args(["ask", str(tmp_path), "question?"])

    with pytest.raises(RuntimeError):
        await cmd_ask(args)


@pytest.mark.asyncio
async def test_cmd_chat_runs_until_exit(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(cli_module, "McpToolClient", _FakeMcpClient)
    monkeypatch.setattr(cli_module, "AsyncAnthropic", MagicMock())

    fake_agent = MagicMock()
    fake_agent.chat_step = AsyncMock(return_value=([], "hi there"))
    monkeypatch.setattr(cli_module, "Agent", MagicMock(return_value=fake_agent))

    inputs = iter(["hello", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    args = build_parser().parse_args(["chat", str(tmp_path)])
    result = await cmd_chat(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "hi there" in captured.out
    fake_agent.chat_step.assert_called_once_with([], "hello")
