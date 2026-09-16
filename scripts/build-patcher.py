#!/usr/bin/env python3
from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path


root = Path(__file__).resolve().parents[1]
output = root / "dist/aim59-patcher.pyz"

with tempfile.TemporaryDirectory(prefix="aim59-patcher-") as temporary:
    staging = Path(temporary)
    shutil.copytree(
        root / "aim59_compat",
        staging / "aim59_compat",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    data = staging / "aim59_compat/data"
    data.mkdir()
    shutil.copy2(root / "manifests/aim-5.9.3861.json", data / "aim-5.9.3861.json")
    (staging / "__main__.py").write_text(
        "from aim59_compat.cli import main\n\nraise SystemExit(main())\n",
        encoding="utf-8",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write(b"#!/usr/bin/env python3\n")
        with zipfile.ZipFile(
            stream,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for source in sorted(path for path in staging.rglob("*") if path.is_file()):
                relative = source.relative_to(staging).as_posix()
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (source.stat().st_mode & 0xFFFF) << 16
                archive.writestr(info, source.read_bytes(), compresslevel=9)
    output.chmod(output.stat().st_mode | 0o111)

print(output)
