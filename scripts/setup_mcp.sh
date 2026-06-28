#!/usr/bin/env bash
# Wires this repo's MCP server up for a given target repo, fully dynamically - no
# placeholder paths to hand-edit. Resolves this repo's venv python and the target
# repo's absolute path, then:
#   1. merges an entry into Claude Desktop's claude_desktop_config.json (macOS/Windows
#      only - there's no official Claude Desktop client on Linux), backing up the
#      existing file first.
#   2. registers the server with Claude Code via `claude mcp add`, if the `claude` CLI
#      is on PATH.
#
# The server name is derived from the target repo's folder name (e.g.
# "onboarding-myproject"), not a single fixed "repo-onboarding-agent" slot - so
# pointing this at multiple repos creates multiple independent entries instead of each
# one overwriting the last.
#
# Usage: ./scripts/setup_mcp.sh <path-to-target-repo> [--allow-pr]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=scripts/_common.sh
source "$SCRIPT_DIR/_common.sh"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <path-to-target-repo> [--allow-pr]" >&2
    exit 1
fi

TARGET_REPO_ARG="$1"
ALLOW_PR=false
for arg in "$@"; do
    [[ "$arg" == "--allow-pr" ]] && ALLOW_PR=true
done

OS_KIND="$(detect_os)"
VENV_BIN="$(venv_bin_dir "$OS_KIND" "$REPO_ROOT/.venv")"
VENV_PYTHON="$VENV_BIN/python"
if [[ "$OS_KIND" == "windows" && ! -f "$VENV_PYTHON" ]]; then
    VENV_PYTHON="$VENV_BIN/python.exe"
fi

if [ ! -x "$VENV_PYTHON" ] && [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: $VENV_PYTHON not found. Run ./scripts/install.sh first." >&2
    exit 1
fi

if [ ! -d "$TARGET_REPO_ARG" ]; then
    echo "ERROR: target repo not found: $TARGET_REPO_ARG" >&2
    exit 1
fi
TARGET_REPO_ABS="$("$VENV_PYTHON" -c "import os, sys; print(os.path.abspath(sys.argv[1]))" "$TARGET_REPO_ARG")"

# Derive a per-target server name (e.g. "onboarding-myproject") instead of a single fixed
# slot, so each target repo gets its own independent entry rather than overwriting the
# previous one.
TARGET_BASENAME="$(basename "$TARGET_REPO_ABS")"
SERVER_NAME="onboarding-$(echo "$TARGET_BASENAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"

echo "Detected OS:  $OS_KIND"
echo "Venv python:  $VENV_PYTHON"
echo "Target repo:  $TARGET_REPO_ABS"
echo "Server name:  $SERVER_NAME"
echo "--allow-pr:   $ALLOW_PR"
echo

# --- Claude Desktop: merge an mcpServers entry into the real config file ---
case "$OS_KIND" in
    macos)   DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json" ;;
    windows) DESKTOP_CONFIG="${APPDATA:-$HOME/AppData/Roaming}/Claude/claude_desktop_config.json" ;;
    *)       DESKTOP_CONFIG="" ;;
esac

if [ -n "$DESKTOP_CONFIG" ]; then
    mkdir -p "$(dirname "$DESKTOP_CONFIG")"
    if [ -f "$DESKTOP_CONFIG" ]; then
        BACKUP="$DESKTOP_CONFIG.bak.$(date +%Y%m%d%H%M%S)"
        cp "$DESKTOP_CONFIG" "$BACKUP"
        echo "Backed up existing config to $BACKUP"
    fi
    "$VENV_PYTHON" - "$DESKTOP_CONFIG" "$VENV_PYTHON" "$TARGET_REPO_ABS" "$ALLOW_PR" "$SERVER_NAME" <<'PYEOF'
import json
import pathlib
import sys

config_path, venv_python, target_repo, allow_pr, server_name = sys.argv[1:6]
path = pathlib.Path(config_path)
existing_text = path.read_text() if path.exists() else ""
config = json.loads(existing_text) if existing_text.strip() else {}
config.setdefault("mcpServers", {})

args = ["-m", "onboarding_agent.mcp_server", "--target-repo", target_repo]
if allow_pr == "true":
    args.append("--allow-pr")

config["mcpServers"][server_name] = {"command": venv_python, "args": args}
path.write_text(json.dumps(config, indent=2) + "\n")
print(f"Wrote {path} (server: {server_name})")
PYEOF
else
    echo "No Claude Desktop client on $OS_KIND - skipping claude_desktop_config.json."
fi

echo

# --- Claude Code: register via its own CLI, no file-editing needed ---
if command -v claude >/dev/null 2>&1; then
    CMD=(claude mcp add "$SERVER_NAME" -- "$VENV_PYTHON" -m onboarding_agent.mcp_server --target-repo "$TARGET_REPO_ABS")
    [[ "$ALLOW_PR" == "true" ]] && CMD+=(--allow-pr)
    echo "Registering with Claude Code: ${CMD[*]}"
    "${CMD[@]}" || echo "claude mcp add reported an issue above (e.g. already registered)."
else
    echo "Claude Code CLI ('claude') not found on PATH - skipping registration."
fi

echo
echo "Done. Restart Claude Desktop (if applicable) for the change to take effect."
