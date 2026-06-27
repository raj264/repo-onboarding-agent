import pytest

from onboarding_agent.mcp_server import TOOLS, build_server


def test_all_tools_present_with_valid_schema():
    names = {tool.name for tool in TOOLS}
    assert names == {
        "search_docs",
        "read_file",
        "list_files",
        "git_log",
        "git_diff",
        "run_tests",
        "run_lint",
        "open_draft_pr",
    }
    for tool in TOOLS:
        assert tool.inputSchema["type"] == "object"
        assert "properties" in tool.inputSchema


@pytest.mark.asyncio
async def test_list_files_tool_dispatches(tmp_path):
    (tmp_path / "a.py").write_text("")
    server = build_server(tmp_path, allow_pr=False)

    handler = server.request_handlers[__import__("mcp.types", fromlist=["CallToolRequest"]).CallToolRequest]
    from mcp.types import CallToolRequest, CallToolRequestParams

    request = CallToolRequest(
        method="tools/call", params=CallToolRequestParams(name="list_files", arguments={})
    )
    result = await handler(request)

    text = result.root.content[0].text
    assert "a.py" in text
    assert result.root.isError is False


@pytest.mark.asyncio
async def test_open_draft_pr_blocked_returns_error_result(tmp_path):
    server = build_server(tmp_path, allow_pr=False)
    from mcp.types import CallToolRequest, CallToolRequestParams

    handler = server.request_handlers[CallToolRequest]
    request = CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(
            name="open_draft_pr",
            arguments={"title": "t", "body": "b", "branch_name": "x", "files": {}},
        ),
    )
    result = await handler(request)

    assert result.root.isError is True
    assert "allow-pr" in result.root.content[0].text
