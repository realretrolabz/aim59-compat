from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class BackendError(RuntimeError):
    pass


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


class WineBackendContract(CompatibilityBackend, WinePrefixBackend, Protocol):
    """Combined contract used while constructing the current Wine backend."""
