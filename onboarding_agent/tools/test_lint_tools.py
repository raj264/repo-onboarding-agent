import subprocess
import sys
from pathlib import Path

_MAX_OUTPUT_CHARS = 20_000


def _truncate(text: str) -> str:
    if len(text) > _MAX_OUTPUT_CHARS:
        return text[:_MAX_OUTPUT_CHARS] + f"\n... [truncated at {_MAX_OUTPUT_CHARS} chars]"
    return text


def _run_command(target_repo: Path, command: list[str], timeout: int, label: str) -> str:
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


def _has_eslint_config(target_repo: Path) -> bool:
    if any((target_repo / name).exists() for name in (".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintrc.yml")):
        return True
    package_json = target_repo / "package.json"
    return package_json.exists() and "eslintConfig" in package_json.read_text(encoding="utf-8", errors="ignore")


def run_lint(target_repo: Path) -> str:
    if _has_ruff_config(target_repo):
        return _run_command(target_repo, ["ruff", "check", "."], 60, "lint")
    if _has_flake8_config(target_repo):
        return _run_command(target_repo, ["flake8"], 60, "lint")
    if _has_eslint_config(target_repo):
        return _run_command(target_repo, ["npx", "eslint", "."], 60, "lint")
    return "No lint config found in target repo."
