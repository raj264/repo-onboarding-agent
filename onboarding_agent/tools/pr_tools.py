"""The one tool with real-world side effects: creates a branch, writes file changes,
commits, pushes, and opens a draft PR via the GitHub CLI (`gh`).

Gated by two independent layers - don't weaken either when touching this file:
1. `allow_pr` (passed in from the `--allow-pr` CLI flag) - this function refuses to run
   at all without it, regardless of what the LLM decides to do.
2. The system prompt (`prompts.py`) instructs the model to get explicit human
   confirmation in chat before ever calling this tool, even when `--allow-pr` is set.
"""

import re
import subprocess
from pathlib import Path

from onboarding_agent.tools.fs_tools import resolve_inside

_SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


class PrNotAllowedError(Exception):
    """Raised when `open_draft_pr` is called without `--allow-pr`."""


def _run(target_repo: Path, command: list[str], step: str) -> str:
    """Runs one step of the PR sequence (git/gh subcommand), raising with a clear
    `'<step>' failed: ...` message on non-zero exit instead of failing silently partway
    through the branch/commit/push/PR sequence.
    """
    result = subprocess.run(
        command,
        cwd=target_repo,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"'{step}' failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def open_draft_pr(
    target_repo: Path,
    title: str,
    body: str,
    branch_name: str,
    files: dict[str, str],
    allow_pr: bool,
) -> str:
    """Creates `branch_name`, writes/overwrites each path in `files` with its given
    content, commits with `title` as the message, pushes, and opens a draft PR.

    `files` maps repo-relative paths to *full* new file content (not a diff) - each path
    is validated via `resolve_inside` before anything is written, and `branch_name`
    against `_SAFE_BRANCH_RE` (alphanumeric, `.`, `_`, `/`, `-` only) before being passed
    to `git checkout -b`, since both ultimately reach `subprocess.run` argv.
    """
    if not allow_pr:
        raise PrNotAllowedError(
            "PR creation is disabled. Restart the agent with --allow-pr to enable this tool."
        )

    if not _SAFE_BRANCH_RE.match(branch_name):
        raise ValueError(f"Unsafe branch name: {branch_name!r}")

    # Resolve every path up front, before mutating anything, so a single bad path
    # aborts cleanly instead of leaving a half-written branch behind.
    resolved_paths = {}
    for relative_path in files:
        resolved_paths[relative_path] = resolve_inside(target_repo, relative_path)

    _run(target_repo, ["git", "checkout", "-b", branch_name], "git checkout -b")

    for relative_path, content in files.items():
        resolved = resolved_paths[relative_path]
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")

    _run(target_repo, ["git", "add", *files.keys()], "git add")
    _run(target_repo, ["git", "commit", "-m", title], "git commit")
    _run(target_repo, ["git", "push", "-u", "origin", branch_name], "git push")
    pr_output = _run(
        target_repo,
        ["gh", "pr", "create", "--draft", "--title", title, "--body", body, "--head", branch_name],
        "gh pr create",
    )

    # `gh pr create` prints the PR URL as its last line of stdout on success.
    url = pr_output.strip().splitlines()[-1] if pr_output.strip() else ""
    return url or "Draft PR created (URL not parsed from gh output)."
