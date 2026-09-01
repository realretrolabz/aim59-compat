from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..download import sha256_file


class BackendError(RuntimeError):
    pass


class WineBackend:
    def __init__(
        self,
        manifest: dict[str, Any],
        prefix: Path,
        patched_dll: Path,
        *,
        wine: str = "wine",
        wineboot: str = "wineboot",
        wineserver: str = "wineserver",
        winetricks: str = "winetricks",
        dry_run: bool = False,
    ) -> None:
        self.manifest = manifest
        self.prefix = prefix
        self.patched_dll = patched_dll
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
        expected = self.manifest["wine"]["version_prefix"]
        if result.returncode != 0 or (enforce_version and not version.startswith(expected)):
            raise BackendError(
                f"This backend is validated only with {expected}. Detected: {version or '<none>'}"
            )
        return version

    def verify_patched_dll(self) -> str:
        if not self.patched_dll.is_file():
            raise BackendError(f"Patched mciwave DLL not found: {self.patched_dll}")
        digest = sha256_file(self.patched_dll)
        expected = self.manifest["mciwave"]["sha256"]
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
        self._run([self.wine, str(installer)])
        self.stop_wine()
        if not self.dry_run:
            self._require_aim_files()

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
            state = {
                "schema": 1,
                "manifest": self.manifest["id"],
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "prefix": str(self.prefix),
                "mciwave_sha256": sha256_file(self.patched_dll),
                "aimapi_disabled": aimapi_disabled.is_file(),
                "mciwave_backup": mciwave_backup.is_file(),
                "system_ini_backup": system_ini_backup.is_file(),
            }
            (self.state_dir / "state.json").write_text(
                json.dumps(state, indent=2) + "\n", encoding="utf-8"
            )
        self.stop_wine()

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
                    (self.aim_dir / "aimapi.dll.disabled").is_file(),
                    "aimapi.dll disabled",
                ),
            ]
        )
        installed = self.system32 / "mciwave.dll"
        expected = self.manifest["mciwave"]["sha256"]
        checks.append(
            (
                installed.is_file() and sha256_file(installed) == expected,
                "Patched mciwave.dll installed",
            )
        )
        checks.append(((self.state_dir / "state.json").is_file(), "Patcher state recorded"))
        return checks

    def launch(self) -> None:
        executable = self.aim_dir / self.manifest["wine"]["executable"]
        if not executable.is_file():
            raise BackendError(f"AIM executable not found: {executable}")
        print(f"→ Launching AIM from {self.prefix}")
        if self.dry_run:
            self._display([self.wine, str(executable)])
            return
        subprocess.Popen([self.wine, str(executable)], env=self.env, cwd=self.aim_dir)

    def rollback(self) -> None:
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
        self.stop_wine()
