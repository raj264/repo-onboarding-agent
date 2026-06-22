from unittest.mock import AsyncMock, MagicMock

import pytest

from onboarding_agent.mcp_client import McpToolClient


def _make_tool(name, description, schema):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = schema
    return tool


def _make_text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


@pytest.mark.asyncio
async def test_list_anthropic_tools_maps_mcp_schema(tmp_path):
    client = McpToolClient(tmp_path)
    client.session = AsyncMock()
    list_result = MagicMock()
    list_result.tools = [_make_tool("search_docs", "search the docs", {"type": "object"})]
    client.session.list_tools.return_value = list_result

    tools = await client.list_anthropic_tools()

    assert tools == [{"name": "search_docs", "description": "search the docs", "input_schema": {"type": "object"}}]


@pytest.mark.asyncio
async def test_call_tool_joins_text_blocks_and_reports_no_error(tmp_path):
    client = McpToolClient(tmp_path)
    client.session = AsyncMock()
    call_result = MagicMock()
    call_result.content = [_make_text_block("first"), _make_text_block("second")]
    call_result.isError = False
    client.session.call_tool.return_value = call_result

    text, is_error = await client.call_tool("read_file", {"path": "a.txt"})

    assert text == "first\nsecond"
    assert is_error is False
    client.session.call_tool.assert_called_once_with("read_file", {"path": "a.txt"})


@pytest.mark.asyncio
async def test_call_tool_reports_error_flag(tmp_path):
    client = McpToolClient(tmp_path)
    client.session = AsyncMock()
    call_result = MagicMock()
    call_result.content = [_make_text_block("boom")]
    call_result.isError = True
    client.session.call_tool.return_value = call_result

    text, is_error = await client.call_tool("open_draft_pr", {})

    assert text == "boom"
    assert is_error is True
