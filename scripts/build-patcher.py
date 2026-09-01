#!/usr/bin/env python3
from __future__ import annotations

import shutil
import tempfile
import zipapp
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
    zipapp.create_archive(
        staging,
        target=output,
        interpreter="/usr/bin/env python3",
        compressed=True,
    )

print(output)
