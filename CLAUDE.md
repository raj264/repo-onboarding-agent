# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # or: pip install -e ".[dev]"

# Run the CLI against a target repo (any other codebase, not this one)
cp .env.example .env   # set ANTHROPIC_API_KEY
onboarding-agent index <path-to-target-repo>
onboarding-agent ask <path-to-target-repo> "how does X work?"
onboarding-agent chat <path-to-target-repo> [--allow-pr]
# without `pip install -e .`: python -m onboarding_agent.cli ...

# Tests (no ANTHROPIC_API_KEY needed - Anthropic + embedding calls are mocked)
pytest tests/ -v
pytest tests/test_agent_loop.py -v                                    # single file
pytest tests/test_agent_loop.py::test_ask_marks_tool_error -v         # single test

# Lint + format (same checks CI runs)
ruff check .
ruff format --check .          # add --check-less `ruff format .` to auto-fix
```

## Architecture

This repo is **both** the AI onboarding tool *and* a deliberately minimal reference
implementation of the four pieces an agentic AI system needs. Reading any single file in
isolation will undersell how they connect - the call chain matters more than any one file:

```
cli.py (argparse: index/ask/chat)
  -> Agent (agent_loop.py)                          the tool-use loop
       -> McpToolClient (mcp_client.py)              spawns the MCP server as a subprocess,
            stdio JSON-RPC                           translates MCP tool schemas <-> Anthropic's
       -> AsyncAnthropic                             the actual LLM call (messages.create)
  -> mcp_server.py (separate process, started by McpToolClient.__aenter__)
       -> dispatches 8 tools to onboarding_agent/tools/*.py
            search_docs   -> retriever.py -> indexer.py (chromadb + sentence-transformers)
            read_file/list_files -> fs_tools.py
            git_log/git_diff -> git_tools.py
            run_tests/run_lint -> test_lint_tools.py
            open_draft_pr -> pr_tools.py
```

**Two separate repos are in play at all times: this one, and the "target repo" the agent
is pointed at.** Every tool function takes a `target_repo: Path` as its first argument and
operates *only* within it (`fs_tools.resolve_inside` enforces this - it's reused by
`pr_tools.open_draft_pr` for the same reason). The RAG index (`indexer.py`/`retriever.py`)
is built from the target repo's own markdown docs and persisted at
`<target_repo>/.onboarding_agent_index/` (a chromadb `PersistentClient`, telemetry
disabled), not from this repo's docs.

**The MCP server is a fresh subprocess per CLI invocation, not a long-running service.**
`McpToolClient.__aenter__` (`mcp_client.py`) launches
`python -m onboarding_agent.mcp_server --target-repo ... [--allow-pr]` and talks to it over
stdio for the lifetime of one `ask`/`chat` call. `build_server()` in `mcp_server.py` is
where the tool dispatch table actually lives (`TOOLS` list = schemas advertised to the
LLM; `handle_call_tool` = the if/elif that routes a tool name to its `tools/*.py`
implementation).

**Two-layer safety gate on `open_draft_pr`** (the only tool with real-world side effects):
the tool itself raises `PrNotAllowedError` unless the CLI was started with `--allow-pr`
(`mcp_server.py` passes `allow_pr` through from `cli.py`'s flag), *and* the system prompt
(`prompts.py`) instructs the model to summarize the proposed diff and get explicit human
confirmation in chat before ever calling the tool, even when the flag is set. Don't weaken
either layer independently when touching this path.

**`Agent._create_response` (`agent_loop.py`) wraps every Anthropic API call in a bounded
retry** (3 attempts, exponential backoff) for transient errors only -
`APIConnectionError` and `APIStatusError` with status 429/529/5xx. Anything else (bad
request, auth failure) raises immediately. `Agent.run_turn` separately caps the
tool-use loop itself at `_MAX_TOOL_ITERATIONS` (10) regardless of retries, so a model that
keeps calling tools without ever reaching `end_turn` still terminates.

**`run_tests`/`run_lint` (`test_lint_tools.py`) detect the target repo's toolchain from
project marker files**, not from this repo's own tooling - e.g. a target repo with
`package.json` gets `npm test`, one with `ruff.toml` or `[tool.ruff]` in `pyproject.toml`
gets `ruff check .`. When adding a new ecosystem, extend the relevant `_detect_*`/`_has_*`
helper rather than the dispatch site.

Tests mock the embedding model (`tests/conftest.py`'s `mock_embedding_model` fixture
patches `indexer.get_embedding_model`) and the Anthropic/MCP clients (`unittest.mock`), so
the whole suite runs offline with no API key.
