"""Persistent catalog for Wine prefixes created by the guided manager.

The catalog is deliberately an allow-list, never a discovery mechanism.  A
path appears here only after this application completed a guided installation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .backends.base import BackendError


_SCHEMA = 1


def catalog_path() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home).expanduser() if data_home else Path.home() / ".local/share"
    return base / "rrlzAIM" / "managed-prefixes.json"


@dataclass(frozen=True)
class ManagedPrefix:
    """The manager-owned parent directory and its fixed Wine child directory."""

    root: Path

    @property
    def prefix(self) -> Path:
        return self.root / "prefix"


class ManagedPrefixCatalog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or catalog_path()

    @staticmethod
    def normalize_root(root: Path) -> Path:
        candidate = root.expanduser().resolve(strict=False)
        if candidate == Path("/"):
            raise BackendError("The AIM data directory cannot be the filesystem root")
        return candidate

    def _load(self) -> dict[str, object]:
        if not self.path.is_file():
            return {"schema": _SCHEMA, "managed": [], "active": None}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BackendError(f"Managed-prefix catalog is unreadable: {self.path}") from exc
        if not isinstance(state, dict) or state.get("schema") != _SCHEMA:
            raise BackendError(f"Managed-prefix catalog is malformed: {self.path}")
        managed = state.get("managed")
        active = state.get("active")
        if (
            not isinstance(managed, list)
            or any(not isinstance(item, str) for item in managed)
            or active is not None and not isinstance(active, str)
        ):
            raise BackendError(f"Managed-prefix catalog is malformed: {self.path}")
        return state

    def _write(self, state: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def entries(self) -> tuple[ManagedPrefix, ...]:
        state = self._load()
        roots: list[ManagedPrefix] = []
        seen: set[str] = set()
        for item in state["managed"]:  # validated by _load
            root = self.normalize_root(Path(item))
            key = str(root)
            if key not in seen:
                seen.add(key)
                roots.append(ManagedPrefix(root))
        return tuple(roots)

    def active(self) -> ManagedPrefix | None:
        state = self._load()
        active = state["active"]
        if active is None:
            return None
        root = self.normalize_root(Path(active))
        return next((entry for entry in self.entries() if entry.root == root), None)

    def record(self, root: Path) -> ManagedPrefix:
        entry = ManagedPrefix(self.normalize_root(root))
        state = self._load()
        roots = list(state["managed"])
        root_text = str(entry.root)
        if root_text not in roots:
            roots.append(root_text)
        state["managed"] = roots
        state["active"] = root_text
        self._write(state)
        return entry

    def select(self, root: Path) -> ManagedPrefix:
        entry = ManagedPrefix(self.normalize_root(root))
        if entry not in self.entries():
            raise BackendError(f"This is not a managed AIM location: {entry.root}")
        state = self._load()
        state["active"] = str(entry.root)
        self._write(state)
        return entry

    def forget(self, root: Path) -> None:
        entry = ManagedPrefix(self.normalize_root(root))
        state = self._load()
        roots = [item for item in state["managed"] if item != str(entry.root)]
        state["managed"] = roots
        if state["active"] == str(entry.root):
            state["active"] = roots[-1] if roots else None
        self._write(state)
