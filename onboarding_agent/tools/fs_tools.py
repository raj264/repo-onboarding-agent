from pathlib import Path

_MAX_LIST_RESULTS = 500


def resolve_inside(target_repo: Path, relative_path: str) -> Path:
    target_repo = target_repo.resolve()
    candidate = (target_repo / relative_path).resolve()
    if candidate != target_repo and target_repo not in candidate.parents:
        raise ValueError(f"Path '{relative_path}' escapes the target repository.")
    return candidate


def read_file(target_repo: Path, path: str, max_bytes: int = 100_000) -> str:
    try:
        resolved = resolve_inside(target_repo, path)
    except ValueError as exc:
        return f"ERROR: {exc}"

    if not resolved.exists():
        return f"ERROR: File not found: {path}"
    if not resolved.is_file():
        return f"ERROR: Not a file: {path}"

    data = resolved.read_bytes()
    truncated = len(data) > max_bytes
    text = data[:max_bytes].decode("utf-8", errors="ignore")
    if truncated:
        text += f"\n... [truncated, file is {len(data)} bytes, showing first {max_bytes}]"
    return text


def list_files(target_repo: Path, glob_pattern: str = "**/*") -> list[str]:
    target_repo = target_repo.resolve()
    results = []
    for path in sorted(target_repo.glob(glob_pattern)):
        if not path.is_file():
            continue
        relative = path.relative_to(target_repo)
        if ".git" in relative.parts:
            continue
        results.append(relative.as_posix())
        if len(results) >= _MAX_LIST_RESULTS:
            results.append(f"... [truncated at {_MAX_LIST_RESULTS} results]")
            break
    return results
