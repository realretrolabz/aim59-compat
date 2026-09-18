"""Interactive, terminal-only management interface for rrlzAIMlinux."""

from __future__ import annotations

import os
import shutil
import sys
import termios
import tty
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from .backends.base import (
    DEFAULT_AIM_SERVER_HOST,
    DEFAULT_AIM_SERVER_PORT,
    AimServerSettings,
    BackendError,
    SetupConfiguration,
)
from .managed_prefixes import ManagedPrefix, ManagedPrefixCatalog


def _cell_width(text: str) -> int:
    width = 0
    for character in text:
        if unicodedata.combining(character):
            continue
        width += 2 if unicodedata.east_asian_width(character) in ("W", "F") else 1
    return width


def _logo_lines() -> tuple[str, ...]:
    source = resources.files("rrlzAIM").joinpath("assets/rrlzAIMLinux.txt")
    # The supplied art is positioned within a fixed-width canvas. Its trailing
    # spaces are part of that canvas and must remain when centering it above the
    # menu box.
    return tuple(source.read_text(encoding="utf-8").splitlines())


@dataclass(frozen=True)
class InstallerChoice:
    mode: str
    value: str


@dataclass(frozen=True)
class ManagerOperations:
    """Small adapter keeping terminal presentation independent of Wine details."""

    default_root: Callable[[], Path]
    normalize_root: Callable[[Path], Path]
    install: Callable[[Path, SetupConfiguration, InstallerChoice], None]
    backend: Callable[[ManagedPrefix], Any]


