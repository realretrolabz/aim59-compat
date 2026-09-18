#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  apply-prefix-fixes.sh PREFIX [PATCHED_MCIWAVE_DLL]

Example:
  scripts/apply-prefix-fixes.sh ~/.wine-aim59

This script assumes AIM 5.9.3861 is already installed in:
  C:\Program Files\AIM
EOF
}

[[ $# -ge 1 && $# -le 2 ]] || { usage >&2; exit 2; }

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="$(realpath -m "$1")"

command=(python3 "$ROOT/rrlzAIMlinux" patch-prefix \
    --non-interactive \
    --prefix "$PREFIX")

if [[ $# -eq 2 ]]; then
    command+=(--patched-dll "$(realpath -m "$2")")
fi

exec "${command[@]}"
