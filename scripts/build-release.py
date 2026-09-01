#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import shutil
import tarfile
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parents[1]
version = (root / "VERSION").read_text(encoding="utf-8").strip()
dist = root / "dist"
patcher = dist / "aim59-patcher.pyz"
published_dll = root / "binaries/mciwave-wine9-x86-aim.dll"
lutris_yaml = root / "lutris/aim-5.9.3861.yml"
archive = dist / f"aim59-compat-{version}-linux.tar.gz"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_tar_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0
    return info


for required in (patcher, published_dll, lutris_yaml):
    if not required.is_file():
        raise SystemExit(f"Missing release input: {required}")

dist.mkdir(parents=True, exist_ok=True)
release_dll = dist / published_dll.name
release_yaml = dist / lutris_yaml.name
shutil.copy2(published_dll, release_dll)
shutil.copy2(lutris_yaml, release_yaml)

with tempfile.TemporaryDirectory(prefix="aim59-release-") as temporary:
    bundle = Path(temporary) / f"aim59-compat-{version}"
    bundle.mkdir()

    launcher = bundle / "aim59"
    shutil.copy2(patcher, launcher)
    launcher.chmod(launcher.stat().st_mode | 0o111)
    shutil.copy2(published_dll, bundle / published_dll.name)

    for filename in ("README.md", "LICENSE", "COPYING.LGPL-2.1", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(root / filename, bundle / filename)
    shutil.copytree(root / "docs", bundle / "docs")
    shutil.copytree(root / "patches", bundle / "patches")
    (bundle / "scripts").mkdir()
    shutil.copy2(root / "scripts/build-mciwave.sh", bundle / "scripts/build-mciwave.sh")
    (bundle / "SOURCE.md").write_text(
        "# Corresponding source\n\n"
        f"Source for this release: https://github.com/realretrolabz/aim59-compat/tree/v{version}\n",
        encoding="utf-8",
    )
    (bundle / "SHA256SUMS").write_text(
        f"{sha256(launcher)}  aim59\n"
        f"{sha256(bundle / published_dll.name)}  {published_dll.name}\n",
        encoding="utf-8",
    )

    with tarfile.open(archive, "w:gz") as output:
        output.add(bundle, arcname=bundle.name, filter=normalized_tar_info)

release_files = (patcher, release_dll, release_yaml, archive)
(dist / "SHA256SUMS").write_text(
    "".join(f"{sha256(path)}  {path.name}\n" for path in release_files),
    encoding="utf-8",
)

print(archive)
print(dist / "SHA256SUMS")
