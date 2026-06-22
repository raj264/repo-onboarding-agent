import subprocess
import sys
from pathlib import Path

_MAX_OUTPUT_CHARS = 20_000


def _truncate(text: str) -> str:
    if len(text) > _MAX_OUTPUT_CHARS:
        return text[:_MAX_OUTPUT_CHARS] + f"\n... [truncated at {_MAX_OUTPUT_CHARS} chars]"
    return text


def run_tests(target_repo: Path, path: str | None = None, timeout: int = 120) -> str:
    target = path or "tests"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", target, "-v"],
            cwd=target_repo,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: test run timed out after {timeout}s."
    except FileNotFoundError as exc:
        return f"ERROR: could not run pytest: {exc}"

    output = result.stdout + result.stderr
    return f"EXIT CODE: {result.returncode}\n{_truncate(output)}"


def run_lint(target_repo: Path) -> str:
    has_ruff_toml = (target_repo / "ruff.toml").exists() or (target_repo / ".ruff.toml").exists()
    pyproject = target_repo / "pyproject.toml"
    has_ruff_pyproject = pyproject.exists() and "[tool.ruff]" in pyproject.read_text(
        encoding="utf-8", errors="ignore"
    )

    if has_ruff_toml or has_ruff_pyproject:
        return _run_lint_command(target_repo, ["ruff", "check", "."])

    has_flake8_cfg = (target_repo / ".flake8").exists()
    setup_cfg = target_repo / "setup.cfg"
    has_flake8_setup_cfg = setup_cfg.exists() and "[flake8]" in setup_cfg.read_text(
        encoding="utf-8", errors="ignore"
    )

    if has_flake8_cfg or has_flake8_setup_cfg:
        return _run_lint_command(target_repo, ["flake8"])

    return "No lint config found in target repo."


def _run_lint_command(target_repo: Path, command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=target_repo,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return "ERROR: lint run timed out after 60s."
    except FileNotFoundError as exc:
        return f"ERROR: could not run linter ({' '.join(command)}): {exc}"

    output = result.stdout + result.stderr
    return f"EXIT CODE: {result.returncode}\n{_truncate(output)}"
