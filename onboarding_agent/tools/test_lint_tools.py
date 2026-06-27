"""Runs the *target* repo's own test suite / linter - detected from project marker
files, not from this tool's own tooling. `run_tests`/`run_lint` work on whatever
language/ecosystem the target repo uses, as long as it's one of the ones detected below.
"""

import subprocess
import sys
from pathlib import Path

_MAX_OUTPUT_CHARS = 20_000


def _truncate(text: str) -> str:
    if len(text) > _MAX_OUTPUT_CHARS:
        return text[:_MAX_OUTPUT_CHARS] + f"\n... [truncated at {_MAX_OUTPUT_CHARS} chars]"
    return text


def _run_command(target_repo: Path, command: list[str], timeout: int, label: str) -> str:
    """Runs `command` in `target_repo`, turning timeouts/missing-executable errors into
    plain result strings (rather than exceptions) so the agent always gets *something*
    useful back instead of a crash.
    """
    try:
        result = subprocess.run(
            command,
            cwd=target_repo,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: {label} timed out after {timeout}s."
    except FileNotFoundError as exc:
        return f"ERROR: could not run {label} ({' '.join(command)}): {exc}"

    output = result.stdout + result.stderr
    return f"EXIT CODE: {result.returncode}\n{_truncate(output)}"


def _detect_test_command(target_repo: Path, path: str | None) -> list[str] | None:
    """Picks a test runner from project marker files, in this priority order: Python
    (pyproject.toml/setup.py/requirements.txt) > npm (package.json) > go (go.mod) >
    cargo (Cargo.toml). Returns None if none of these markers are present.
    """
    if (
        (target_repo / "pyproject.toml").exists()
        or (target_repo / "setup.py").exists()
        or (target_repo / "requirements.txt").exists()
    ):
        return [sys.executable, "-m", "pytest", path or "tests", "-v"]
    if (target_repo / "package.json").exists():
        return ["npm", "test"]
    if (target_repo / "go.mod").exists():
        return ["go", "test", "./..."]
    if (target_repo / "Cargo.toml").exists():
        return ["cargo", "test"]
    return None


def run_tests(target_repo: Path, path: str | None = None, timeout: int = 120) -> str:
    """Runs the target repo's detected test command. `path` only narrows pytest runs
    (the other runners don't take a comparable per-path argument here).
    """
    command = _detect_test_command(target_repo, path)
    if command is None:
        return (
            "No recognized test runner found in target repo "
            "(looked for pytest, npm test, go test, cargo test)."
        )
    return _run_command(target_repo, command, timeout, "tests")


def _has_ruff_config(target_repo: Path) -> bool:
    if (target_repo / "ruff.toml").exists() or (target_repo / ".ruff.toml").exists():
        return True
    pyproject = target_repo / "pyproject.toml"
    return pyproject.exists() and "[tool.ruff]" in pyproject.read_text(encoding="utf-8", errors="ignore")


def _has_flake8_config(target_repo: Path) -> bool:
    if (target_repo / ".flake8").exists():
        return True
    setup_cfg = target_repo / "setup.cfg"
    return setup_cfg.exists() and "[flake8]" in setup_cfg.read_text(encoding="utf-8", errors="ignore")


_ESLINT_CONFIG_NAMES = (
    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.js",
    ".eslintrc.yml",
    # Flat config, the default format since ESLint v9 (mid-2024).
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    "eslint.config.ts",
)


def _has_eslint_config(target_repo: Path) -> bool:
    if any((target_repo / name).exists() for name in _ESLINT_CONFIG_NAMES):
        return True
    package_json = target_repo / "package.json"
    return package_json.exists() and "eslintConfig" in package_json.read_text(
        encoding="utf-8", errors="ignore"
    )


def run_lint(target_repo: Path) -> str:
    """Picks a linter from config files present in the target repo, in priority order
    ruff > flake8 > eslint, and runs it. Returns a plain message (not an error) if none
    of those configs are found - a missing lint config isn't a failure.
    """
    if _has_ruff_config(target_repo):
        return _run_command(target_repo, ["ruff", "check", "."], 60, "lint")
    if _has_flake8_config(target_repo):
        return _run_command(target_repo, ["flake8"], 60, "lint")
    if _has_eslint_config(target_repo):
        return _run_command(target_repo, ["npx", "eslint", "."], 60, "lint")
    return "No lint config found in target repo."
