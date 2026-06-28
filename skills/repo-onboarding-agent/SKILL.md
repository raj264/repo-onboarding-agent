---
name: repo-onboarding-agent
description: Use this project's onboarding MCP tools (search_docs, git_log, git_diff, run_tests, run_lint, open_draft_pr) instead of guessing when a question is about how the current codebase works, its recent history, or whether its tests/lint pass. Applies once the repo-onboarding-agent MCP server is connected (check with /mcp).
---

# repo-onboarding-agent

This plugin connects an MCP server (`repo-onboarding-agent`) scoped to the
current project -- check with `/mcp` that it shows as connected before relying
on the guidance below. If it's not connected, see "If the MCP server isn't
connected" further down.

## When to prefer these tools over your own Bash/Grep/Read

- **`search_docs`** -- a semantic (RAG) search over this project's own
  markdown documentation, not a literal grep. Prefer it for "how does X work"
  or "where is Y documented" questions, especially when the user's wording
  doesn't match the docs' exact terms -- that's exactly the case grep misses
  and RAG catches. It only searches markdown; for non-doc source code,
  reading the code directly is still more reliable than RAG.
- **`run_tests`** / **`run_lint`** -- detect this project's actual toolchain
  from its marker files (pytest/npm/go/cargo for tests; ruff/flake8/eslint
  for lint) rather than assuming one. Prefer these over hand-rolling the
  command yourself when you're not sure which runner applies.
- **`git_log`** / **`git_diff`** -- equivalent to running the git CLI
  directly; use whichever is more convenient in context, there's no behavior
  difference worth choosing one over the other for.
- **`read_file`** / **`list_files`** -- redundant with your own Read/Glob
  tools; no reason to prefer these specifically.

## `open_draft_pr` -- real-world side effects, confirm before calling

This tool creates a branch, commits the given file changes, pushes, and opens
a **draft** pull request via `gh`. Two independent gates apply:
- It's disabled by default. The plugin's bundled MCP config does not pass
  `--allow-pr`, so calling it will raise `PrNotAllowedError` unless the user
  has separately registered the server with `--allow-pr` themselves
  (`./scripts/setup_mcp.sh <target-repo> --allow-pr` in this repo's own
  checkout -- not something the plugin install does for them).
- Even when enabled, **always summarize the exact proposed file changes in
  plain chat text and get an explicit "yes" from the user in their next
  message before calling this tool.** Never call it speculatively or as part
  of a larger plan the user hasn't confirmed line-by-line.

## If the MCP server isn't connected

This plugin's bundled `.mcp.json` scopes the server to whatever project
Claude Code is rooted at when the plugin loads (`${CLAUDE_PROJECT_DIR}`) --
so it should "just work" without extra setup. If `/mcp` shows it as Failed
with a literal `${CLAUDE_PLUGIN_ROOT}` or `${CLAUDE_PROJECT_DIR}` string in
the error, that variable wasn't substituted by this Claude Code build (a
known issue in some non-CLI builds); tell the user to run
`./scripts/setup_mcp.sh <this-project's-path>` from inside a checkout of
https://github.com/raj264/repo-onboarding-agent instead, which registers the
same server with a hardcoded absolute path and has no such issue.
