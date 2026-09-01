#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath


root = Path(__file__).resolve().parents[1]
version = (root / "VERSION").read_text(encoding="utf-8").strip()
dist = root / "dist"
archive = dist / f"aim59-compat-{version}-linux.tar.gz"
bundle_root = PurePosixPath(f"aim59-compat-{version}")
allowed_dll = "mciwave-wine9-x86-aim.dll"

metadata = json.loads((root / "project.json").read_text(encoding="utf-8"))
if metadata.get("version") != version:
    raise SystemExit("project.json and VERSION disagree")

version_check = subprocess.run(
    [sys.executable, str(dist / "aim59-patcher.pyz"), "--version"],
    check=True,
    capture_output=True,
    text=True,
)
if version_check.stdout.strip() != f"aim59 {version}":
    raise SystemExit("Built patcher and VERSION disagree")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


release_sums: dict[str, str] = {}
for line in (dist / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
    checksum, filename = line.split("  ", 1)
    release_sums[filename] = checksum

expected_release_files = {
    "aim59-patcher.pyz",
    allowed_dll,
    "aim-5.9.3861.yml",
    archive.name,
}
if set(release_sums) != expected_release_files:
    raise SystemExit("dist/SHA256SUMS does not list the exact release payload")
for filename, expected in release_sums.items():
    if digest_file(dist / filename) != expected:
        raise SystemExit(f"Release checksum mismatch: {filename}")

with tarfile.open(archive, "r:gz") as source:
    members = {PurePosixPath(member.name): member for member in source.getmembers()}
    launcher_path = bundle_root / "aim59"
    dll_path = bundle_root / allowed_dll
    sums_path = bundle_root / "SHA256SUMS"
    for required in (launcher_path, dll_path, sums_path, bundle_root / "SOURCE.md"):
        if required not in members:
            raise SystemExit(f"Terminal bundle is missing {required}")
    if members[launcher_path].mode & 0o111 == 0:
        raise SystemExit("Terminal bundle launcher is not executable")

    for member_path in members:
        lowered = member_path.name.lower()
        if lowered.endswith((".exe", ".ocm")):
            raise SystemExit(f"Proprietary-looking binary in terminal bundle: {member_path}")
        if lowered.endswith(".dll") and lowered != allowed_dll:
            raise SystemExit(f"Unexpected DLL in terminal bundle: {member_path}")

    def member_bytes(path: PurePosixPath) -> bytes:
        extracted = source.extractfile(members[path])
        if extracted is None:
            raise SystemExit(f"Unable to read bundle member: {path}")
        return extracted.read()

    launcher = member_bytes(launcher_path)
    dll = member_bytes(dll_path)
    if not launcher.startswith(b"#!/usr/bin/env python3"):
        raise SystemExit("Terminal bundle launcher is not the Python zip application")

    internal_sums: dict[str, str] = {}
    for line in io.BytesIO(member_bytes(sums_path)).read().decode("utf-8").splitlines():
        checksum, filename = line.split("  ", 1)
        internal_sums[filename] = checksum
    if internal_sums != {"aim59": digest_bytes(launcher), allowed_dll: digest_bytes(dll)}:
        raise SystemExit("Terminal bundle checksums do not match its payload")

print(f"OK: {archive.relative_to(root)}")
print("Release verification passed.")
