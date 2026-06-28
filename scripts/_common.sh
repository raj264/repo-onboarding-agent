# shellcheck shell=bash
# Shared helpers sourced by the other scripts/*.sh files. Not meant to be run directly.

detect_os() {
    case "$(uname -s)" in
        Darwin) echo "macos" ;;
        Linux) echo "linux" ;;
        MINGW* | MSYS* | CYGWIN*) echo "windows" ;;
        *) echo "unknown" ;;
    esac
}

# venv layout differs by platform: POSIX puts the interpreter/scripts in bin/, Windows
# (even under Git Bash/MSYS, since it's still the native Windows `venv` module) in
# Scripts/. Usage: venv_bin_dir <os_kind> <venv_dir>
venv_bin_dir() {
    if [[ "$1" == "windows" ]]; then
        echo "$2/Scripts"
    else
        echo "$2/bin"
    fi
}
