from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..download import sha256_file
from .base import AimServerSettings, BackendError, SetupConfiguration, SetupPresentation


_AIM_SERVER_REGISTRY_KEY = (
    r"HKCU\Software\America Online\AOL Instant Messenger (TM)\CurrentVersion\Server"
)
_AOL_DESKTOP_SHORTCUT_NAME = "Free AOL & Unlimited Internet.lnk"
_AIM_UNINSTALLER_NAME = "uninstll.exe"
_AIM_UNINSTALL_LOG = r"C:\Program Files\AIM\install.log"
_WINE_USERPROFILE_PATTERN = re.compile(
    r'^"USERPROFILE"="C:\\\\users\\\\([^"\\\\/]+)"$',
    re.MULTILINE,
)
_REGISTRY_STRING_PATTERN = re.compile(r'^"(?P<name>[^"]+)"="(?P<value>.*)"$')
_REGISTRY_DWORD_PATTERN = re.compile(r'^"(?P<name>[^"]+)"=dword:(?P<value>[0-9a-fA-F]+)$')


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
        self.setup_configuration = SetupConfiguration()

    @property
    def aim_dir(self) -> Path:
        return self.prefix / self.manifest["wine"]["aim_directory"]

    @property
    def system32(self) -> Path:
        return self.prefix / "drive_c/windows/system32"

    @property
    def state_dir(self) -> Path:
        return self.prefix / ".rrlzAIM"

    @property
    def state_file(self) -> Path:
        return self.state_dir / "state.json"

    @property
    def aol_shortcut_backup_directory(self) -> Path:
        return self.state_dir / "aol-desktop-shortcuts"

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
        return self.xdg_data_home / "applications" / f"rrlzAIMlinux-{self._prefix_id}.desktop"

    @property
    def wine_generated_menu_entries(self) -> tuple[Path, ...]:
        applications = self.xdg_data_home / "applications"
        return (
            applications / "wine/Programs/AOL Instant Messenger/AIM.desktop",
            applications / "wine-Programs-AOL Instant Messenger-AIM.desktop",
        )

    @property
    def application_icon(self) -> Path:
        return self.xdg_data_home / "rrlzAIMlinux/icons" / f"{self._prefix_id}.png"

    @property
    def _prefix_id(self) -> str:
        """Stable per-prefix filename fragment for independently managed launchers."""
        return hashlib.sha256(str(self.prefix).encode("utf-8")).hexdigest()[:16]

    @property
    def installer_menu_link(self) -> Path:
        return self.prefix / (
            "drive_c/ProgramData/Microsoft/Windows/Start Menu/Programs/"
            "AOL Instant Messenger/AIM.lnk"
        )

    @property
    def wine_users_directory(self) -> Path:
        return self.prefix / "drive_c/users"

    @property
    def setup_presentation(self) -> SetupPresentation:
        server = self.setup_configuration.server
        server_line = (
            f"AIM server: {server.host}:{server.port}"
            if server is not None
            else "AIM server: keep AIM's existing setting"
        )
        shortcut_line = (
            "AOL desktop shortcut: remove exact 'Free AOL & Unlimited Internet.lnk'"
            if self.setup_configuration.remove_aol_desktop_shortcut
            else "AOL desktop shortcut: leave unchanged"
        )
        launcher_line = (
            "XDG AIM launcher: create"
            if self.setup_configuration.create_xdg_launcher
            else "XDG AIM launcher: do not create"
        )
        return SetupPresentation(
            confirmation_lines=(
                f"Wine prefix: {self.prefix}",
                f"Patched DLL: {self.patched_dll}",
                server_line,
                shortcut_line,
                launcher_line,
            ),
            launch_command=f"rrlzAIMlinux launch --prefix {self.prefix}",
        )

    def configure_setup(self, configuration: SetupConfiguration) -> None:
        self.setup_configuration = configuration

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
        cwd: Path | None = None,
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
            cwd=cwd,
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
            "Name=rrlzAIM - AIM 5.9\n"
            "Comment=Launch AIM 5.9.3861 with its compatibility prefix\n"
            f"Exec={command}\n"
            f"Path={self.aim_dir}\n"
            f"Icon={self.application_icon}\n"
            "Terminal=false\n"
            "StartupNotify=true\n"
            "StartupWMClass=aim.exe\n"
            "Categories=Network;InstantMessaging;\n"
            "Keywords=AIM;AOL;Chat;Instant Messaging;\n"
            f"X-RrlzAIMlinux-Prefix={self.prefix}\n"
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
        if f"X-RrlzAIMlinux-Prefix={self.prefix}\n" in desktop_entry:
            self.application_menu_entry.unlink()
            if self.application_icon.is_file():
                self.application_icon.unlink()

    def prepare_setup(self) -> None:
        self.check_tools(require_winetricks=True, require_wineboot=True)
        self.verify_patched_dll()
        if not self.dry_run and (self.aim_dir / "aim.exe").is_file():
            raise BackendError(
                f"AIM is already installed in this Wine prefix: {self.prefix}\n"
                "Use 'rrlzAIMlinux launch' to run it or 'rrlzAIMlinux uninstall' "
                "before a fresh setup."
            )

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

    def _require_win32_prefix(self) -> None:
        system_reg = self.prefix / "system.reg"
        if not system_reg.is_file():
            raise BackendError(f"Wine prefix not found: {self.prefix}")
        header = system_reg.read_text(encoding="utf-8", errors="ignore")[:512]
        if "#arch=win64" in header:
            raise BackendError(f"Existing prefix is 64-bit, not win32: {self.prefix}")
        if "#arch=win32" not in header:
            raise BackendError(f"Wine prefix architecture could not be verified: {self.prefix}")

    def _require_aim_executable(self) -> None:
        executable = self.aim_dir / self.manifest["wine"]["executable"]
        if not executable.is_file():
            raise BackendError(f"AIM executable not found: {executable}")

    def _write_server_settings(self, settings: AimServerSettings) -> None:
        print(f"→ Configuring AIM server: {settings.host}:{settings.port}")
        self._run(
            [
                self.wine,
                "reg",
                "add",
                _AIM_SERVER_REGISTRY_KEY,
                "/v",
                "Host",
                "/t",
                "REG_SZ",
                "/d",
                settings.host,
                "/f",
            ]
        )
        self._run(
            [
                self.wine,
                "reg",
                "add",
                _AIM_SERVER_REGISTRY_KEY,
                "/v",
                "Port",
                "/t",
                "REG_DWORD",
                "/d",
                str(settings.port),
                "/f",
            ]
        )

    def set_server(self, settings: AimServerSettings) -> None:
        if not self.dry_run:
            self._require_win32_prefix()
            self._require_aim_executable()
        self._write_server_settings(settings)

    @staticmethod
    def _registry_values(path: Path, key: str) -> dict[str, str]:
        """Read simple REG_SZ and REG_DWORD values from a Wine .reg file."""
        if not path.is_file():
            return {}
        target = key.replace("\\", "\\\\").casefold()
        in_target = False
        values: dict[str, str] = {}
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_target = stripped[1:-1].casefold() == target
                continue
            if not in_target:
                continue
            string_match = _REGISTRY_STRING_PATTERN.match(stripped)
            if string_match:
                values[string_match["name"].casefold()] = string_match["value"]
                continue
            dword_match = _REGISTRY_DWORD_PATTERN.match(stripped)
            if dword_match:
                values[dword_match["name"].casefold()] = dword_match["value"]
        return values

    def _user_registry_values(self, key: str) -> dict[str, str]:
        return self._registry_values(self.prefix / "user.reg", key)

    def current_server_status(self) -> str:
        """Read the prefix-local current-user setting without launching Wine."""
        if not (self.prefix / "user.reg").is_file():
            return "Server: not available (Wine user registry is missing)"
        values = self._user_registry_values(_AIM_SERVER_REGISTRY_KEY.removeprefix("HKCU\\"))
        host = values.get("host")
        try:
            port = int(values["port"], 16)
        except (KeyError, ValueError):
            port = None
        if host and port:
            return f"Server: {host}:{port}"
        return "Server: unchanged or not set"

    @staticmethod
    def _casefold_file(directory: Path, filename: str) -> bool:
        if (directory / filename).is_file():
            return True
        if not directory.is_dir():
            return False
        try:
            return any(
                candidate.is_file() and candidate.name.casefold() == filename.casefold()
                for candidate in directory.iterdir()
            )
        except OSError:
            return False

    def _system_ini_maps_waveaudio(self) -> bool:
        system_ini = self.prefix / "drive_c/windows/system.ini"
        if not system_ini.is_file():
            return False
        in_mci = False
        try:
            lines = system_ini.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_mci = stripped.casefold() == "[mci]"
                continue
            if in_mci and stripped.casefold() == "waveaudio=mciwave.dll":
                return True
        return False

    def _find_aim_uninstaller(self) -> Path:
        if not self.aim_dir.is_dir():
            raise BackendError(f"AIM installation directory not found: {self.aim_dir}")
        matches = [
            candidate
            for candidate in self.aim_dir.iterdir()
            if (
                candidate.is_file()
                and not candidate.is_symlink()
                and candidate.name.casefold() == _AIM_UNINSTALLER_NAME
            )
        ]
        if not matches:
            raise BackendError(
                "AIM's expected prefix-local uninstaller was not found: "
                f"{self.aim_dir / _AIM_UNINSTALLER_NAME}"
            )
        if len(matches) > 1:
            raise BackendError(
                "More than one AIM uninstaller matches the expected name in: "
                f"{self.aim_dir}"
            )
        return matches[0]

    def _restore_aimapi_for_uninstall(self) -> bool:
        aimapi = self.aim_dir / "aimapi.dll"
        disabled = self.aim_dir / "aimapi.dll.disabled"
        if aimapi.is_file():
            if disabled.is_file():
                raise BackendError(
                    "Both aimapi.dll and aimapi.dll.disabled exist; resolve this "
                    f"manually before uninstalling: {self.aim_dir}"
                )
            return False
        if not disabled.is_file():
            raise BackendError(
                "AIM's uninstaller requires aimapi.dll, but neither the original "
                f"nor the patcher-disabled file was found: {self.aim_dir}"
            )
        disabled.rename(aimapi)
        print("→ Restored aimapi.dll for AIM's uninstaller")
        return True

    def _re_disable_aimapi_after_unsuccessful_uninstall(self) -> None:
        aimapi = self.aim_dir / "aimapi.dll"
        disabled = self.aim_dir / "aimapi.dll.disabled"
        if aimapi.is_file() and not disabled.exists():
            aimapi.rename(disabled)
            print("→ Restored the compatibility aimapi.dll disablement")

    def _prefix_removal_target(self) -> Path:
        if self.prefix.is_symlink():
            raise BackendError(
                "Refusing to recursively remove a Wine prefix represented by a "
                f"symbolic link: {self.prefix}"
            )
        try:
            target = self.prefix.resolve(strict=True)
        except OSError as exc:
            raise BackendError(f"Wine prefix not found: {self.prefix}") from exc
        protected = {
            Path("/").resolve(),
            Path.home().resolve(),
            Path.cwd().resolve(),
        }
        if target in protected or target == target.parent:
            raise BackendError(
                "Refusing to recursively remove a broad directory as a Wine prefix: "
                f"{target}"
            )
        return target

    def _remove_completed_prefix(self, prefix: Path) -> None:
        print(f"→ Removing completed AIM Wine prefix: {prefix}")
        shutil.rmtree(prefix)
        if prefix.exists():
            raise BackendError(f"Wine prefix could not be removed: {prefix}")

    def uninstall(self) -> None:
        if self.dry_run:
            uninstaller = self.aim_dir / _AIM_UNINSTALLER_NAME
            print(f"→ Would run AIM's uninstaller in {self.prefix}")
            self._run(
                [self.wine, str(uninstaller), "-LOG=", _AIM_UNINSTALL_LOG, "-OEM="],
                cwd=self.aim_dir,
            )
            self._run([self.wineserver, "-w"])
            print(f"  → Would remove {self.application_menu_entry}")
            print(f"  → Would recursively remove {self.prefix}")
            return

        self._require_win32_prefix()
        self._require_aim_executable()
        prefix = self._prefix_removal_target()
        uninstaller = self._find_aim_uninstaller()
        restored_aimapi = self._restore_aimapi_for_uninstall()
        print(f"→ Running AIM's uninstaller from {uninstaller}")
        try:
            self._run(
                [self.wine, str(uninstaller), "-LOG=", _AIM_UNINSTALL_LOG, "-OEM="],
                cwd=self.aim_dir,
            )
            print("→ Waiting for the AIM uninstaller to exit")
            self._run([self.wineserver, "-w"])
        except (OSError, subprocess.SubprocessError):
            if restored_aimapi:
                self._re_disable_aimapi_after_unsuccessful_uninstall()
            raise

        if (self.aim_dir / self.manifest["wine"]["executable"]).is_file():
            if restored_aimapi:
                self._re_disable_aimapi_after_unsuccessful_uninstall()
            raise BackendError(
                "AIM's uninstaller finished but aim.exe is still present. The "
                "project menu entry and Wine prefix were left unchanged."
            )

        self.remove_menu_shortcut()
        self._remove_wine_generated_menu_entries()
        self._remove_completed_prefix(prefix)

    def _load_state(self) -> dict[str, Any]:
        if not self.state_file.is_file():
            return {}
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BackendError(f"Patcher state is unreadable: {self.state_file}") from exc
        if not isinstance(state, dict):
            raise BackendError(f"Patcher state is malformed: {self.state_file}")
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def _current_wine_user_directory(self) -> Path | None:
        user_registry = self.prefix / "user.reg"
        if not user_registry.is_file():
            return None
        try:
            contents = user_registry.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        match = _WINE_USERPROFILE_PATTERN.search(contents)
        if match is None:
            return None
        user_name = match.group(1)
        if user_name in (".", ".."):
            return None
        return self.wine_users_directory / user_name

    def _aol_desktop_shortcut_paths(self) -> tuple[Path, ...]:
        current_user = self._current_wine_user_directory()
        paths = [] if current_user is None else [
            current_user / "Desktop" / _AOL_DESKTOP_SHORTCUT_NAME
        ]
        paths.append(
            self.wine_users_directory
            / "Public"
            / "Desktop"
            / _AOL_DESKTOP_SHORTCUT_NAME
        )

        deduplicated: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            try:
                key = str(path.resolve(strict=False)).casefold()
            except OSError:
                key = str(path).casefold()
            if key not in seen:
                seen.add(key)
                deduplicated.append(path)
        return tuple(deduplicated)

    def _aol_shortcut_backup_records(
        self,
        state: dict[str, Any],
    ) -> list[dict[str, str]]:
        records = state.get("aol_desktop_shortcut_backups", [])
        if not isinstance(records, list):
            raise BackendError("AOL desktop shortcut backup state is malformed")
        validated: list[dict[str, str]] = []
        for record in records:
            if not isinstance(record, dict):
                raise BackendError("AOL desktop shortcut backup state is malformed")
            target = record.get("target")
            backup = record.get("backup")
            if not isinstance(target, str) or not isinstance(backup, str):
                raise BackendError("AOL desktop shortcut backup state is malformed")
            validated.append({"target": target, "backup": backup})
        return validated

    def _record_aol_shortcut_backup(self, path: Path) -> None:
        try:
            target = path.resolve(strict=False)
        except OSError as exc:
            raise BackendError(f"Could not resolve AOL desktop shortcut: {path}") from exc
        target_text = str(target)
        state = self._load_state()
        records = self._aol_shortcut_backup_records(state)
        backup_name = hashlib.sha256(target_text.encode("utf-8")).hexdigest() + ".lnk"
        backup = self.aol_shortcut_backup_directory / backup_name
        existing_record = next(
            (record for record in records if record["target"] == target_text),
            None,
        )
        if existing_record is not None and existing_record["backup"] != backup_name:
            raise BackendError(
                "Recorded AOL desktop shortcut backup does not match its target: "
                f"{target}"
            )
        if existing_record is None and backup.exists():
            raise BackendError(
                "An untracked AOL desktop shortcut backup already exists: "
                f"{backup}"
            )
        self.aol_shortcut_backup_directory.mkdir(parents=True, exist_ok=True)
        temporary = backup.with_name(backup.name + ".tmp")
        try:
            shutil.copy2(path, temporary)
            temporary.replace(backup)
        except OSError as exc:
            raise BackendError(f"Could not back up AOL desktop shortcut: {path}") from exc
        if existing_record is None:
            records.append({"target": target_text, "backup": backup_name})
            state["aol_desktop_shortcut_backups"] = records
            self._write_state(state)

    def remove_aol_desktop_shortcut(self) -> None:
        print("→ Removing optional AOL desktop shortcut")
        if self._current_wine_user_directory() is None:
            print("  ! Could not determine the active Wine user; skipped its Desktop")
        found = 0
        for path in self._aol_desktop_shortcut_paths():
            if path.is_symlink():
                found += 1
                print(f"  ! Skipped symbolic-link AOL desktop shortcut: {path}")
                continue
            if not path.is_file():
                continue
            found += 1
            if self.dry_run:
                print(f"  → Would remove {path}")
                continue
            try:
                self._record_aol_shortcut_backup(path)
                path.unlink()
            except (BackendError, OSError) as exc:
                print(f"  ! Could not remove {path}: {exc}")
                continue
            print(f"  ✓ Removed {path}")

        if found == 0:
            print("  → The optional AOL desktop shortcut was not present")

    def restore_aol_desktop_shortcuts(self) -> None:
        state = self._load_state()
        records = self._aol_shortcut_backup_records(state)
        if not records:
            return
        print("→ Restoring project-backed AOL desktop shortcuts")
        for record in records:
            target = Path(record["target"])
            backup_name = record["backup"]
            expected_name = (
                hashlib.sha256(record["target"].encode("utf-8")).hexdigest()
                + ".lnk"
            )
            backup = self.aol_shortcut_backup_directory / backup_name
            if (
                target.name != _AOL_DESKTOP_SHORTCUT_NAME
                or backup_name != expected_name
                or not backup.is_file()
            ):
                print(f"  ! Could not restore recorded AOL desktop shortcut: {target}")
                continue
            if target.exists() or target.is_symlink():
                print(f"  → Left existing AOL desktop shortcut unchanged: {target}")
                continue
            if not target.parent.is_dir():
                print(f"  ! Could not restore missing desktop directory: {target.parent}")
                continue
            try:
                shutil.copy2(backup, target)
            except OSError as exc:
                print(f"  ! Could not restore {target}: {exc}")
                continue
            print(f"  ✓ Restored {target}")

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
            if self.setup_configuration.create_xdg_launcher:
                self.install_menu_shortcut()
            else:
                print("→ Leaving the XDG AIM launcher uncreated")
        finally:
            self.stop_wine()

        if self.setup_configuration.server is not None:
            try:
                self._write_server_settings(self.setup_configuration.server)
            finally:
                self.stop_wine()
        else:
            print("→ Leaving AIM's existing server setting unchanged")
        if self.setup_configuration.remove_aol_desktop_shortcut:
            self.remove_aol_desktop_shortcut()

        if not self.dry_run:
            previous_state = self._load_state()
            shortcut_backups = self._aol_shortcut_backup_records(previous_state)
            state = {
                "schema": 1,
                "manifest": self.manifest["id"],
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "prefix": str(self.prefix),
                "mciwave_sha256": sha256_file(self.patched_dll),
                "wine_version": self.wine_version_prefix,
                "aimapi_disabled": aimapi_disabled.is_file(),
                "superbuddy_registered": True,
                "mciwave_backup": mciwave_backup.is_file(),
                "system_ini_backup": system_ini_backup.is_file(),
                "mciwave_override": True,
                "mci_waveaudio_mappings": True,
                "application_menu_entry": str(self.application_menu_entry),
                "application_icon": str(self.application_icon),
            }
            if shortcut_backups:
                state["aol_desktop_shortcut_backups"] = shortcut_backups
            self._write_state(state)

    def doctor(self) -> list[tuple[bool, str]]:
        checks: list[tuple[bool, str]] = []
        try:
            version = self.check_tools(require_winetricks=False)
            checks.append((True, f"Wine version: {version}"))
        except BackendError as exc:
            checks.append((False, str(exc)))

        system_registry = self.prefix / "system.reg"
        prefix_exists = system_registry.is_file()
        checks.append((prefix_exists, f"Wine prefix: {self.prefix}"))
        architecture = ""
        if prefix_exists:
            try:
                architecture = system_registry.read_text(
                    encoding="utf-8", errors="ignore"
                )[:512]
            except OSError:
                pass
        checks.append(("#arch=win32" in architecture, "Wine prefix architecture: win32"))
        wine_settings = self._user_registry_values(r"Software\Wine")
        checks.append(
            (wine_settings.get("version", "").casefold() == "winxp", "Wine Windows version: XP")
        )
        checks.extend(
            [
                (self._casefold_file(self.system32, "mfc40.dll"), "mfc40 installed"),
                ((self.aim_dir / "aim.exe").is_file(), "AIM executable installed"),
                ((self.aim_dir / "sb.dll").is_file(), "SuperBuddy component installed"),
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
        overrides = self._user_registry_values(r"Software\Wine\DllOverrides")
        checks.append(
            (
                overrides.get("mciwave", "").casefold() == "native,builtin",
                "mciwave override: native,builtin",
            )
        )
        mci = self._registry_values(
            system_registry,
            r"Software\Microsoft\Windows NT\CurrentVersion\MCI",
        )
        mci32 = self._registry_values(
            system_registry,
            r"Software\Microsoft\Windows NT\CurrentVersion\MCI32",
        )
        checks.append(
            (
                mci.get("waveaudio", "").casefold() == "mciwave.dll"
                and mci32.get("waveaudio", "").casefold() == "mciwave.dll",
                "MCI and MCI32 WaveAudio mappings",
            )
        )
        checks.append((self._system_ini_maps_waveaudio(), "system.ini WaveAudio mapping"))
        try:
            state = self._load_state()
        except BackendError:
            state = {}
        checks.append(
            (state.get("superbuddy_registered") is True, "SuperBuddy registration recorded")
        )
        checks.append((self.state_file.is_file(), "Patcher state recorded"))
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
        subprocess.Popen(
            [self.wine, str(executable)],
            env=self.env,
            cwd=self.aim_dir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

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
            self.restore_aol_desktop_shortcuts()
            if self.state_file.is_file():
                state = self._load_state()
                state["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
                self._write_state(state)
            self.remove_menu_shortcut()
        self.stop_wine()
