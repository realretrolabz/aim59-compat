from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any


class ManifestError(RuntimeError):
    pass


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    if path is not None:
        source = path.read_text(encoding="utf-8")
    else:
        local = repository_root() / "manifests" / "aim-5.9.3861.json"
        if local.is_file():
            source = local.read_text(encoding="utf-8")
        else:
            source = (
                resources.files("rrlzAIM")
                .joinpath("data/aim-5.9.3861.json")
                .read_text(encoding="utf-8")
            )

    try:
        manifest = json.loads(source)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Invalid manifest JSON: {exc}") from exc

    required = ("id", "name", "version", "installer", "wine", "mciwave")
    missing = [key for key in required if key not in manifest]
    if missing:
        raise ManifestError(f"Manifest is missing: {', '.join(missing)}")

    supported = manifest["wine"].get("version_prefixes")
    variants = manifest["mciwave"].get("variants")
    if not isinstance(supported, list) or not supported:
        raise ManifestError("Manifest wine.version_prefixes must be a non-empty list")
    if not isinstance(variants, dict):
        raise ManifestError("Manifest mciwave.variants must be a mapping")
    missing_variants = [version for version in supported if version not in variants]
    if missing_variants:
        raise ManifestError(
            "Manifest is missing mciwave variants for: "
            + ", ".join(missing_variants)
        )
    return manifest
