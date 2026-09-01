#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Checking shell syntax..."
while IFS= read -r -d '' f; do
    bash -n "$f"
done < <(find scripts -maxdepth 1 -type f -name '*.sh' -print0)

echo "Checking Lutris YAML..."
python3 scripts/validate-yaml.py

echo "Checking Python patcher..."
python3 -m compileall -q aim59_compat scripts tests
python3 -m unittest discover -s tests

echo "Checking release package..."
python3 scripts/build-patcher.py
python3 scripts/build-release.py
python3 scripts/verify-release.py

echo "Checking tracked published binary..."
scripts/verify-mciwave.sh binaries/mciwave-wine9-x86-aim.dll --published

echo "Checking SHA256SUMS..."
sha256sum -c checksums/SHA256SUMS

echo "Checking for proprietary AIM binaries..."
bad=0
while IFS= read -r -d '' f; do
    case "$f" in
        ./binaries/mciwave-wine9-x86-aim.dll)
            ;;
        *)
            echo "Unexpected Windows executable/binary in repository: $f" >&2
            bad=1
            ;;
    esac
done < <(
    git ls-files --cached --others --exclude-standard -z |
        while IFS= read -r -d '' f; do
            case "${f,,}" in
                *.exe|*.ocm|*.dll)
                    printf '%s\0' "./$f"
                    ;;
            esac
        done
)

if [[ $bad -ne 0 ]]; then
    exit 1
fi

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git diff --check
fi

echo "Repository verification passed."
