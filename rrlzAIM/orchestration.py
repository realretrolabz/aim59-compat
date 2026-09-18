from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .backends.base import CompatibilityBackend, SetupPresentation


def run_setup(
    backend: CompatibilityBackend,
    *,
    acquire_installer: Callable[[], Path],
    confirm: Callable[[SetupPresentation], None],
    configure: Callable[[], None] | None = None,
) -> None:
    backend.prepare_setup()
    installer = acquire_installer()
    if configure is not None:
        configure()
    presentation = backend.setup_presentation
    confirm(presentation)
    backend.setup(installer)

    print()
    print("✓ AIM compatibility setup completed")
    print(f"  Run: {presentation.launch_command}")


def run_doctor(backend: CompatibilityBackend) -> int:
    failed = False
    for passed, message in backend.doctor():
        print(("✓" if passed else "✗") + " " + message)
        failed = failed or not passed
    return 1 if failed else 0


def run_launch(backend: CompatibilityBackend) -> None:
    backend.launch()


def run_rollback(backend: CompatibilityBackend) -> None:
    backend.rollback()
    print("✓ Compatibility rollback completed")
