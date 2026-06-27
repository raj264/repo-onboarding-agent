#!/usr/bin/env bash
# Removes .venv (and everything pip installed into it). Leaves .env and any indexed
# target repos untouched - this only undoes what install.sh created.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

VENV_DIR=".venv"

if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    echo "Removed $VENV_DIR."
else
    echo "$VENV_DIR not found, nothing to remove."
fi
