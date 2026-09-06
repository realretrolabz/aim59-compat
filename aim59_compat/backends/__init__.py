"""Platform-specific compatibility backends and build-target selection."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .base import BackendError, CompatibilityBackend, WineBackendContract


class BackendTarget(str, Enum):
    WINE = "wine"
    WINDOWS = "windows"


DEFAULT_BUILD_TARGET = BackendTarget.WINE


@dataclass(frozen=True)
class WineBackendOptions:
    prefix: Path
    patched_dll: Path
    auto_select_patched_dll: bool = False
    wine: str = "wine"
    wineboot: str = "wineboot"
    wineserver: str = "wineserver"
    winetricks: str = "winetricks"
    dry_run: bool = False


def host_target(host_platform: str) -> BackendTarget:
    if host_platform.startswith("linux"):
        return BackendTarget.WINE
    if host_platform == "win32":
        return BackendTarget.WINDOWS
    raise BackendError(f"Unsupported host platform: {host_platform}")


def select_backend_target(
    build_target: BackendTarget | str,
    *,
    host_platform: str | None = None,
) -> BackendTarget:
    try:
        target = BackendTarget(build_target)
    except ValueError as exc:
        raise BackendError(f"Unknown backend target: {build_target}") from exc

    host = host_platform if host_platform is not None else sys.platform
    expected = host_target(host)
    if target is not expected:
        raise BackendError(
            f"Backend target '{target.value}' cannot run on host '{host}'; "
            f"this host requires the '{expected.value}' build target"
        )
    return target


def create_backend(
    manifest: dict[str, Any],
    target: BackendTarget,
    *,
    wine_options: WineBackendOptions | None = None,
) -> CompatibilityBackend:
    if target is BackendTarget.WINE:
        if wine_options is None:
            raise BackendError("Wine backend options are required")
        return create_wine_backend(manifest, wine_options)
    raise BackendError("The native Windows backend is not implemented or supported")


def create_wine_backend(
    manifest: dict[str, Any], options: WineBackendOptions
) -> WineBackendContract:
    from .wine import WineBackend

    return WineBackend(
        manifest,
        options.prefix,
        options.patched_dll,
        auto_select_patched_dll=options.auto_select_patched_dll,
        wine=options.wine,
        wineboot=options.wineboot,
        wineserver=options.wineserver,
        winetricks=options.winetricks,
        dry_run=options.dry_run,
    )
