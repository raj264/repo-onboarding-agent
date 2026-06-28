#!/usr/bin/env bash
# Creates (or reuses) .venv, installs runtime deps + this package in editable mode,
# and seeds .env from .env.example if it doesn't exist yet. Pass --dev to also install
# requirements-dev.txt (pytest, ruff) for contributing/testing.
#
# Picks an explicit Python >=3.10 rather than trusting a bare `python3` - on macOS in
# particular, `python3` commonly resolves to Apple's stock 3.9, which is too old for
# this project's `mcp` dependency (and for the local hook that auto-activates .venv on
# cd, which would otherwise make a once-broken venv self-perpetuating on every rebuild).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
# shellcheck source=scripts/_common.sh
source "$SCRIPT_DIR/_common.sh"

VENV_DIR=".venv"

# Detected once per install run (not cached to disk - it's a few milliseconds of
# `uname`, not worth persisting) and used to pick the right venv layout, Python
# candidates, and which OS-specific fixups below actually apply.
OS_KIND="$(detect_os)"
echo "Detected OS: $OS_KIND ($(uname -s))"
VENV_BIN="$(venv_bin_dir "$OS_KIND" "$VENV_DIR")"

find_python() {
    local candidates=(python3.12 python3.11 python3.10 python3)
    # The official python.org Windows installer (and many Git Bash setups) expose the
    # `py` launcher rather than versioned `python3.x` binaries on PATH.
    if [[ "$OS_KIND" == "windows" ]]; then
        candidates=(py "${candidates[@]}" python)
    fi
    for candidate in "${candidates[@]}"; do
        if command -v "$candidate" >/dev/null 2>&1; then
            local version
            version="$("$candidate" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null)" || continue
            local major="${version%%.*}"
            local minor="${version#*.}"
            if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
                command -v "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_BIN="$(find_python)" || {
    echo "ERROR: no Python >=3.10 found (checked python3.12, python3.11, python3.10, python3$([[ "$OS_KIND" == "windows" ]] && echo ", py, python"))." >&2
    case "$OS_KIND" in
        macos) echo "Install one, e.g.: brew install python@3.12" >&2 ;;
        linux) echo "Install one via your package manager, e.g.: apt install python3.12" >&2 ;;
        windows) echo "Install one from https://python.org/downloads/ or: winget install Python.Python.3.12" >&2 ;;
        *) echo "Install Python 3.10+ for your platform." >&2 ;;
    esac
    exit 1
}
echo "Using $PYTHON_BIN ($("$PYTHON_BIN" --version))."

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtualenv at $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_BIN/activate"
pip install --upgrade pip
pip install -r requirements.txt -e .

if [[ "${1:-}" == "--dev" ]]; then
    pip install -r requirements-dev.txt
fi

# macOS (notably under iCloud-synced folders like ~/Desktop) sometimes applies the
# UF_HIDDEN flag to setuptools' generated editable-install shim files. Python 3.12+'s
# site.py silently skips hidden .pth files, which breaks the editable install (pip
# reports success, but `import onboarding_agent` only works by the accident of cwd
# already being the repo root). Clear it defensively so the console script works.
if [[ "$OS_KIND" == "macos" ]] && command -v chflags >/dev/null 2>&1; then
    find "$VENV_DIR" -flags +hidden -exec chflags nohidden {} + 2>/dev/null || true
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example - set ANTHROPIC_API_KEY before running 'ask'/'chat'."
fi

echo "Done. Activate with: source $VENV_BIN/activate"
