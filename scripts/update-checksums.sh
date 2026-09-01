#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

sha256sum binaries/mciwave-wine9-x86-aim.dll > checksums/SHA256SUMS
cat checksums/SHA256SUMS
