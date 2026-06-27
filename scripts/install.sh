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
cd "$(dirname "${BASH_SOURCE[0]}")/.."

VENV_DIR=".venv"

find_python() {
    for candidate in python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            local version
            version="$("$candidate" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
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
    echo "ERROR: no Python >=3.10 found (checked python3.12, python3.11, python3.10, python3)." >&2
    echo "Install one, e.g.: brew install python@3.12" >&2
    exit 1
}
echo "Using $PYTHON_BIN ($("$PYTHON_BIN" --version))."

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtualenv at $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt -e .

if [[ "${1:-}" == "--dev" ]]; then
    pip install -r requirements-dev.txt
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example - set ANTHROPIC_API_KEY before running 'ask'/'chat'."
fi

echo "Done. Activate with: source $VENV_DIR/bin/activate"
