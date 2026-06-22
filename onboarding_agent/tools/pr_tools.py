import re
import subprocess
from pathlib import Path

from onboarding_agent.tools.fs_tools import resolve_inside

_SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


class PrNotAllowedError(Exception):
    pass


def _run(target_repo: Path, command: list[str], step: str) -> str:
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
    if not allow_pr:
        raise PrNotAllowedError(
            "PR creation is disabled. Restart the agent with --allow-pr to enable this tool."
        )

    if not _SAFE_BRANCH_RE.match(branch_name):
        raise ValueError(f"Unsafe branch name: {branch_name!r}")

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

    url = pr_output.strip().splitlines()[-1] if pr_output.strip() else ""
    return url or "Draft PR created (URL not parsed from gh output)."
