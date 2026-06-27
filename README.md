# Repo Onboarding Agent

[![CI](https://github.com/raj264/repo-onboarding-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/raj264/repo-onboarding-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](pyproject.toml)

Clone this once, then point it at *any* codebase to get an AI onboarding
assistant for that repo: it answers "how does X work" questions grounded in
that repo's own docs, can inspect git history and run tests/lint, and can
optionally draft a PR with a suggested fix.

It's also a small, complete demonstration of the four building blocks of an
AI system working together:

- **LLM** — Anthropic Claude is the reasoning brain.
- **RAG** — the target repo's markdown docs are chunked, embedded locally, and
  retrieved with `chromadb` + `sentence-transformers`.
- **MCP** — a Model Context Protocol server exposes git/filesystem/test/lint/PR
  tools as a standard connector layer.
- **Agent** — a tool-use loop ties the LLM to the MCP tools, deciding what to
  investigate and when to act. It's bounded on both sides: a capped number of
  tool-use iterations per turn, and a bounded exponential-backoff retry around
  the Anthropic call itself for transient rate-limit/overload errors.

## Architecture

```
CLI (argparse) -> Agent loop <-> Anthropic API (LLM, the brain)
                       |
                  MCP Client (stdio)
                       |
                  MCP Server (8 tools)
              /        |         \
        chromadb +   git/fs     pytest/lint/gh
        sentence-    tools      (run_tests, run_lint,
        transformers            open_draft_pr)
        (RAG over target
         repo's docs)
```

## Project Structure

```
repo-onboarding-agent/
├── onboarding_agent/
│   ├── cli.py            # argparse subcommands: index / ask / chat
│   ├── config.py         # model/embedding/chroma constants
│   ├── indexer.py        # markdown chunking + chromadb indexing
│   ├── retriever.py      # RAG search over the index
│   ├── mcp_server.py      # MCP server exposing 8 tools
│   ├── mcp_client.py      # MCP client (stdio) + Anthropic tool-schema adapter
│   ├── agent_loop.py      # Claude tool-use loop
│   ├── prompts.py         # system prompt
│   └── tools/             # fs, git, test/lint, docs, PR tool implementations
└── tests/                  # pytest suite (no API key required)
```

## Getting Started

### Prerequisites
- Python 3.10+
- `git`
- [GitHub CLI](https://cli.github.com/) (`gh`) — only needed for the `open_draft_pr` tool

### Install

```bash
git clone https://github.com/raj264/repo-onboarding-agent.git
cd repo-onboarding-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional, for the `onboarding-agent` command on your PATH:
pip install -e .
```

Contributing or running the test suite? Also install dev dependencies (pytest, ruff):

```bash
pip install -r requirements.txt -r requirements-dev.txt
# or: pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

### Use

```bash
onboarding-agent index <path-to-target-repo>
onboarding-agent ask <path-to-target-repo> "how does the retry logic work?"
onboarding-agent chat <path-to-target-repo>
```

Without `pip install -e .`, run the same commands via `python -m onboarding_agent.cli ...`.

`--allow-pr` enables the `open_draft_pr` tool (off by default). Even with the
flag set, the agent is instructed to summarize the proposed diff and ask for
your confirmation in chat before opening anything — this is a two-layer
safety gate (the tool itself also refuses to run without `--allow-pr`).

### Example session

```
$ onboarding-agent index ~/projects/some-target-repo
Indexed 14 markdown files (87 chunks).

$ onboarding-agent ask ~/projects/some-target-repo "how does the retry logic work in the ingestion pipeline?"
Looking at docs/architecture.md and the ingestion module...

The retry logic wraps each external call with exponential backoff: 3 attempts,
base delay 1s, doubling each time. Documented in docs/architecture.md under
"Retry Strategy".

$ onboarding-agent chat ~/projects/some-target-repo --allow-pr
you> the FAQ doc says the timeout is 30s but the code uses 60s, can you fix the doc?
assistant> I checked docs/faq.md and the code - you're right, the FAQ says 30s
but the code uses 60s. Proposed change to docs/faq.md:

  - The default timeout is 30 seconds.
  + The default timeout is 60 seconds.

Should I open a draft PR with this change? (yes/no)
you> yes
assistant> Opened draft PR: https://github.com/you/some-target-repo/pull/42
```

## MCP Tools Exposed

| Tool | Description |
|---|---|
| `search_docs` | RAG search over the target repo's indexed markdown docs |
| `read_file` | Read a file relative to the target repo root |
| `list_files` | List files matching a glob pattern |
| `git_log` | Recent commit history, optionally scoped to a path |
| `git_diff` | Diff against a given ref (default `HEAD~1`) |
| `run_tests` | Run the target repo's tests — detects pytest, npm test, go test, or cargo test from project markers |
| `run_lint` | Run ruff/flake8 (Python) or eslint (JS/TS) if configured in the target repo |
| `open_draft_pr` | Create a branch, commit changes, push, and open a draft PR (requires `--allow-pr`) |

## Design notes / limitations

A few deliberate scope decisions, not oversights:

- **RAG corpus is markdown-only.** `search_docs` indexes `.md`/`.markdown` files. Most
  repos document architecture decisions in markdown, and keeping the indexer to one
  format keeps chunking simple and predictable. Code itself is inspected directly via
  `read_file`/`list_files`/`git_log`/`git_diff` rather than embedded.
- **No reranking.** Retrieval is a single local embedding model (`all-MiniLM-L6-v2`) plus
  cosine similarity via chromadb — good enough for "find the right doc section," not
  tuned for precision-critical retrieval.
- **stdio transport only.** The MCP client/server pair talk over stdio (spawned
  subprocess), not HTTP/SSE — appropriate for a single-user local CLI, not for serving
  multiple concurrent agents against one target repo.
- **No cross-session memory.** Each `chat` invocation starts a fresh conversation; there's
  no persisted history across CLI runs. The RAG index, by contrast, *is* persisted
  (`.onboarding_agent_index/`) so it doesn't need rebuilding every run.

## Testing

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v

# lint + format check (same as CI)
ruff check .
ruff format --check .
```

No `ANTHROPIC_API_KEY` is needed to run the test suite — Anthropic and
embedding-model calls are mocked.

## License

MIT License — see [LICENSE](LICENSE).
