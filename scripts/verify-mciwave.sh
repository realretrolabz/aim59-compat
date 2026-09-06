#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 PATH_TO_MCIWAVE_DLL [--published]" >&2
    exit 2
fi

DLL="$1"
MODE="${2:-}"

if [[ -n "$MODE" && "$MODE" != "--published" ]]; then
    echo "Usage: $0 PATH_TO_MCIWAVE_DLL [--published]" >&2
    exit 2
fi

[[ -f "$DLL" ]] || {
    echo "Not found: $DLL" >&2
    exit 1
}

desc="$(file "$DLL")"
echo "$desc"
grep -q 'PE32' <<<"$desc" || {
    echo "FAIL: not PE32" >&2
    exit 1
}
grep -Eq 'Intel 80386|i386' <<<"$desc" || {
    echo "FAIL: not 32-bit x86" >&2
    exit 1
}

markers="$(strings "$DLL" | grep -E '^Wine (builtin|patched) DLL$' || true)"
echo "Marker:"
echo "${markers:-<none>}"

grep -qx 'Wine patched DLL' <<<"$markers" || {
    echo "FAIL: patched Wine marker missing" >&2
    exit 1
}

if grep -qx 'Wine builtin DLL' <<<"$markers"; then
    echo "FAIL: builtin marker still present" >&2
    exit 1
fi

echo "Imports:"
imports="$(objdump -p "$DLL" 2>/dev/null | awk '/DLL Name:/ {print tolower($3)}' | sort -u)"
echo "$imports"

for required in kernel32.dll ntdll.dll ucrtbase.dll user32.dll winmm.dll; do
    grep -qx "$required" <<<"$imports" || {
        echo "FAIL: expected import missing: $required" >&2
        exit 1
    }
done

sha="$(sha256sum "$DLL" | awk '{print $1}')"
echo "SHA256: $sha"

if [[ "$MODE" == "--published" ]]; then
    published_path="binaries/$(basename -- "$DLL")"
    expected="$({ awk -v path="$published_path" '$2 == path { print $1 }' "$ROOT/checksums/SHA256SUMS"; } || true)"
    if [[ -z "$expected" ]]; then
        echo "FAIL: no published checksum for $published_path" >&2
        exit 1
    fi
    if [[ "$sha" != "$expected" ]]; then
        echo "FAIL: published binary checksum mismatch" >&2
        exit 1
    fi
fi

echo "OK: mciwave DLL structural checks passed."
