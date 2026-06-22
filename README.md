# Repo Onboarding Agent

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
  investigate and when to act.

## Architecture

```
CLI (argparse) -> Agent loop <-> Anthropic API (LLM, the brain)
                       |
                  MCP Client (stdio)
                       |
                  MCP Server (7 tools)
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
│   ├── mcp_server.py      # MCP server exposing 7 tools
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
| `run_tests` | Run pytest in the target repo |
| `run_lint` | Run ruff/flake8 if configured in the target repo |
| `open_draft_pr` | Create a branch, commit changes, push, and open a draft PR (requires `--allow-pr`) |

## Testing

```bash
pip install -r requirements.txt
pytest tests/ -v
```

No `ANTHROPIC_API_KEY` is needed to run the test suite — Anthropic and
embedding-model calls are mocked.

## License

MIT License — see [LICENSE](LICENSE).
