#!/usr/bin/env bash
set -euo pipefail

# Cross-build the native Windows setup with Mono. The produced
# managed PE executable must still be tested on Windows; this command does not
# validate UAC, the Windows registry, or the original AIM installer workflow.

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIRECTORY="$ROOT/.build/windows-exe"
OUTPUT_PATH="$OUTPUT_DIRECTORY/rrlzAIM.exe"
ICON_PATH="$ROOT/windows/AIM59Setup/assets/aim59-setup.ico"
SOURCES=(
    "$ROOT/windows/AIM59Setup/Program.cs"
    "$ROOT/windows/AIM59Setup/NativeWorkflow.cs"
)

if ! command -v mono-csc >/dev/null 2>&1; then
    echo "mono-csc was not found. On Debian/Ubuntu install mono-devel, then retry." >&2
    exit 1
fi

for source in "${SOURCES[@]}"; do
    if [[ ! -f "$source" ]]; then
        echo "C# source file was not found: $source" >&2
        exit 1
    fi
done

if [[ ! -f "$ICON_PATH" ]]; then
    echo "Windows icon was not found: $ICON_PATH" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIRECTORY"

unexpected="$(find "$OUTPUT_DIRECTORY" -maxdepth 1 -type f ! -name 'rrlzAIM.exe' -print -quit)"
if [[ -n "$unexpected" ]]; then
    echo "Refusing to write beside unexpected build output: $unexpected" >&2
    exit 1
fi

mono-csc \
    -nologo \
    -target:winexe \
    -platform:anycpu \
    -optimize+ \
    -debug- \
    "-out:$OUTPUT_PATH" \
    "-win32icon:$ICON_PATH" \
    -r:System.dll \
    -r:System.Core.dll \
    -r:System.Drawing.dll \
    -r:System.Windows.Forms.dll \
    "${SOURCES[@]}"

if [[ ! -s "$OUTPUT_PATH" ]]; then
    echo "rrlzAIM.exe was not built." >&2
    exit 1
fi

echo "Built: $OUTPUT_PATH"
