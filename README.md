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

## Quickstart

```bash
git clone https://github.com/raj264/repo-onboarding-agent.git && cd repo-onboarding-agent
./scripts/install.sh           # creates .venv, installs deps + this package, seeds .env
source .venv/bin/activate
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...

onboarding-agent index ~/path/to/some-target-repo
onboarding-agent ask ~/path/to/some-target-repo "how does the retry logic work?"
```

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
├── scripts/                # see table below
└── tests/                  # pytest suite (no API key required)
```

| Script | Purpose |
|---|---|
| `install.sh [--dev]` | Detects OS + a Python ≥3.10, creates `.venv`, installs runtime deps in editable mode (`--dev` adds pytest/ruff), seeds `.env`. |
| `uninstall.sh` | Removes `.venv`. Nothing else (`.env`, indexed target repos) is touched. |
| `reinstall.sh [--dev]` | Runs `uninstall.sh` then `install.sh` back to back — a clean rebuild after dependency/version/entry-point changes. |
| `setup_mcp.sh <target-repo> [--allow-pr]` | Wires this repo's MCP server into Claude Desktop's config and Claude Code, dynamically, for the given target repo. |
| `_common.sh` | Shared OS-detection helpers sourced by the scripts above — not meant to be run directly. |

## Getting Started

### Prerequisites
- Python 3.10+
- `git`
- [GitHub CLI](https://cli.github.com/) (`gh`) — only needed for the `open_draft_pr` tool

### Install

```bash
git clone https://github.com/raj264/repo-onboarding-agent.git
cd repo-onboarding-agent
./scripts/install.sh
```

The script detects the OS once at the start (`Detected OS: macos/linux/windows`) and
adapts accordingly: it picks a Python >=3.10 interpreter (trying `python3.12`/`3.11`/
`3.10`/`python3`, plus the `py` launcher and bare `python` on Windows — a bare `python3`
is often Apple's stock 3.9 on macOS, or simply absent on Windows), uses the right venv
layout (`bin/` on macOS/Linux, `Scripts/` on Windows), and only runs the macOS-specific
hidden-file fixup (see Troubleshooting below) when actually on macOS. It then creates
`.venv` and installs this package in editable mode so the `onboarding-agent` command and
live code edits both work. Native Windows requires running the script via Git Bash, WSL,
or another bash-compatible shell (it's a `.sh` script, not `.ps1`/`.bat`).

Contributing or running the test suite? Pass `--dev` to also install dev dependencies
(pytest, ruff):

```bash
./scripts/install.sh --dev
```

Prefer doing it by hand instead of the script:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -e .
# add dev deps: pip install -r requirements-dev.txt   (or: pip install -e ".[dev]")
```

**Uninstall / reinstall:** `scripts/uninstall.sh` removes `.venv` (nothing else is
touched — `.env` and any indexed target repos are left alone). `scripts/reinstall.sh`
runs uninstall then install back to back (forwarding `--dev`) for a clean rebuild —
useful after pulling changes that touch dependencies, the package version, or the
console-script entry point, or after editing `mcp_server.py` if a Claude Desktop/Code
config (below) needs those changes installed into the venv it points at.

**Troubleshooting `ModuleNotFoundError: No module named 'onboarding_agent'`:** on
macOS, folders under iCloud-synced locations (e.g. `~/Desktop`) can have the OS apply
the hidden-file flag to the editable install's generated shim files, which Python's
`site` module silently skips — breaking the install even though `pip` reported
success. `install.sh` clears this flag automatically, but it can recur if iCloud
re-syncs the folder; if you hit this, just re-run `./scripts/install.sh`.

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

### Use as an MCP server inside Claude Desktop / Claude Code

No separate install — the MCP server is the same package you already set up in
[Install](#install) above (`mcp` is a regular runtime dependency); it's just a
different entry point (`python -m onboarding_agent.mcp_server` instead of the
`onboarding-agent` CLI), so make sure you've run the Install steps first.

The CLI above runs its own Agent loop, calling the Anthropic API directly
(`ANTHROPIC_API_KEY` required). The same 8 tools can instead be plugged straight
into Claude Desktop or Claude Code as an MCP server — Claude itself becomes the
agent loop, so **no `ANTHROPIC_API_KEY` is needed for this repo** in that mode
(you can skip [Configure](#configure) entirely if this is the only way you plan
to use it).

**`scripts/setup_mcp.sh <path-to-target-repo> [--allow-pr]`** wires this up with no
placeholder paths to hand-edit — it resolves this repo's venv python and the target
repo's absolute path dynamically, derives a server name from the target repo's folder
(e.g. `onboarding-myproject`, not a single shared slot — pointing it at multiple repos
creates multiple independent entries instead of each one overwriting the last), then:
- merges that entry into Claude Desktop's `claude_desktop_config.json` (macOS/Windows;
  there's no official Desktop client on Linux, so this step is skipped there), backing
  up the existing file first;
- registers the same server with Claude Code via `claude mcp add`, if the `claude` CLI
  is on PATH.

```bash
./scripts/setup_mcp.sh ~/projects/some-target-repo
./scripts/setup_mcp.sh ~/projects/some-target-repo --allow-pr   # also enable open_draft_pr
```

Restart Claude Desktop / re-run `claude` after this for the change to take effect, then
just ask things like *"use search_docs to explain how the retry logic works in this
repo."* The two-layer safety gate on `open_draft_pr` still applies regardless of
`--allow-pr` (Claude is instructed via the tool's own description to confirm with you in
chat before opening anything).

<details>
<summary>What the script writes (manual equivalent, if you'd rather not run it)</summary>

```json
{
  "mcpServers": {
    "onboarding-<target-repo-folder-name>": {
      "command": "/absolute/path/to/repo-onboarding-agent/.venv/bin/python",
      "args": [
        "-m", "onboarding_agent.mcp_server",
        "--target-repo", "/absolute/path/to/target-repo"
      ]
    }
  }
}
```

For Claude Code directly: `claude mcp add onboarding-<target-repo-folder-name> -- /absolute/path/to/repo-onboarding-agent/.venv/bin/python -m onboarding_agent.mcp_server --target-repo /absolute/path/to/target-repo`

Either way, use the venv's `python` directly (not a bare `python`/`python3`) since
Desktop/Code spawn the process without your shell's virtualenv activation.
</details>

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
- **Platform support is honest, not aspirational.** CI (`ci.yml`) only runs on
  `ubuntu-latest` — Linux is the one platform with continuous verification. macOS has
  been hand-verified (and needed real fixes: an iCloud-sync hidden-file quirk breaking
  editable installs, plus `transformers`/`numpy` pins for PyTorch's macOS x86_64 wheel
  ceiling — see `requirements.txt` and `scripts/install.sh`), but isn't in CI, so a
  regression there wouldn't be caught automatically. Windows has OS-detection support in
  `scripts/*.sh` (via Git Bash/WSL) but has never been run on an actual Windows machine.

## Testing

```bash
./scripts/install.sh --dev
source .venv/bin/activate
pytest tests/ -v

# lint + format check (same as CI)
ruff check .
ruff format --check .
shellcheck -x scripts/*.sh   # lints the install/uninstall/reinstall/setup_mcp scripts
```

No `ANTHROPIC_API_KEY` is needed to run the test suite — Anthropic and
embedding-model calls are mocked.

## License

MIT License — see [LICENSE](LICENSE).
