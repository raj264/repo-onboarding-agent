import subprocess
from pathlib import Path

_MAX_DIFF_CHARS = 20_000


def _is_git_repo(target_repo: Path) -> bool:
    return (target_repo / ".git").exists()


def _run_git(target_repo: Path, args: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-C", str(target_repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return result.returncode, result.stderr.strip()
    return result.returncode, result.stdout


def git_log(target_repo: Path, path: str | None = None, n: int = 10) -> str:
    if not _is_git_repo(target_repo):
        return f"ERROR: {target_repo} is not a git repository."

    args = ["log", f"-{n}", "--oneline", "--no-color"]
    if path:
        args.extend(["--", path])

    returncode, output = _run_git(target_repo, args)
    if returncode != 0:
        return f"ERROR: git log failed: {output}"
    return output or "No commits found."


def git_diff(target_repo: Path, ref: str = "HEAD~1") -> str:
    if not _is_git_repo(target_repo):
        return f"ERROR: {target_repo} is not a git repository."

    returncode, output = _run_git(target_repo, ["diff", "--no-color", ref])
    if returncode != 0:
        return f"ERROR: git diff failed: {output}"

    if len(output) > _MAX_DIFF_CHARS:
        output = output[:_MAX_DIFF_CHARS] + f"\n... [truncated, diff exceeded {_MAX_DIFF_CHARS} chars]"
    return output or "No differences found."
