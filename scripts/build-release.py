#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import shutil
import tarfile
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parents[1]
version = (root / "VERSION").read_text(encoding="utf-8").strip()
dist = root / "dist"
patcher = dist / "rrlzAIMlinux.pyz"
published_dlls = (
    root / "binaries/mciwave-wine9-x86-aim.dll",
    root / "binaries/mciwave-wine10-x86-aim.dll",
)
archive = dist / f"rrlzAIM-{version}-linux.tar.gz"


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


for required in (patcher, *published_dlls):
    if not required.is_file():
        raise SystemExit(f"Missing release input: {required}")

dist.mkdir(parents=True, exist_ok=True)
release_dlls = tuple(dist / source.name for source in published_dlls)
for source, destination in zip(published_dlls, release_dlls):
    shutil.copy2(source, destination)

with tempfile.TemporaryDirectory(prefix="rrlzAIM-release-") as temporary:
    bundle = Path(temporary) / f"rrlzAIM-{version}"
    bundle.mkdir()

    launcher = bundle / "rrlzAIMlinux"
    shutil.copy2(patcher, launcher)
    launcher.chmod(launcher.stat().st_mode | 0o111)
    for published_dll in published_dlls:
        shutil.copy2(published_dll, bundle / published_dll.name)

    for filename in ("README.md", "LICENSE", "COPYING.LGPL-2.1", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(root / filename, bundle / filename)
    shutil.copytree(root / "assets", bundle / "assets")
    shutil.copytree(root / "docs", bundle / "docs")
    shutil.copytree(root / "patches", bundle / "patches")
    (bundle / "scripts").mkdir()
    shutil.copy2(root / "scripts/build-mciwave.sh", bundle / "scripts/build-mciwave.sh")
    (bundle / "SOURCE.md").write_text(
        "# Corresponding source\n\n"
        f"Source for this release: https://github.com/realretrolabz/rrlzAIM/tree/v{version}\n",
        encoding="utf-8",
    )
    (bundle / "SHA256SUMS").write_text(
        f"{sha256(launcher)}  rrlzAIMlinux\n"
        + "".join(
            f"{sha256(bundle / source.name)}  {source.name}\n"
            for source in published_dlls
        ),
        encoding="utf-8",
    )

    with archive.open("wb") as raw_output:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_output,
            mtime=0,
        ) as compressed_output:
            with tarfile.open(fileobj=compressed_output, mode="w") as output:
                output.add(bundle, arcname=bundle.name, filter=normalized_tar_info)

release_files = (patcher, *release_dlls, archive)
(dist / "SHA256SUMS").write_text(
    "".join(f"{sha256(path)}  {path.name}\n" for path in release_files),
    encoding="utf-8",
)

print(archive)
print(dist / "SHA256SUMS")
