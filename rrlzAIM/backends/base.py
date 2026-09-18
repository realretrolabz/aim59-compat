from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class BackendError(RuntimeError):
    pass


DEFAULT_AIM_SERVER_HOST = "aim.realretrolabz.com"
DEFAULT_AIM_SERVER_PORT = 5190


@dataclass(frozen=True)
class AimServerSettings:
    """An explicit AIM OSCAR server preference.

    ``None`` in :class:`SetupConfiguration` represents the separate "keep the
    existing setting" choice; an instance always represents a validated value
    that should be written to the target backend.
    """

    host: str
    port: int

    def __post_init__(self) -> None:
        if not isinstance(self.host, str):
            raise ValueError("A custom AIM server host is required")
        host = self.host.strip()
        if not host:
            raise ValueError("A custom AIM server host is required")
        if any(ord(character) < 32 for character in host):
            raise ValueError("AIM server host cannot contain control characters")
        if isinstance(self.port, bool) or not isinstance(self.port, int):
            raise ValueError("Server port must be a whole number from 1 through 65535")
        if not 1 <= self.port <= 65535:
            raise ValueError("Server port must be a whole number from 1 through 65535")
        object.__setattr__(self, "host", host)


@dataclass(frozen=True)
class SetupConfiguration:
    """Optional user choices applied after AIM has been installed."""

    server: AimServerSettings | None = None
    remove_aol_desktop_shortcut: bool = False
    create_xdg_launcher: bool = True


@dataclass(frozen=True)
class SetupPresentation:
    confirmation_lines: tuple[str, ...]
    launch_command: str


class CompatibilityBackend(Protocol):
    @property
    def setup_presentation(self) -> SetupPresentation:
        """Return backend-specific details shown by shared setup orchestration."""
        ...

    def prepare_setup(self) -> None:
        """Validate backend requirements before acquiring an installer."""
        ...

    def configure_setup(self, configuration: SetupConfiguration) -> None:
        """Accept resolved optional choices before setup confirmation."""
        ...

    def setup(self, installer: Path) -> None:
        """Prepare AIM and apply this backend's compatibility changes."""
        ...

    def doctor(self) -> list[tuple[bool, str]]:
        """Return diagnostic status and user-facing messages."""
        ...

    def launch(self) -> None:
        """Validate the runtime and launch AIM."""
        ...

    def rollback(self) -> None:
        """Validate the runtime and restore backend-owned changes."""
        ...


class WinePrefixBackend(Protocol):
    def check_tools(
        self,
        *,
        require_winetricks: bool,
        require_wineboot: bool = False,
        enforce_version: bool = True,
    ) -> str:
        """Validate commands needed for a Wine-prefix operation."""
        ...

    def apply(self) -> None:
        """Apply Wine-prefix compatibility changes."""
        ...

    def set_server(self, settings: AimServerSettings) -> None:
        """Write an AIM server preference to an existing Wine prefix."""
        ...

    def install_menu_shortcut(self) -> None:
        """Create this prefix's project-owned XDG launcher."""
        ...

    def remove_menu_shortcut(self) -> None:
        """Remove this prefix's project-owned XDG launcher."""
        ...

    def remove_aol_desktop_shortcut(self) -> None:
        """Remove only AIM's optional AOL promotional desktop shortcut."""
        ...

    def uninstall(self) -> None:
        """Run AIM's uninstaller and remove its completed Wine prefix."""
        ...


class WineBackendContract(CompatibilityBackend, WinePrefixBackend, Protocol):
    """Combined contract used while constructing the current Wine backend."""