class TerminalDisplay:
    def __init__(self) -> None:
        self.logo = _logo_lines()
        self.logo_width = max((_cell_width(line) for line in self.logo), default=0)

    @property
    def terminal_size(self) -> os.terminal_size:
        return shutil.get_terminal_size(fallback=(80, 24))

    @property
    def has_room_for_logo(self) -> bool:
        """Whether the complete logo and menu can be shown without scrolling."""
        size = self.terminal_size
        return size.columns >= self.logo_width and size.lines >= len(self.logo) + 10

    @property
    def box_width(self) -> int:
        """Use the logo width when visible, otherwise retain a readable menu."""
        desired = max(78, self.logo_width) if self.has_room_for_logo else 78
        return max(4, min(desired, self.terminal_size.columns))

    def clear(self) -> None:
        print("\033[2J\033[H", end="")

    @staticmethod
    def _clip(text: str, width: int) -> str:
        if width <= 0:
            return ""
        if _cell_width(text) <= width:
            return text
        if width <= 3:
            return "." * width
        return text[: max(0, width - 3)] + "..."

    def centered(self, text: str, *, width: int | None = None) -> str:
        available = width or self.terminal_size.columns
        return " " * max(0, (available - _cell_width(text)) // 2) + text

    def _box_line(self, text: str = "") -> str:
        inner = self.box_width - 2
        clipped = self._clip(text, inner)
        padding = max(0, (inner - _cell_width(clipped)) // 2)
        return "│" + " " * padding + clipped + " " * (inner - padding - _cell_width(clipped)) + "│"

    def _draw_box(self, lines: list[str]) -> None:
        print(self.centered("╔" + "═" * (self.box_width - 2) + "╗"))
        for line in lines:
            print(self.centered(self._box_line(line)))
        print(self.centered("╚" + "═" * (self.box_width - 2) + "╝"))

    def _draw_logo(self) -> None:
        left = max(0, (self.terminal_size.columns - self.logo_width) // 2)
        for line in self.logo:
            print(" " * left + line)

    def main_menu(self, active: ManagedPrefix | None) -> None:
        self.clear()
        show_logo = self.has_room_for_logo
        menu_height = 9
        logo_height = len(self.logo) + 1 if show_logo else 0
        top_padding = max(0, (self.terminal_size.lines - logo_height - menu_height) // 2)
        print("\n" * top_padding, end="")
        if show_logo:
            self._draw_logo()
            print()
        status = "No managed AIM installation selected"
        if active is not None:
            status = f"Selected: {active.root}"
        inner = self.box_width - 2
        column_width = max(1, (inner - 3) // 2)
        pairs = (
            ("1. Install AIM", "4. Shortcut settings"),
            ("2. Launch AIM", "5. Diagnostics & maintenance"),
            ("3. Server settings", "6. Uninstall AIM"),
            ("", "7. Exit"),
        )
        rows = ["rrlzAIMlinux", status, ""]
        for left, right in pairs:
            rows.append(left.center(column_width) + "   " + right.center(column_width))
        self._draw_box(rows)

    def screen(self, title: str, lines: list[str]) -> None:
        self.clear()
        rows = ["rrlzAIMlinux", title, "", *lines]
        self._draw_box(rows)

    def prompt(self, text: str) -> str:
        return input(self.centered(text)).strip()

    def pause(self) -> None:
        input(self.centered("Press Enter to return to the menu."))

    def checkbox(self, title: str, label: str, *, selected: bool = False) -> bool:
        while True:
            marker = "X" if selected else " "
            self.screen(title, [f"[{marker}] {label}", "", "Space: toggle     Enter: continue"])
            key = self.read_key()
            if key == " ":
                selected = not selected
            elif key in ("\n", "\r"):
                return selected
            elif key.lower() == "q":
                raise KeyboardInterrupt

    @staticmethod
    def read_key() -> str:
        if not sys.stdin.isatty():
            return input()[:1]
        descriptor = sys.stdin.fileno()
        previous = termios.tcgetattr(descriptor)
        try:
            tty.setcbreak(descriptor)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)


class TerminalManager:
    def __init__(self, operations: ManagerOperations, catalog: ManagedPrefixCatalog | None = None) -> None:
        self.operations = operations
        self.catalog = catalog or ManagedPrefixCatalog()
        self.display = TerminalDisplay()

    def run(self) -> int:
        while True:
            active = self.catalog.active()
            self.display.main_menu(active)
            choice = self.display.prompt("Select an option [1-7]: ")
            if choice == "1":
                self.install()
            elif choice == "2":
                self.with_active("Launch AIM", lambda entry: self.operations.backend(entry).launch())
            elif choice == "3":
                self.server_settings()
            elif choice == "4":
                self.shortcut_settings()
            elif choice == "5":
                self.diagnostics()
            elif choice == "6":
                self.uninstall()
            elif choice == "7" or choice.lower() in ("q", "quit", "exit"):
                self.display.clear()
                return 0
            else:
                self.display.screen("Menu", ["Choose a number from 1 through 7."])
                self.display.pause()

    def _run_action(self, title: str, action: Callable[[], None]) -> bool:
        self.display.screen(title, ["Working…"])
        try:
            action()
        except (BackendError, OSError, ValueError) as exc:
            self.display.screen(title, ["Action stopped:", str(exc)])
            self.display.pause()
            return False
        self.display.pause()
        return True

    def with_active(self, title: str, action: Callable[[ManagedPrefix], None]) -> None:
        active = self.catalog.active()
        if active is None:
            self.display.screen(title, ["No managed AIM installation is selected.", "Install AIM first."])
            self.display.pause()
            return
        self._run_action(title, lambda: action(active))

    def _choose_root(self) -> Path:
        default = self.operations.default_root()
        self.display.screen(
            "Install AIM — location",
            [
                "Choose the AIM data directory.",
                "Wine will always use its fixed child directory: prefix",
                f"Default: {default}",
            ],
        )
        entered = self.display.prompt("AIM data directory [default]: ")
        return self.operations.normalize_root(Path(entered).expanduser() if entered else default)

    def _choose_server(
        self,
        *,
        title: str = "Install AIM — server",
        current: str | None = None,
    ) -> AimServerSettings:
        lines = [] if current is None else [current, ""]
        lines.extend(
            [
                f"1. realretrolabz ({DEFAULT_AIM_SERVER_HOST}:{DEFAULT_AIM_SERVER_PORT})",
                "2. Custom server hostname",
            ]
        )
        self.display.screen(
            title,
            lines,
        )
        choice = self.display.prompt("Server [1]: ") or "1"
        if choice == "1":
            return AimServerSettings(DEFAULT_AIM_SERVER_HOST, DEFAULT_AIM_SERVER_PORT)
        if choice == "2":
            self.display.screen(
                "Server settings — custom server"
                if title == "Server settings"
                else "Install AIM — custom server",
                [f"Port {DEFAULT_AIM_SERVER_PORT} is used by the guided installer."],
            )
            return AimServerSettings(
                self.display.prompt("Server hostname: "), DEFAULT_AIM_SERVER_PORT
            )
        raise BackendError("Choose server option 1 or 2")

    def _choose_installer(self) -> InstallerChoice:
        self.display.screen(
            "Install AIM — installer source",
            [
                "1. Download verified AIM 5.9.3861 from OldVersion.com",
                "2. Use a local aim593861.exe",
                "3. Download from a direct URL",
            ],
        )
        choice = self.display.prompt("Installer source [1]: ") or "1"
        if choice == "1":
            return InstallerChoice("source", "oldversion")
        if choice == "2":
            value = self.display.prompt("Path to aim593861.exe: ")
            if value:
                return InstallerChoice("installer", value)
        if choice == "3":
            value = self.display.prompt("Installer URL: ")
            if value:
                return InstallerChoice("installer_url", value)
        raise BackendError("Choose a valid installer source")

    def install(self) -> None:
        try:
            root = self._choose_root()
            if root.exists() and not root.is_dir():
                raise BackendError("The AIM data directory must be a directory")
            if (root / "prefix").exists() or (root / "prefix").is_symlink():
                raise BackendError(
                    "The selected AIM data directory already contains a prefix. "
                    "The manager will not take ownership of an existing installation."
                )
            server = self._choose_server()
            remove_aol = self.display.checkbox(
                "Install AIM — shortcut cleanup",
                "Remove the AOL promotional desktop shortcut",
            )
            self.display.screen(
                "Install AIM — XDG launcher",
                [
                    "Create an XDG AIM launcher?",
                    "Without it, launch AIM through rrlzAIMlinux or Wine manually.",
                ],
            )
            answer = self.display.prompt("Create XDG launcher? [Y/n]: ").lower() or "y"
            if answer not in ("y", "yes", "n", "no"):
                raise BackendError("Please answer yes or no for the XDG launcher")
            create_launcher = answer in ("y", "yes")
            installer = self._choose_installer()
            configuration = SetupConfiguration(
                server=server,
                remove_aol_desktop_shortcut=remove_aol,
                create_xdg_launcher=create_launcher,
            )
            lines = [
                f"AIM data directory: {root}",
                f"Wine prefix: {root / 'prefix'}",
                f"Server: {server.host}:{server.port}",
                f"Remove AOL shortcut: {'yes' if remove_aol else 'no'}",
                f"Create XDG launcher: {'yes' if create_launcher else 'no'}",
                "",
                "Begin installation? [Y/n]",
            ]
            self.display.screen("Install AIM — confirmation", lines)
            if (self.display.prompt("Continue [Y/n]: ").lower() or "y") not in ("y", "yes"):
                return
        except (BackendError, ValueError) as exc:
            self.display.screen("Install AIM", [str(exc)])
            self.display.pause()
            return

        def action() -> None:
            self.operations.install(root, configuration, installer)
            self.catalog.record(root)
            print(f"✓ Managed AIM location saved: {root}")

        self._run_action("Install AIM", action)

    def server_settings(self) -> None:
        active = self.catalog.active()
        if active is None:
            self.display.screen("Server settings", ["No managed AIM installation is selected."])
            self.display.pause()
            return
        backend = self.operations.backend(active)
        try:
            current = getattr(backend, "current_server_status", lambda: "Server: unavailable")()
            settings = self._choose_server(title="Server settings", current=current)
        except (BackendError, ValueError) as exc:
            self.display.screen("Server settings", [str(exc)])
            self.display.pause()
            return

        def action() -> None:
            backend.check_tools(require_winetricks=False)
            backend.set_server(settings)
            print("✓ AIM server setting applied")

        self._run_action("Server settings", action)

    def shortcut_settings(self) -> None:
        active = self.catalog.active()
        if active is None:
            self.display.screen("Shortcut settings", ["No managed AIM installation is selected."])
            self.display.pause()
            return
        self.display.screen(
            "Shortcut settings",
            [
                "1. Remove AOL promotional desktop shortcut",
                "2. Create XDG AIM launcher",
                "3. Remove XDG AIM launcher",
                "4. Back",
            ],
        )
        choice = self.display.prompt("Shortcut action [1-4]: ")
        backend = self.operations.backend(active)
        if choice == "1":
            self._run_action("Shortcut settings", backend.remove_aol_desktop_shortcut)
        elif choice == "2":
            def create_launcher() -> None:
                backend.check_tools(require_winetricks=False)
                backend.install_menu_shortcut()

            self._run_action("Shortcut settings", create_launcher)
        elif choice == "3":
            self._run_action("Shortcut settings", backend.remove_menu_shortcut)

    def diagnostics(self) -> None:
        active = self.catalog.active()
        self.display.screen(
            "Diagnostics & prefix maintenance",
            [
                "1. Run diagnostics",
                "2. Select a managed AIM location",
                "3. Back",
            ],
        )
        choice = self.display.prompt("Choose an action [1-3]: ")
        if choice == "2":
            self.select_managed_prefix()
            return
        if choice != "1":
            return
        if active is None:
            self.display.screen("Diagnostics", ["No managed AIM installation is selected."])
            self.display.pause()
            return
        try:
            backend = self.operations.backend(active)
            checks = backend.doctor()
            server_status = getattr(backend, "current_server_status", lambda: "Server: unavailable")()
            lines = [f"{'OK' if passed else 'CHECK'}  {message}" for passed, message in checks]
            lines.append(server_status)
            self.display.screen("Diagnostics", lines)
        except BackendError as exc:
            self.display.screen("Diagnostics", [str(exc)])
        self.display.pause()

    def select_managed_prefix(self) -> None:
        entries = self.catalog.entries()
        if not entries:
            self.display.screen("Select managed AIM location", ["No guided installations have been recorded."])
            self.display.pause()
            return
        self.display.screen(
            "Select managed AIM location",
            [f"{index}. {entry.root}" for index, entry in enumerate(entries, start=1)],
        )
        try:
            choice = int(self.display.prompt("Select a location: "))
            selected = entries[choice - 1]
            self.catalog.select(selected.root)
        except (ValueError, IndexError, BackendError):
            self.display.screen("Select managed AIM location", ["Choose a listed location number."])
            self.display.pause()

    def uninstall(self) -> None:
        active = self.catalog.active()
        if active is None:
            self.display.screen("Uninstall AIM", ["No managed AIM installation is selected."])
            self.display.pause()
            return
        self.display.screen(
            "Uninstall AIM",
            [
                "This runs AIM's uninstaller, removes its XDG launcher,",
                "then permanently deletes this managed location:",
                str(active.root),
                "Wine prefix:",
                str(active.prefix),
                "",
                "Type UNINSTALL to continue.",
            ],
        )
        if self.display.prompt("Confirmation: ") != "UNINSTALL":
            return

        def action() -> None:
            backend = self.operations.backend(active)
            backend.check_tools(require_winetricks=False, enforce_version=False)
            backend.uninstall()
            self.catalog.forget(active.root)
            print("✓ Managed AIM location removed")

        self._run_action("Uninstall AIM", action)
