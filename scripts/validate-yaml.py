#!/usr/bin/env python3
from pathlib import Path
import re
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
    if data["runner"] != "linux":
        raise SystemExit(f"{path}: must use the Linux runner for system Wine")
    for key in ("game", "installer"):
        if key not in script:
            raise SystemExit(f"{path}: missing script key {key!r}")
    rendered = path.read_text(encoding="utf-8")
    if " setup " not in rendered or "--source oldversion" not in rendered:
        raise SystemExit(f"{path}: does not delegate setup to the canonical patcher")
    if "file: aim59_bundle" not in rendered:
        raise SystemExit(f"{path}: does not extract the release-bundle alias")
    if 'python3 -u "$CACHE/aim59" setup' not in rendered:
        raise SystemExit(f"{path}: does not run the release-bundled patcher")
    game = script["game"]
    if game.get("exe") != "/usr/bin/env":
        raise SystemExit(f"{path}: does not launch through the system environment")
    launch_args = game.get("args", "")
    if 'WINEPREFIX="$GAMEDIR/prefix" wine ' not in launch_args or not launch_args.endswith(
        '/drive_c/Program Files/AIM/aim.exe"'
    ):
        raise SystemExit(f"{path}: does not launch AIM with system Wine")
    if script.get("wine"):
        raise SystemExit(f"{path}: contains a Lutris-managed Wine configuration")
    if script.get("system", {}).get("disable_runtime") is not True:
        raise SystemExit(f"{path}: must disable the Lutris runtime for system Wine")
    if "--patched-dll" in rendered:
        raise SystemExit(f"{path}: bypasses the patcher's version-aware DLL selection")
    bundle_files = [
        item["aim59_bundle"]
        for item in script.get("files", [])
        if isinstance(item, dict) and "aim59_bundle" in item
    ]
    if len(bundle_files) != 1 or not isinstance(bundle_files[0], dict):
        raise SystemExit(f"{path}: must define exactly one release-bundle alias")
    checksum = bundle_files[0].get("checksum", "")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", checksum) is None:
        raise SystemExit(f"{path}: release bundle does not have a valid SHA-256")
    release_base = (
        f"https://github.com/realretrolabz/aim59-compat/releases/download/v{version}/"
    )
    if release_base not in rendered:
        raise SystemExit(f"{path}: does not use the current version's GitHub Release assets")
    archive_name = f"aim59-compat-{version}-linux.tar.gz"
    if rendered.count(archive_name) != 2:
        raise SystemExit(f"{path}: does not use the current release bundle")
    if "file://" in rendered or "$SCRIPTDIR" in rendered:
        raise SystemExit(f"{path}: contains an unsupported local asset reference")
    for duplicated_step in ("name: create_prefix", "name: winetricks", "name: wineexec"):
        if duplicated_step in rendered:
            raise SystemExit(f"{path}: duplicates canonical step {duplicated_step!r}")
    print(f"OK: {path.relative_to(root)}")

print("YAML validation passed.")
