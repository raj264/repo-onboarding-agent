from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from onboarding_agent.agent_loop import Agent


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(id_, name, input_):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


def _response(stop_reason, content):
    return SimpleNamespace(stop_reason=stop_reason, content=content)


@pytest.fixture
def mock_mcp_client():
    client = AsyncMock()
    client.list_anthropic_tools.return_value = [
        {"name": "search_docs", "description": "search", "input_schema": {"type": "object", "properties": {}}}
    ]
    return client


@pytest.fixture
def mock_anthropic_client():
    return AsyncMock()


@pytest.mark.asyncio
async def test_ask_returns_final_text_without_tool_use(mock_mcp_client, mock_anthropic_client):
    mock_anthropic_client.messages.create.return_value = _response(
        "end_turn", [_text_block("hello there")]
    )

    agent = Agent(mock_mcp_client, mock_anthropic_client)
    answer = await agent.ask("hi")

    assert answer == "hello there"
    mock_mcp_client.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_ask_executes_tool_then_returns_final_text(mock_mcp_client, mock_anthropic_client):
    mock_mcp_client.call_tool.return_value = ("doc content", False)
    mock_anthropic_client.messages.create.side_effect = [
        _response("tool_use", [_tool_use_block("id1", "search_docs", {"query": "x"})]),
        _response("end_turn", [_text_block("final answer")]),
    ]

    agent = Agent(mock_mcp_client, mock_anthropic_client)
    answer = await agent.ask("how does x work?")

    assert answer == "final answer"
    mock_mcp_client.call_tool.assert_called_once_with("search_docs", {"query": "x"})

    final_messages = mock_anthropic_client.messages.create.call_args_list[-1].kwargs["messages"]
    tool_result_message = final_messages[-2]
    assert tool_result_message["role"] == "user"
    assert tool_result_message["content"][0]["content"] == "doc content"
    assert "is_error" not in tool_result_message["content"][0]


@pytest.mark.asyncio
async def test_ask_marks_tool_error(mock_mcp_client, mock_anthropic_client):
    mock_mcp_client.call_tool.side_effect = RuntimeError("boom")
    mock_anthropic_client.messages.create.side_effect = [
        _response("tool_use", [_tool_use_block("id1", "open_draft_pr", {})]),
        _response("end_turn", [_text_block("could not complete that")]),
    ]

    agent = Agent(mock_mcp_client, mock_anthropic_client)
    answer = await agent.ask("open a pr")

    assert answer == "could not complete that"
    final_messages = mock_anthropic_client.messages.create.call_args_list[-1].kwargs["messages"]
    tool_result = final_messages[-2]["content"][0]
    assert tool_result["is_error"] is True
    assert "boom" in tool_result["content"]


@pytest.mark.asyncio
async def test_run_turn_stops_after_max_tool_iterations(mock_mcp_client, mock_anthropic_client):
    mock_mcp_client.call_tool.return_value = ("doc content", False)
    mock_anthropic_client.messages.create.return_value = _response(
        "tool_use", [_tool_use_block("id1", "search_docs", {"query": "x"})]
    )

    agent = Agent(mock_mcp_client, mock_anthropic_client)
    answer = await agent.ask("loop forever")

    assert "Stopped after" in answer
    assert mock_mcp_client.call_tool.call_count == 10


@pytest.mark.asyncio
async def test_chat_step_maintains_history(mock_mcp_client, mock_anthropic_client):
    mock_anthropic_client.messages.create.return_value = _response("end_turn", [_text_block("ok")])

    agent = Agent(mock_mcp_client, mock_anthropic_client)
    messages, answer = await agent.chat_step([], "first question")

    assert answer == "ok"
    assert messages[0] == {"role": "user", "content": "first question"}
