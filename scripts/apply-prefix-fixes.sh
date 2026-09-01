#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  apply-prefix-fixes.sh PREFIX [PATCHED_MCIWAVE_DLL]

Example:
  scripts/apply-prefix-fixes.sh ~/.wine-aim59 binaries/mciwave-wine9-x86-aim.dll

This script assumes AIM 5.9.3861 is already installed in:
  C:\Program Files\AIM
EOF
}

[[ $# -ge 1 && $# -le 2 ]] || { usage >&2; exit 2; }

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="$(realpath -m "$1")"
PATCH_DLL="${2:-$ROOT/binaries/mciwave-wine9-x86-aim.dll}"

exec python3 "$ROOT/aim59" patch-prefix \
    --non-interactive \
    --prefix "$PREFIX" \
    --patched-dll "$PATCH_DLL"
