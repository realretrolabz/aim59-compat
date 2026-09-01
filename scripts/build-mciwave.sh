#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WINE_VERSION="${WINE_VERSION:-9.0}"
CACHE_DIR="${CACHE_DIR:-$ROOT/.cache}"
BUILD_ROOT="${BUILD_ROOT:-$ROOT/.build}"
DIST_DIR="${DIST_DIR:-$ROOT/dist}"
SOURCE_ARCHIVE="$CACHE_DIR/wine-$WINE_VERSION.tar.xz"
SOURCE_DIR="$BUILD_ROOT/wine-$WINE_VERSION"
BUILD_DIR="$BUILD_ROOT/wine-$WINE_VERSION-build-pe32"
PATCH_FILE="$ROOT/patches/wine-9.0-mciwave-aim.patch"
OUTPUT="$DIST_DIR/mciwave-wine9-x86-aim.dll"

if [[ "$WINE_VERSION" != "9.0" ]]; then
    echo "This patch is validated only for Wine 9.0." >&2
    exit 2
fi

for cmd in curl tar patch make python3 file strings i686-w64-mingw32-gcc; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "Missing required command: $cmd" >&2
        exit 1
    }
done

mkdir -p "$CACHE_DIR" "$BUILD_ROOT" "$DIST_DIR"

if [[ ! -f "$SOURCE_ARCHIVE" ]]; then
    echo "Downloading Wine $WINE_VERSION source..."
    curl -L --fail --show-error \
        "https://dl.winehq.org/wine/source/9.0/wine-$WINE_VERSION.tar.xz" \
        -o "$SOURCE_ARCHIVE"
fi

rm -rf "$SOURCE_DIR" "$BUILD_DIR"
tar -xf "$SOURCE_ARCHIVE" -C "$BUILD_ROOT"

echo "Applying AIM MCI compatibility patch..."
patch -d "$SOURCE_DIR" -p1 < "$PATCH_FILE"

mkdir -p "$BUILD_DIR"
pushd "$BUILD_DIR" >/dev/null

"$SOURCE_DIR/configure" \
    --enable-archs=i386 \
    --disable-tests

make -j"$(nproc)" -C dlls/mciwave

BUILT="$BUILD_DIR/dlls/mciwave/i386-windows/mciwave.dll"
[[ -f "$BUILT" ]] || {
    echo "Expected build output not found: $BUILT" >&2
    exit 1
}

cp "$BUILT" "$OUTPUT"

python3 - "$OUTPUT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
data = path.read_bytes()
old = b"Wine builtin DLL"
new = b"Wine patched DLL"

count = data.count(old)
if count != 1:
    raise SystemExit(f"Expected exactly one Wine builtin marker, found {count}")

if len(old) != len(new):
    raise SystemExit("Replacement marker length mismatch")

path.write_bytes(data.replace(old, new, 1))
PY

popd >/dev/null

"$ROOT/scripts/verify-mciwave.sh" "$OUTPUT"

echo
echo "Built: $OUTPUT"
sha256sum "$OUTPUT"
