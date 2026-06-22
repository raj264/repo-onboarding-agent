import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpToolClient:
    def __init__(self, target_repo: Path, allow_pr: bool = False):
        self._target_repo = target_repo
        self._allow_pr = allow_pr
        self._stack = AsyncExitStack()
        self.session: ClientSession | None = None

    async def __aenter__(self) -> "McpToolClient":
        args = ["-m", "onboarding_agent.mcp_server", "--target-repo", str(self._target_repo)]
        if self._allow_pr:
            args.append("--allow-pr")

        server_params = StdioServerParameters(command=sys.executable, args=args)

        read, write = await self._stack.enter_async_context(stdio_client(server_params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._stack.aclose()

    async def list_anthropic_tools(self) -> list[dict]:
        result = await self.session.list_tools()
        return [
            {"name": tool.name, "description": tool.description, "input_schema": tool.inputSchema}
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> tuple[str, bool]:
        result = await self.session.call_tool(name, arguments)
        text = "\n".join(block.text for block in result.content if block.type == "text")
        return text, bool(result.isError)
