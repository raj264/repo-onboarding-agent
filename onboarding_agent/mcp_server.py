"""The MCP server: advertises the 8 tools below and dispatches calls to their
implementations in `tools/*.py`. Run as a subprocess by `mcp_client.McpToolClient`, one
instance per CLI invocation, scoped to a single `target_repo`.
"""

import argparse
import asyncio
from pathlib import Path

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from onboarding_agent import __version__
from onboarding_agent.tools.docs_tools import search_docs_tool
from onboarding_agent.tools.fs_tools import list_files, read_file
from onboarding_agent.tools.git_tools import git_diff, git_log
from onboarding_agent.tools.pr_tools import open_draft_pr
from onboarding_agent.tools.test_lint_tools import run_lint, run_tests

# Tool schemas advertised to the LLM via McpToolClient.list_anthropic_tools(). Keep each
# description and inputSchema in sync with the corresponding branch in handle_call_tool
# below and the implementation it calls in tools/*.py.
TOOLS = [
    types.Tool(
        name="search_docs",
        description=(
            "Search the target repository's indexed markdown documentation for content "
            "relevant to a query. Returns the top-k most relevant doc chunks with their "
            "source file paths. Use this before answering any 'how does X work' question."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language search query."},
                "k": {"type": "integer", "description": "Number of results to return.", "default": 5},
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="read_file",
        description="Read a file's contents, given a path relative to the target repository root.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to the target repo root."},
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="list_files",
        description="List files in the target repo matching a glob pattern (e.g. '**/*.py', 'docs/**/*.md').",
        inputSchema={
            "type": "object",
            "properties": {
                "glob_pattern": {
                    "type": "string",
                    "description": "Glob pattern relative to the repo root.",
                    "default": "**/*",
                },
            },
            "required": [],
        },
    ),
    types.Tool(
        name="git_log",
        description="Show recent git commit history for the target repository, optionally scoped to a path.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Optional path to scope the log to."},
                "n": {"type": "integer", "description": "Number of commits to show.", "default": 10},
            },
            "required": [],
        },
    ),
    types.Tool(
        name="git_diff",
        description=(
            "Show the git diff between the target repository's working tree and a given ref "
            "(default: previous commit)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Git ref to diff against.", "default": "HEAD~1"},
            },
            "required": [],
        },
    ),
    types.Tool(
        name="run_tests",
        description=(
            "Run the target repository's test suite and return the output. Detects the runner from "
            "project markers: pytest (pyproject.toml/setup.py/requirements.txt), npm test (package.json), "
            "go test (go.mod), or cargo test (Cargo.toml). The optional 'path' argument only scopes pytest "
            "runs. Reports a clear message if no recognized runner is found."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Optional path/file to scope a pytest run to."},
            },
            "required": [],
        },
    ),
    types.Tool(
        name="run_lint",
        description=(
            "Run the linter configured in the target repository (ruff/flake8 for Python, eslint for "
            "JavaScript/TypeScript), if any config is found. Reports 'No lint config found in target "
            "repo.' if none is present."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    types.Tool(
        name="open_draft_pr",
        description=(
            "Create a new branch, commit the given file changes, push, and open a DRAFT pull request "
            "via the GitHub CLI. This has real-world side effects and is disabled unless the agent was "
            "started with --allow-pr. Even when enabled, you must summarize the proposed changes to the "
            "human in chat and get explicit confirmation before calling this tool."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Pull request title."},
                "body": {"type": "string", "description": "Pull request body/description."},
                "branch_name": {"type": "string", "description": "New branch name to create."},
                "files": {
                    "type": "object",
                    "description": "Mapping of file path (relative to repo root) to full new file content.",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["title", "body", "branch_name", "files"],
        },
    ),
]


def build_server(target_repo: Path, allow_pr: bool) -> Server:
    """Constructs the MCP `Server`, closing over `target_repo`/`allow_pr` so every tool
    call below is implicitly scoped to this run's target repository and PR permission.
    """
    server = Server("repo-onboarding-agent")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return TOOLS

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        # Dispatch table: tool name -> implementation in tools/*.py. Each branch maps
        # the MCP `arguments` dict onto that function's keyword arguments, applying the
        # same defaults declared in the matching TOOLS[].inputSchema above.
        arguments = arguments or {}

        if name == "search_docs":
            result = search_docs_tool(target_repo, arguments["query"], k=arguments.get("k", 5))
        elif name == "read_file":
            result = read_file(target_repo, arguments["path"])
        elif name == "list_files":
            files = list_files(target_repo, arguments.get("glob_pattern", "**/*"))
            result = "\n".join(files) if files else "No files matched."
        elif name == "git_log":
            result = git_log(target_repo, path=arguments.get("path"), n=arguments.get("n", 10))
        elif name == "git_diff":
            result = git_diff(target_repo, ref=arguments.get("ref", "HEAD~1"))
        elif name == "run_tests":
            result = run_tests(target_repo, path=arguments.get("path"))
        elif name == "run_lint":
            result = run_lint(target_repo)
        elif name == "open_draft_pr":
            result = open_draft_pr(
                target_repo,
                title=arguments["title"],
                body=arguments["body"],
                branch_name=arguments["branch_name"],
                files=arguments["files"],
                allow_pr=allow_pr,
            )
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [types.TextContent(type="text", text=result)]

    return server


async def run_stdio(target_repo: Path, allow_pr: bool) -> None:
    """Builds the server and serves it over stdio until the parent process (the
    `McpToolClient` that spawned this subprocess) closes the pipes.
    """
    server = build_server(target_repo, allow_pr)
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="repo-onboarding-agent",
                server_version=__version__,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    """Entry point for `python -m onboarding_agent.mcp_server`, the command
    `McpToolClient` spawns as a subprocess (see mcp_client.py).
    """
    parser = argparse.ArgumentParser(description="Repo Onboarding Agent MCP server")
    parser.add_argument("--target-repo", required=True, type=Path)
    parser.add_argument("--allow-pr", action="store_true", default=False)
    args = parser.parse_args()
    asyncio.run(run_stdio(args.target_repo, args.allow_pr))


if __name__ == "__main__":
    main()
