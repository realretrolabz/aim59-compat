from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..download import sha256_file
from .base import BackendError, SetupPresentation


class WineBackend:
    def __init__(
        self,
        manifest: dict[str, Any],
        prefix: Path,
        patched_dll: Path,
        *,
        auto_select_patched_dll: bool = False,
        wine: str = "wine",
        wineboot: str = "wineboot",
        wineserver: str = "wineserver",
        winetricks: str = "winetricks",
        dry_run: bool = False,
    ) -> None:
        self.manifest = manifest
        self.prefix = prefix
        self.patched_dll = patched_dll
        self.auto_select_patched_dll = auto_select_patched_dll
        self.wine_version_prefix: str | None = None
        self.wine = wine
        self.wineboot = wineboot
        self.wineserver = wineserver
        self.winetricks = winetricks
        self.dry_run = dry_run

    @property
    def aim_dir(self) -> Path:
        return self.prefix / self.manifest["wine"]["aim_directory"]

    @property
    def system32(self) -> Path:
        return self.prefix / "drive_c/windows/system32"

    @property
    def state_dir(self) -> Path:
        return self.prefix / ".aim59-compat"

    @property
    def xdg_data_home(self) -> Path:
        data_home = os.environ.get("XDG_DATA_HOME")
        return (
            Path(data_home).expanduser()
            if data_home
            else Path.home() / ".local/share"
        )

    @property
    def application_menu_entry(self) -> Path:
        return self.xdg_data_home / "applications/aim59-compat.desktop"

    @property
    def wine_generated_menu_entries(self) -> tuple[Path, ...]:
        applications = self.xdg_data_home / "applications"
        return (
            applications / "wine/Programs/AOL Instant Messenger/AIM.desktop",
            applications / "wine-Programs-AOL Instant Messenger-AIM.desktop",
        )

    @property
    def application_icon(self) -> Path:
        return self.xdg_data_home / "aim59-compat/icons/aim.png"

    @property
    def installer_menu_link(self) -> Path:
        return self.prefix / (
            "drive_c/ProgramData/Microsoft/Windows/Start Menu/Programs/"
            "AOL Instant Messenger/AIM.lnk"
        )

    @property
    def setup_presentation(self) -> SetupPresentation:
        return SetupPresentation(
            confirmation_lines=(
                f"Wine prefix: {self.prefix}",
                f"Patched DLL: {self.patched_dll}",
            ),
            launch_command=f"aim59 launch --prefix {self.prefix}",
        )

    @property
    def env(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["WINEPREFIX"] = str(self.prefix)
        return environment

    def _display(self, command: list[str]) -> None:
        print("  $ " + " ".join(command))

    def _run(
        self,
        command: list[str],
        *,
        check: bool = True,
        capture: bool = False,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self._display(command)
        if self.dry_run:
            return subprocess.CompletedProcess(command, 0, "", "")
        environment = self.env
        if extra_env:
            environment.update(extra_env)
        return subprocess.run(
            command,
            env=environment,
            check=check,
            text=True,
            capture_output=capture,
        )

    def check_tools(
        self,
        *,
        require_winetricks: bool,
        require_wineboot: bool = False,
        enforce_version: bool = True,
    ) -> str:
        tools = [self.wine, self.wineserver]
        if require_wineboot:
            tools.append(self.wineboot)
        if require_winetricks:
            tools.append(self.winetricks)
        missing = [tool for tool in tools if shutil.which(tool) is None]
        if missing:
            raise BackendError(f"Missing required command(s): {', '.join(missing)}")

        result = subprocess.run(
            [self.wine, "--version"],
            check=False,
            text=True,
            capture_output=True,
        )
        version = result.stdout.strip() or result.stderr.strip()
        if "wine32 is missing" in result.stderr.lower():
            raise BackendError(
                "Wine 32-bit support is missing. On Debian with i386 enabled, run: "
                "sudo apt install wine32:i386"
            )
        supported = tuple(self.manifest["wine"]["version_prefixes"])
        matched = next((item for item in supported if version.startswith(item)), None)
        if result.returncode != 0 or (enforce_version and matched is None):
            expected = " or ".join(item.removeprefix("wine-") for item in supported)
            raise BackendError(
                f"This backend has version-matched patches only for Wine {expected}. "
                f"Detected: {version or '<none>'}"
            )
        if matched is not None:
            self.wine_version_prefix = matched
            if self.auto_select_patched_dll:
                filename = self.manifest["mciwave"]["variants"][matched]["filename"]
                self.patched_dll = self.patched_dll.with_name(filename)
        return version

    def _mciwave_variant(self) -> dict[str, str]:
        if self.wine_version_prefix is None:
            raise BackendError("Wine version must be checked before selecting mciwave.dll")
        return self.manifest["mciwave"]["variants"][self.wine_version_prefix]

    def verify_patched_dll(self) -> str:
        if not self.patched_dll.is_file():
            raise BackendError(f"Patched mciwave DLL not found: {self.patched_dll}")
        digest = sha256_file(self.patched_dll)
        expected = self._mciwave_variant()["sha256"]
        if digest != expected:
            raise BackendError(
                f"Patched mciwave checksum mismatch: expected {expected}, got {digest}"
            )
        if b"Wine patched DLL" not in self.patched_dll.read_bytes():
            raise BackendError("Patched mciwave marker is missing")
        return digest

    def create_prefix(self) -> None:
        system_reg = self.prefix / "system.reg"
        if system_reg.exists():
            header = system_reg.read_text(encoding="utf-8", errors="ignore")[:512]
            if "#arch=win64" in header:
                raise BackendError(f"Existing prefix is 64-bit, not win32: {self.prefix}")
            print(f"✓ Reusing Wine prefix: {self.prefix}")
            return

        print(f"→ Creating 32-bit Wine prefix: {self.prefix}")
        if not self.dry_run:
            self.prefix.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [self.wineboot, "-u"],
            extra_env={"WINEARCH": self.manifest["wine"]["arch"]},
        )

    def install_prerequisites(self) -> None:
        packages = list(self.manifest["wine"]["winetricks"])
        print("→ Installing Wine prerequisites: " + " ".join(packages))
        self._run([self.winetricks, "-q", *packages])

    def install_aim(self, installer: Path) -> None:
        print(f"→ Running AIM {self.manifest['version']} installer")
        overrides = os.environ.get("WINEDLLOVERRIDES", "")
        if overrides:
            overrides += ";"
        overrides += "winemenubuilder.exe="
        self._run(
            [self.wine, str(installer)],
            extra_env={"WINEDLLOVERRIDES": overrides},
        )
        self.stop_wine()
        if not self.dry_run:
            self._require_aim_files()

    @staticmethod
    def _desktop_exec_argument(value: str) -> str:
        escaped = value.replace("\\", "\\\\")
        for character in ('"', "`", "$"):
            escaped = escaped.replace(character, "\\" + character)
        return f'"{escaped}"'

    def install_menu_shortcut(self) -> None:
        print("→ Installing AIM application-menu shortcut")
        executable = self.aim_dir / self.manifest["wine"]["executable"]
        if not self.dry_run:
            if not self.installer_menu_link.is_file():
                raise BackendError(
                    "AIM installer did not create the shortcut needed to extract "
                    f"its icon: {self.installer_menu_link}"
                )
            self.application_icon.parent.mkdir(parents=True, exist_ok=True)

        self._run(
            [
                self.wine,
                "winemenubuilder.exe",
                "-t",
                str(self.installer_menu_link),
                str(self.application_icon),
            ]
        )
        if not self.dry_run:
            if (
                not self.application_icon.is_file()
                or self.application_icon.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n"
            ):
                raise BackendError(
                    "Wine could not extract AIM's embedded icon to "
                    f"{self.application_icon}"
                )

        command = " ".join(
            (
                "env",
                self._desktop_exec_argument(f"WINEPREFIX={self.prefix}"),
                self._desktop_exec_argument(self.wine),
                self._desktop_exec_argument(str(executable)),
            )
        )
        desktop_entry = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=AOL Instant Messenger 5.9\n"
            "Comment=Launch AIM 5.9.3861 with its compatibility prefix\n"
            f"Exec={command}\n"
            f"Path={self.aim_dir}\n"
            f"Icon={self.application_icon}\n"
            "Terminal=false\n"
            "StartupNotify=true\n"
            "StartupWMClass=aim.exe\n"
            "Categories=Network;InstantMessaging;\n"
            "Keywords=AIM;AOL;Chat;Instant Messaging;\n"
            f"X-AIM59-Prefix={self.prefix}\n"
        )
        if self.dry_run:
            print(f"  → Would write {self.application_menu_entry}")
            return

        self._remove_wine_generated_menu_entries()
        self.application_menu_entry.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.application_menu_entry.with_suffix(".desktop.tmp")
        temporary.write_text(desktop_entry, encoding="utf-8")
        temporary.chmod(0o644)
        temporary.replace(self.application_menu_entry)

        written = self.application_menu_entry.read_text(
            encoding="utf-8", errors="replace"
        )
        if written != desktop_entry:
            raise BackendError(
                f"Failed to verify application-menu entry: {self.application_menu_entry}"
            )

    def _remove_wine_generated_menu_entries(self) -> None:
        for path in self.wine_generated_menu_entries:
            if not path.is_file():
                continue
            desktop_entry = path.read_text(encoding="utf-8", errors="replace")
            if str(self.prefix) in desktop_entry:
                path.unlink()

    def remove_menu_shortcut(self) -> None:
        if not self.application_menu_entry.is_file():
            return
        desktop_entry = self.application_menu_entry.read_text(
            encoding="utf-8", errors="replace"
        )
        if f"X-AIM59-Prefix={self.prefix}\n" in desktop_entry:
            self.application_menu_entry.unlink()
            if self.application_icon.is_file():
                self.application_icon.unlink()

    def prepare_setup(self) -> None:
        self.check_tools(require_winetricks=True, require_wineboot=True)
        self.verify_patched_dll()

    def setup(self, installer: Path) -> None:
        self.create_prefix()
        self.install_prerequisites()
        self.install_aim(installer)
        self.apply()

    def stop_wine(self) -> None:
        self._run([self.wineserver, "-k"], check=False)

    def _require_aim_files(self) -> None:
        required = [self.aim_dir / "aim.exe", self.aim_dir / "sb.dll"]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise BackendError("AIM installation is incomplete; missing: " + ", ".join(missing))

    def _update_system_ini(self, path: Path) -> None:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        output: list[str] = []
        in_mci = False
        found_section = False
        wrote_key = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if in_mci and not wrote_key:
                    output.append("waveaudio=mciwave.dll")
                    wrote_key = True
                in_mci = stripped.lower() == "[mci]"
                if in_mci:
                    found_section = True
                output.append(line)
                continue

            if in_mci and stripped.lower().startswith("waveaudio="):
                if not wrote_key:
                    output.append("waveaudio=mciwave.dll")
                    wrote_key = True
                continue
            output.append(line)

        if not found_section:
            if output and output[-1] != "":
                output.append("")
            output.extend(["[mci]", "waveaudio=mciwave.dll"])
        elif in_mci and not wrote_key:
            output.append("waveaudio=mciwave.dll")

        path.write_text("\n".join(output) + "\n", encoding="utf-8")

    def apply(self) -> None:
        self.verify_patched_dll()
        if not self.dry_run:
            self._require_aim_files()

        print("→ Registering AIM SuperBuddy component")
        self._run([self.wine, "regsvr32", "/s", r"C:\Program Files\AIM\sb.dll"])
        self.stop_wine()

        aimapi = self.aim_dir / "aimapi.dll"
        aimapi_disabled = self.aim_dir / "aimapi.dll.disabled"
        mciwave = self.system32 / "mciwave.dll"
        mciwave_backup = self.system32 / "mciwave.dll.pre-aim-patch"
        system_ini = self.prefix / "drive_c/windows/system.ini"
        system_ini_backup = self.state_dir / "system.ini.pre-aim-patch"

        print("→ Applying prefix-local compatibility files")
        if not self.dry_run:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            if system_ini.is_file() and not system_ini_backup.exists():
                shutil.copy2(system_ini, system_ini_backup)
            if aimapi.is_file() and not aimapi_disabled.exists():
                aimapi.rename(aimapi_disabled)
            if mciwave.is_file() and not mciwave_backup.exists():
                shutil.copy2(mciwave, mciwave_backup)
            self.system32.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.patched_dll, mciwave)

        print("→ Configuring Wine DLL and MCI mappings")
        self._run(
            [
                self.wine,
                "reg",
                "add",
                r"HKCU\Software\Wine\DllOverrides",
                "/v",
                "mciwave",
                "/t",
                "REG_SZ",
                "/d",
                "native,builtin",
                "/f",
            ]
        )
        for key in (
            r"HKLM\Software\Microsoft\Windows NT\CurrentVersion\MCI",
            r"HKLM\Software\Microsoft\Windows NT\CurrentVersion\MCI32",
        ):
            self._run(
                [
                    self.wine,
                    "reg",
                    "add",
                    key,
                    "/v",
                    "WaveAudio",
                    "/t",
                    "REG_SZ",
                    "/d",
                    "mciwave.dll",
                    "/f",
                ]
            )

        if not self.dry_run:
            self._update_system_ini(system_ini)
        try:
            self.install_menu_shortcut()
        finally:
            self.stop_wine()

        if not self.dry_run:
            state = {
                "schema": 1,
                "manifest": self.manifest["id"],
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "prefix": str(self.prefix),
                "mciwave_sha256": sha256_file(self.patched_dll),
                "wine_version": self.wine_version_prefix,
                "aimapi_disabled": aimapi_disabled.is_file(),
                "mciwave_backup": mciwave_backup.is_file(),
                "system_ini_backup": system_ini_backup.is_file(),
                "application_menu_entry": str(self.application_menu_entry),
                "application_icon": str(self.application_icon),
            }
            (self.state_dir / "state.json").write_text(
                json.dumps(state, indent=2) + "\n", encoding="utf-8"
            )

    def doctor(self) -> list[tuple[bool, str]]:
        checks: list[tuple[bool, str]] = []
        try:
            version = self.check_tools(require_winetricks=False)
            checks.append((True, f"Wine version: {version}"))
        except BackendError as exc:
            checks.append((False, str(exc)))

        checks.extend(
            [
                ((self.prefix / "system.reg").is_file(), f"Wine prefix: {self.prefix}"),
                ((self.aim_dir / "aim.exe").is_file(), "AIM executable installed"),
                ((self.aim_dir / "sb.dll").is_file(), "SuperBuddy component installed"),
                (
                    self.application_menu_entry.is_file()
                    and self.application_icon.is_file(),
                    "Application-menu shortcut installed",
                ),
                (
                    (self.aim_dir / "aimapi.dll.disabled").is_file(),
                    "aimapi.dll disabled",
                ),
            ]
        )
        installed = self.system32 / "mciwave.dll"
        try:
            expected = self._mciwave_variant()["sha256"]
        except BackendError:
            expected = ""
        checks.append(
            (
                installed.is_file() and sha256_file(installed) == expected,
                "Patched mciwave.dll installed",
            )
        )
        checks.append(((self.state_dir / "state.json").is_file(), "Patcher state recorded"))
        return checks

    def launch(self) -> None:
        self.check_tools(require_winetricks=False)
        executable = self.aim_dir / self.manifest["wine"]["executable"]
        if not executable.is_file():
            raise BackendError(f"AIM executable not found: {executable}")
        print(f"→ Launching AIM from {self.prefix}")
        if self.dry_run:
            self._display([self.wine, str(executable)])
            return
        subprocess.Popen([self.wine, str(executable)], env=self.env, cwd=self.aim_dir)

    def rollback(self) -> None:
        self.check_tools(require_winetricks=False, enforce_version=False)
        if not (self.prefix / "system.reg").is_file():
            raise BackendError(f"Wine prefix not found: {self.prefix}")
        print(f"→ Rolling back AIM compatibility changes in {self.prefix}")
        self.stop_wine()
        mciwave = self.system32 / "mciwave.dll"
        mciwave_backup = self.system32 / "mciwave.dll.pre-aim-patch"
        aimapi = self.aim_dir / "aimapi.dll"
        aimapi_disabled = self.aim_dir / "aimapi.dll.disabled"
        system_ini = self.prefix / "drive_c/windows/system.ini"
        system_ini_backup = self.state_dir / "system.ini.pre-aim-patch"

        if not self.dry_run:
            if mciwave_backup.is_file():
                shutil.copy2(mciwave_backup, mciwave)
            if aimapi_disabled.is_file() and not aimapi.exists():
                aimapi_disabled.rename(aimapi)
            if system_ini_backup.is_file():
                shutil.copy2(system_ini_backup, system_ini)

        self._run(
            [
                self.wine,
                "reg",
                "delete",
                r"HKCU\Software\Wine\DllOverrides",
                "/v",
                "mciwave",
                "/f",
            ],
            check=False,
        )
        if not self.dry_run:
            state_file = self.state_dir / "state.json"
            if state_file.is_file():
                state = json.loads(state_file.read_text(encoding="utf-8"))
                state["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
                state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            self.remove_menu_shortcut()
        self.stop_wine()
