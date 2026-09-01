#!/usr/bin/env python3
from pathlib import Path
import sys
import yaml

root = Path(__file__).resolve().parents[1]
version = (root / "VERSION").read_text(encoding="utf-8").strip()
files = [
    root / "lutris" / "aim-5.9.3861.yml",
]

for path in files:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: root is not a mapping")
    for key in ("name", "game_slug", "version", "slug", "runner", "script"):
        if key not in data:
            raise SystemExit(f"{path}: missing root key {key!r}")
    script = data["script"]
    if not isinstance(script, dict):
        raise SystemExit(f"{path}: script is not a mapping")
    for key in ("game", "installer"):
        if key not in script:
            raise SystemExit(f"{path}: missing script key {key!r}")
    rendered = path.read_text(encoding="utf-8")
    if " setup " not in rendered or "--source oldversion" not in rendered:
        raise SystemExit(f"{path}: does not delegate setup to the canonical patcher")
    if "$aim59_patcher" not in rendered or "$mciwave_patch" not in rendered:
        raise SystemExit(f"{path}: does not use Lutris installer-file aliases")
    release_base = (
        f"https://github.com/realretrolabz/aim59-compat/releases/download/v{version}/"
    )
    if release_base not in rendered:
        raise SystemExit(f"{path}: does not use the current version's GitHub Release assets")
    if "file://" in rendered or "$SCRIPTDIR" in rendered:
        raise SystemExit(f"{path}: contains an unsupported local asset reference")
    for duplicated_step in ("name: create_prefix", "name: winetricks", "name: wineexec"):
        if duplicated_step in rendered:
            raise SystemExit(f"{path}: duplicates canonical step {duplicated_step!r}")
    print(f"OK: {path.relative_to(root)}")

print("YAML validation passed.")
