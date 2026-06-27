#!/usr/bin/env bash
# Clean rebuild: drop .venv and recreate it from scratch. Plain code edits are picked
# up automatically by the editable install and don't need this - run it after pulling
# changes that touch dependencies, the package version, or the console-script entry
# point, or after editing onboarding_agent/mcp_server.py if Claude Desktop/Code's MCP
# server (which points at .venv/bin/python) needs those changes installed. Forwards any
# arguments (e.g. --dev) to install.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/uninstall.sh"
"$SCRIPT_DIR/install.sh" "$@"
