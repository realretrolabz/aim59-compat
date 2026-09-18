from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from rrlzAIM.backends import (
    BackendTarget,
    WineBackendOptions,
    create_backend,
    select_backend_target,
)
from rrlzAIM.backends.base import (
    DEFAULT_AIM_SERVER_HOST,
    DEFAULT_AIM_SERVER_PORT,
    AimServerSettings,
    BackendError,
    SetupConfiguration,
    SetupPresentation,
)
from rrlzAIM.backends.wine import WineBackend
from rrlzAIM.cli import (
    build_parser,
    default_aim_prefix_root,
    default_prefix,
    default_dll,
    main,
    resolve_server_settings,
    resolve_setup_configuration,
    verify_installer,
    wine_options_from_args,
)
from rrlzAIM.download import DownloadError, _OldVersionFormParser, download_direct
from rrlzAIM.managed_prefixes import ManagedPrefixCatalog
from rrlzAIM.manager import TerminalDisplay
from rrlzAIM.manifest import load_manifest
from rrlzAIM.orchestration import run_doctor, run_launch, run_rollback, run_setup


class ManifestTests(unittest.TestCase):
    def test_supported_manifest(self) -> None:
        manifest = load_manifest()
        self.assertEqual(manifest["version"], "5.9.3861")
        self.assertEqual(
            manifest["wine"]["version_prefixes"],
            ["wine-9.0", "wine-10.0"],
        )
        self.assertEqual(
            set(manifest["mciwave"]["variants"]),
            {"wine-9.0", "wine-10.0"},
        )
        self.assertEqual(len(manifest["installer"]["sha256"][0]), 64)


class DownloadParserTests(unittest.TestCase):
    def test_oldversion_form_is_extracted(self) -> None:
        parser = _OldVersionFormParser()
        parser.feed(
            '<form action="/software/download/token/" method="POST">'
            '<input type="hidden" name="csrfmiddlewaretoken" value="secret">'
            "</form>"
        )
        self.assertEqual(parser.action, "/software/download/token/")
        self.assertEqual(parser.csrf, "secret")

    def test_direct_download_rejects_non_http_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(DownloadError):
                download_direct("file:///etc/passwd", Path(temporary) / "installer.exe")


class InstallerVerificationTests(unittest.TestCase):
    def test_known_hash_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            installer = Path(temporary) / "aim.exe"
            installer.write_bytes(b"test installer")
            digest = hashlib.sha256(installer.read_bytes()).hexdigest()
            manifest = {"installer": {"sha256": [digest], "size": installer.stat().st_size}}
            self.assertEqual(
                verify_installer(installer, manifest, allow_unverified=False), digest
            )


class ManagedPrefixTests(unittest.TestCase):
    def test_catalog_records_only_explicit_guided_install_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = ManagedPrefixCatalog(root / "managed-prefixes.json")
            untracked = root / "untracked"
            (untracked / "prefix").mkdir(parents=True)
            managed = root / "my-aim"

            self.assertEqual(catalog.entries(), ())
            catalog.record(managed)

            self.assertEqual(catalog.entries()[0].root, managed.resolve())
            self.assertEqual(catalog.active().prefix, managed.resolve() / "prefix")
            catalog.forget(managed)
            self.assertEqual(catalog.entries(), ())

    def test_aimwineprefix_selects_the_parent_with_a_fixed_prefix_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "custom-data"
            with patch.dict(os.environ, {"AIMwineprefix": str(root)}):
                self.assertEqual(default_aim_prefix_root(), root.resolve())
                self.assertEqual(default_prefix(), root.resolve() / "prefix")
                args = build_parser().parse_args(["doctor", "--aim-prefix", str(root)])
                self.assertEqual(wine_options_from_args(args).prefix, root.resolve() / "prefix")

    def test_terminal_manager_hides_the_logo_without_blocking_small_terminals(self) -> None:
        display = TerminalDisplay()
        self.assertGreater(display.logo_width, 120)
        output = io.StringIO()
        with (
            patch(
                "rrlzAIM.manager.shutil.get_terminal_size",
                return_value=os.terminal_size((80, 24)),
            ),
            contextlib.redirect_stdout(output),
        ):
            self.assertFalse(display.has_room_for_logo)
            self.assertEqual(display.box_width, 78)
            display.main_menu(None)

        self.assertIn("7. Exit", output.getvalue())
        self.assertNotIn("▓", output.getvalue())

        with patch(
            "rrlzAIM.manager.shutil.get_terminal_size",
            return_value=os.terminal_size((display.logo_width, len(display.logo) + 10)),
        ):
            self.assertTrue(display.has_room_for_logo)
            self.assertEqual(display.box_width, display.logo_width)


class ServerConfigurationTests(unittest.TestCase):
    def test_server_settings_validate_host_and_port(self) -> None:
        self.assertEqual(
            AimServerSettings(" server.example ", 5191),
            AimServerSettings("server.example", 5191),
        )
        for host, port in (
            ("", 5190),
            ("server\nname", 5190),
            ("server", True),
            ("server", 0),
            ("server", 65536),
        ):
            with self.subTest(host=host, port=port):
                with self.assertRaises(ValueError):
                    AimServerSettings(host, port)

    def test_guided_setup_selects_custom_server_and_shortcut_cleanup(self) -> None:
        args = build_parser().parse_args(["setup", "--source", "oldversion"])
        with patch(
            "builtins.input",
            side_effect=["3", "oscar.example", "12345", "yes"],
        ), contextlib.redirect_stdout(io.StringIO()):
            configuration = resolve_setup_configuration(args)

        self.assertEqual(
            configuration,
            SetupConfiguration(
                server=AimServerSettings("oscar.example", 12345),
                remove_aol_desktop_shortcut=True,
            ),
        )

    def test_noninteractive_setup_keeps_existing_server_without_prompting(self) -> None:
        args = build_parser().parse_args(
            ["setup", "--source", "oldversion", "--non-interactive"]
        )
        with patch("builtins.input") as prompt:
            configuration = resolve_setup_configuration(args)

        self.assertEqual(configuration, SetupConfiguration())
        prompt.assert_not_called()

    def test_yes_setup_keeps_existing_server_without_prompting(self) -> None:
        args = build_parser().parse_args(
            ["setup", "--source", "oldversion", "--yes"]
        )
        with patch("builtins.input") as prompt:
            configuration = resolve_setup_configuration(args)

        self.assertEqual(configuration, SetupConfiguration())
        prompt.assert_not_called()

    def test_explicit_realretrolabz_choice_uses_the_pinned_default(self) -> None:
        args = build_parser().parse_args(
            [
                "setup",
                "--source",
                "oldversion",
                "--server",
                "realretrolabz",
                "--remove-aol-desktop-shortcut",
                "--yes",
            ]
        )
        self.assertEqual(
            resolve_setup_configuration(args),
            SetupConfiguration(
                server=AimServerSettings(
                    DEFAULT_AIM_SERVER_HOST,
                    DEFAULT_AIM_SERVER_PORT,
                ),
                remove_aol_desktop_shortcut=True,
            ),
        )

    def test_interactive_set_server_does_not_offer_keep(self) -> None:
        args = build_parser().parse_args(["set-server"])
        output = io.StringIO()
        with (
            patch("builtins.input", side_effect=["2", "oscar.example", "5191"]),
            contextlib.redirect_stdout(output),
        ):
            settings = resolve_server_settings(
                args,
                prompt_if_unspecified=True,
                allow_keep=False,
            )

        self.assertEqual(settings, AimServerSettings("oscar.example", 5191))
        self.assertNotIn("Keep AIM", output.getvalue())


class ReleaseLayoutTests(unittest.TestCase):
    def test_release_verifier_has_no_retired_frontend_checksum_gate(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = (root / "scripts" / "verify-release.py").read_text(encoding="utf-8")
        makefile = (root / "Makefile").read_text(encoding="utf-8")
        repository_check = (root / "scripts" / "verify-repo.sh").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("--require-published-bundle-checksum", verifier)
        self.assertNotIn("Lutris", verifier)
        self.assertNotIn("--require-published-bundle-checksum", makefile)
        self.assertIn("python3 scripts/verify-release.py", repository_check)

    def test_adjacent_release_dll_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = root / "rrlzAIMlinux"
            dll = root / "mciwave-wine9-x86-aim.dll"
            launcher.touch()
            dll.touch()
            with patch("sys.argv", [str(launcher)]):
                self.assertEqual(default_dll(), dll)

    def test_adjacent_wine10_dll_can_seed_auto_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = root / "rrlzAIMlinux"
            dll = root / "mciwave-wine10-x86-aim.dll"
            launcher.touch()
            dll.touch()
            with patch("sys.argv", [str(launcher)]):
                self.assertEqual(default_dll(), dll)


class BackendSelectionTests(unittest.TestCase):
    def test_build_targets_match_their_hosts(self) -> None:
        self.assertIs(
            select_backend_target("wine", host_platform="linux"),
            BackendTarget.WINE,
        )
        self.assertIs(
            select_backend_target("windows", host_platform="win32"),
            BackendTarget.WINDOWS,
        )

    def test_wine_target_is_rejected_on_windows(self) -> None:
        with self.assertRaisesRegex(BackendError, "cannot run on host 'win32'"):
            select_backend_target(BackendTarget.WINE, host_platform="win32")

    def test_windows_target_is_rejected_on_linux(self) -> None:
        with self.assertRaisesRegex(BackendError, "cannot run on host 'linux'"):
            select_backend_target(BackendTarget.WINDOWS, host_platform="linux")

    def test_unsupported_host_is_rejected(self) -> None:
        with self.assertRaisesRegex(BackendError, "Unsupported host platform: darwin"):
            select_backend_target(BackendTarget.WINE, host_platform="darwin")

    def test_windows_backend_is_not_speculatively_implemented(self) -> None:
        with self.assertRaisesRegex(BackendError, "not implemented or supported"):
            create_backend({}, BackendTarget.WINDOWS)

    def test_wine_target_constructs_the_existing_backend(self) -> None:
        options = WineBackendOptions(
            prefix=Path("/prefix"),
            patched_dll=Path("/mciwave.dll"),
            wine="wine9",
            dry_run=True,
        )
        backend = create_backend(
            load_manifest(),
            BackendTarget.WINE,
            wine_options=options,
        )

        self.assertIsInstance(backend, WineBackend)
        self.assertEqual(backend.prefix, options.prefix)
        self.assertEqual(backend.patched_dll, options.patched_dll)
        self.assertEqual(backend.wine, "wine9")
        self.assertTrue(backend.dry_run)


class OrchestrationTests(unittest.TestCase):
    def test_setup_preserves_preflight_acquisition_and_apply_order(self) -> None:
        events: list[object] = []
        installer = Path("/external-cache/aim593861.exe")
        backend = Mock()
        backend.setup_presentation = SetupPresentation(
            confirmation_lines=("Wine prefix: /prefix", "Patched DLL: /mciwave.dll"),
            launch_command="rrlzAIMlinux launch --prefix /prefix",
        )
        backend.prepare_setup.side_effect = lambda: events.append("prepare")
        backend.setup.side_effect = lambda path: events.append(("setup", path))

        def acquire() -> Path:
            events.append("acquire")
            return installer

        def confirm(presentation: SetupPresentation) -> None:
            events.append(("confirm", presentation))

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run_setup(backend, acquire_installer=acquire, confirm=confirm)

        self.assertEqual(
            events,
            [
                "prepare",
                "acquire",
                ("confirm", backend.setup_presentation),
                ("setup", installer),
            ],
        )
        self.assertEqual(
            output.getvalue(),
            "\n✓ AIM compatibility setup completed\n"
            "  Run: rrlzAIMlinux launch --prefix /prefix\n",
        )

    def test_setup_configures_after_installer_acquisition_and_before_confirmation(self) -> None:
        events: list[object] = []
        installer = Path("/external-cache/aim593861.exe")
        backend = Mock()
        backend.setup_presentation = SetupPresentation(
            confirmation_lines=("Wine prefix: /prefix",),
            launch_command="rrlzAIMlinux launch --prefix /prefix",
        )
        backend.prepare_setup.side_effect = lambda: events.append("prepare")
        backend.setup.side_effect = lambda path: events.append(("setup", path))

        def acquire() -> Path:
            events.append("acquire")
            return installer

        def configure() -> None:
            events.append("configure")

        def confirm(_: SetupPresentation) -> None:
            events.append("confirm")

        with contextlib.redirect_stdout(io.StringIO()):
            run_setup(
                backend,
                acquire_installer=acquire,
                configure=configure,
                confirm=confirm,
            )

        self.assertEqual(
            events,
            ["prepare", "acquire", "configure", "confirm", ("setup", installer)],
        )

    def test_doctor_launch_and_rollback_delegate_to_backend(self) -> None:
        backend = Mock()
        backend.doctor.return_value = [(True, "ready"), (False, "missing")]
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            self.assertEqual(run_doctor(backend), 1)
            run_launch(backend)
            run_rollback(backend)

        backend.launch.assert_called_once_with()
        backend.rollback.assert_called_once_with()
        self.assertEqual(
            output.getvalue(),
            "✓ ready\n✗ missing\n✓ Compatibility rollback completed\n",
        )


class CliBackendRegressionTests(unittest.TestCase):
    def test_setup_dispatches_through_selected_backend(self) -> None:
        backend = Mock()
        backend.setup_presentation = SetupPresentation(
            confirmation_lines=("Wine prefix: /prefix", "Patched DLL: /mciwave.dll"),
            launch_command="rrlzAIMlinux launch --prefix /prefix",
        )
        installer = Path("/external-cache/aim593861.exe")

        with (
            patch("rrlzAIM.cli.create_backend", return_value=backend) as create,
            patch("rrlzAIM.cli.acquire_installer", return_value=installer),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main(
                ["setup", "--installer", str(installer), "--non-interactive"],
                host_platform="linux",
            )

        self.assertEqual(result, 0)
        create.assert_called_once()
        backend.prepare_setup.assert_called_once_with()
        backend.configure_setup.assert_called_once_with(SetupConfiguration())
        backend.setup.assert_called_once_with(installer)

    def test_patch_prefix_remains_wine_specific(self) -> None:
        backend = Mock()
        with (
            patch(
                "rrlzAIM.cli.create_wine_backend", return_value=backend
            ) as create_wine,
            patch("rrlzAIM.cli.create_backend") as create_shared,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main(["patch-prefix", "--dry-run"], host_platform="linux")

        self.assertEqual(result, 0)
        create_wine.assert_called_once()
        create_shared.assert_not_called()
        backend.check_tools.assert_called_once_with(require_winetricks=False)
        backend.apply.assert_called_once_with()

    def test_set_server_dispatches_to_the_wine_backend(self) -> None:
        backend = Mock()
        with (
            patch(
                "rrlzAIM.cli.create_wine_backend", return_value=backend
            ) as create_wine,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main(
                [
                    "set-server",
                    "--server",
                    "custom",
                    "--server-host",
                    "oscar.example",
                    "--server-port",
                    "4242",
                    "--non-interactive",
                    "--dry-run",
                ],
                host_platform="linux",
            )

        self.assertEqual(result, 0)
        create_wine.assert_called_once()
        backend.check_tools.assert_called_once_with(require_winetricks=False)
        backend.set_server.assert_called_once_with(AimServerSettings("oscar.example", 4242))

    def test_uninstall_dispatches_to_the_wine_backend(self) -> None:
        backend = Mock()
        with (
            patch(
                "rrlzAIM.cli.create_wine_backend", return_value=backend
            ) as create_wine,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main(
                ["uninstall", "--yes", "--dry-run"],
                host_platform="linux",
            )

        self.assertEqual(result, 0)
        create_wine.assert_called_once()
        backend.check_tools.assert_called_once_with(
            require_winetricks=False,
            enforce_version=False,
        )
        backend.uninstall.assert_called_once_with()

    def test_noninteractive_uninstall_requires_yes(self) -> None:
        backend = Mock()
        errors = io.StringIO()
        with (
            patch("rrlzAIM.cli.create_wine_backend", return_value=backend),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(errors),
        ):
            result = main(
                ["uninstall", "--non-interactive"],
                host_platform="linux",
            )

        self.assertEqual(result, 1)
        backend.uninstall.assert_not_called()
        self.assertIn("requires --yes", errors.getvalue())

    def test_cli_rejects_mismatched_host_before_backend_construction(self) -> None:
        errors = io.StringIO()
        with (
            patch("rrlzAIM.cli.create_backend") as create,
            contextlib.redirect_stderr(errors),
        ):
            result = main(["doctor"], host_platform="win32")

        self.assertEqual(result, 1)
        create.assert_not_called()
        self.assertIn("cannot run on host 'win32'", errors.getvalue())

    def test_fetch_remains_independent_of_backend_selection(self) -> None:
        installer = Path("/external-cache/aim593861.exe")
        with (
            patch("rrlzAIM.cli.acquire_installer", return_value=installer),
            patch("rrlzAIM.cli.select_backend_target") as select,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main(
                ["fetch", "--source", "oldversion"],
                build_target=BackendTarget.WINE,
                host_platform="win32",
            )

        self.assertEqual(result, 0)
        select.assert_not_called()


class SystemIniTests(unittest.TestCase):
    def test_mci_mapping_is_added_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix = root / "prefix"
            system_ini = prefix / "drive_c/windows/system.ini"
            system_ini.parent.mkdir(parents=True)
            system_ini.write_text("[boot]\nshell=explorer.exe\n", encoding="utf-8")
            backend = WineBackend(
                load_manifest(), prefix, root / "mciwave.dll", dry_run=True
            )
            backend._update_system_ini(system_ini)
            backend._update_system_ini(system_ini)
            result = system_ini.read_text(encoding="utf-8")
            self.assertEqual(result.count("[mci]"), 1)
            self.assertEqual(result.count("waveaudio=mciwave.dll"), 1)


class ApplicationMenuTests(unittest.TestCase):
    def make_backend(self, root: Path) -> WineBackend:
        return WineBackend(
            load_manifest(),
            root / "prefix",
            root / "mciwave.dll",
        )

    def test_xdg_desktop_entry_launches_the_configured_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "AIM Prefix $test"
            backend = self.make_backend(root)

            with patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                backend.installer_menu_link.parent.mkdir(parents=True)
                backend.installer_menu_link.touch()
                matching, unrelated = backend.wine_generated_menu_entries
                matching.parent.mkdir(parents=True)
                matching.write_text(f"Exec={backend.prefix}\n", encoding="utf-8")
                unrelated.parent.mkdir(parents=True, exist_ok=True)
                unrelated.write_text("Exec=/another/prefix\n", encoding="utf-8")

                def extract(_: list[str], **__: object) -> None:
                    backend.application_icon.write_bytes(b"\x89PNG\r\n\x1a\nicon")

                backend._run = Mock(side_effect=extract)
                with contextlib.redirect_stdout(io.StringIO()):
                    backend.install_menu_shortcut()
                desktop_entry = backend.application_menu_entry
                application_icon = backend.application_icon
                self.assertFalse(matching.exists())
                self.assertTrue(unrelated.is_file())

            contents = desktop_entry.read_text(encoding="utf-8")
            self.assertIn("Name=rrlzAIM - AIM 5.9\n", contents)
            self.assertIn('Exec=env "WINEPREFIX=', contents)
            self.assertIn("\\$test/prefix", contents)
            self.assertIn(f"Icon={application_icon}\n", contents)
            self.assertIn(f"X-RrlzAIMlinux-Prefix={backend.prefix}\n", contents)
            self.assertEqual(desktop_entry.stat().st_mode & 0o777, 0o644)
            backend._run.assert_called_once_with(
                [
                    "wine",
                    "winemenubuilder.exe",
                    "-t",
                    str(backend.installer_menu_link),
                    str(application_icon),
                ]
            )

    def test_removal_only_deletes_the_entry_for_this_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = self.make_backend(root)
            with patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data")}):
                backend.application_menu_entry.parent.mkdir(parents=True)
                backend.application_menu_entry.write_text(
                    "[Desktop Entry]\nX-RrlzAIMlinux-Prefix=/another/prefix\n",
                    encoding="utf-8",
                )
                backend.application_icon.parent.mkdir(parents=True)
                backend.application_icon.write_bytes(b"icon")
                backend.remove_menu_shortcut()
                self.assertTrue(backend.application_menu_entry.is_file())
                self.assertTrue(backend.application_icon.is_file())

                backend.application_menu_entry.write_text(
                    f"[Desktop Entry]\nX-RrlzAIMlinux-Prefix={backend.prefix}\n",
                    encoding="utf-8",
                )
                backend.remove_menu_shortcut()
                self.assertFalse(backend.application_menu_entry.exists())
                self.assertFalse(backend.application_icon.exists())

    def test_missing_installer_link_stops_icon_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary))
            backend._run = Mock()

            with (
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaisesRegex(BackendError, "needed to extract"),
            ):
                backend.install_menu_shortcut()

            backend._run.assert_not_called()


class WineManagementTests(unittest.TestCase):
    def make_backend(self, root: Path, *, dry_run: bool = True) -> WineBackend:
        return WineBackend(
            load_manifest(),
            root / "prefix",
            root / "mciwave.dll",
            dry_run=dry_run,
        )

    def make_uninstallable_backend(self, root: Path) -> WineBackend:
        backend = self.make_backend(root, dry_run=False)
        backend.prefix.mkdir()
        (backend.prefix / "system.reg").write_text("#arch=win32\n", encoding="utf-8")
        backend.aim_dir.mkdir(parents=True)
        (backend.aim_dir / "aim.exe").write_bytes(b"aim")
        (backend.aim_dir / "aimapi.dll.disabled").write_bytes(b"aimapi")
        (backend.aim_dir / "uninstll.EXE").write_bytes(b"uninstaller")
        return backend

    def test_set_server_writes_host_and_port_with_wine_registry_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary))
            backend._run = Mock()

            with contextlib.redirect_stdout(io.StringIO()):
                backend.set_server(AimServerSettings("oscar.example", 4242))

        registry_key = (
            r"HKCU\Software\America Online\AOL Instant Messenger (TM)\CurrentVersion\Server"
        )
        self.assertEqual(
            backend._run.mock_calls,
            [
                call(
                    [
                        "wine",
                        "reg",
                        "add",
                        registry_key,
                        "/v",
                        "Host",
                        "/t",
                        "REG_SZ",
                        "/d",
                        "oscar.example",
                        "/f",
                    ]
                ),
                call(
                    [
                        "wine",
                        "reg",
                        "add",
                        registry_key,
                        "/v",
                        "Port",
                        "/t",
                        "REG_DWORD",
                        "/d",
                        "4242",
                        "/f",
                    ]
                ),
            ],
        )

    def test_setup_preflight_refuses_to_reinstall_an_existing_aim_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary), dry_run=False)
            backend.aim_dir.mkdir(parents=True)
            (backend.aim_dir / "aim.exe").write_bytes(b"aim")
            backend.check_tools = Mock()
            backend.verify_patched_dll = Mock()

            with self.assertRaisesRegex(BackendError, "already installed"):
                backend.prepare_setup()

        backend.check_tools.assert_called_once_with(
            require_winetricks=True,
            require_wineboot=True,
        )
        backend.verify_patched_dll.assert_called_once_with()

    def test_uninstall_runs_aim_uninstaller_then_removes_menu_and_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_uninstallable_backend(Path(temporary))
            uninstaller = backend.aim_dir / "uninstll.EXE"
            aim_executable = backend.aim_dir / "aim.exe"

            def run(command: list[str], **_: object) -> None:
                if command[0] == backend.wine:
                    aim_executable.unlink()

            backend._run = Mock(side_effect=run)
            backend.remove_menu_shortcut = Mock()
            backend._remove_wine_generated_menu_entries = Mock()

            with contextlib.redirect_stdout(io.StringIO()):
                backend.uninstall()

            self.assertEqual(
                backend._run.mock_calls,
                [
                    call(
                        [
                            "wine",
                            str(uninstaller),
                            "-LOG=",
                            r"C:\Program Files\AIM\install.log",
                            "-OEM=",
                        ],
                        cwd=backend.aim_dir,
                    ),
                    call(["wineserver", "-w"]),
                ],
            )
            backend.remove_menu_shortcut.assert_called_once_with()
            backend._remove_wine_generated_menu_entries.assert_called_once_with()
            self.assertFalse(backend.prefix.exists())

    def test_uninstall_keeps_the_prefix_after_a_cancelled_or_incomplete_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_uninstallable_backend(Path(temporary))
            backend._run = Mock()
            backend.remove_menu_shortcut = Mock()
            backend._remove_wine_generated_menu_entries = Mock()

            with (
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaisesRegex(BackendError, "aim.exe is still present"),
            ):
                backend.uninstall()

            self.assertTrue(backend.prefix.is_dir())
            self.assertTrue((backend.aim_dir / "aim.exe").is_file())
            self.assertTrue((backend.aim_dir / "aimapi.dll.disabled").is_file())
            backend.remove_menu_shortcut.assert_not_called()
            backend._remove_wine_generated_menu_entries.assert_not_called()

    def test_uninstall_refuses_a_symbolic_link_in_place_of_aims_uninstaller(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = self.make_uninstallable_backend(root)
            uninstaller = backend.aim_dir / "uninstll.EXE"
            uninstaller.unlink()
            target = root / "outside-prefix.exe"
            target.write_bytes(b"not an AIM uninstaller")
            uninstaller.symlink_to(target)
            backend._run = Mock()

            with self.assertRaisesRegex(BackendError, "uninstaller was not found"):
                backend.uninstall()

            backend._run.assert_not_called()
            self.assertTrue((backend.aim_dir / "aimapi.dll.disabled").is_file())

    def test_dry_run_uninstall_only_displays_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary))
            backend._run = Mock()

            with contextlib.redirect_stdout(io.StringIO()) as output:
                backend.uninstall()

        self.assertEqual(
            backend._run.mock_calls,
            [
                call(
                    [
                        "wine",
                        str(backend.aim_dir / "uninstll.exe"),
                        "-LOG=",
                        r"C:\Program Files\AIM\install.log",
                        "-OEM=",
                    ],
                    cwd=backend.aim_dir,
                ),
                call(["wineserver", "-w"]),
            ],
        )
        self.assertIn("Would recursively remove", output.getvalue())

    def test_setup_configuration_applies_the_requested_management_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary))
            backend.configure_setup(
                SetupConfiguration(
                    server=AimServerSettings("oscar.example", 4242),
                    remove_aol_desktop_shortcut=True,
                )
            )
            backend.verify_patched_dll = Mock()
            backend._run = Mock()
            backend.stop_wine = Mock()
            actions = Mock()
            actions.attach_mock(Mock(), "menu")
            actions.attach_mock(Mock(), "server")
            actions.attach_mock(Mock(), "shortcut")
            backend.install_menu_shortcut = actions.menu
            backend._write_server_settings = actions.server
            backend.remove_aol_desktop_shortcut = actions.shortcut

            with contextlib.redirect_stdout(io.StringIO()):
                backend.apply()

        self.assertEqual(
            actions.mock_calls,
            [
                call.menu(),
                call.server(AimServerSettings("oscar.example", 4242)),
                call.shortcut(),
            ],
        )

    def test_setup_can_leave_the_xdg_launcher_uncreated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary))
            backend.configure_setup(SetupConfiguration(create_xdg_launcher=False))
            backend.verify_patched_dll = Mock()
            backend._run = Mock()
            backend.stop_wine = Mock()
            backend.install_menu_shortcut = Mock()

            with contextlib.redirect_stdout(io.StringIO()):
                backend.apply()

        backend.install_menu_shortcut.assert_not_called()

    def test_current_server_status_reads_the_prefix_local_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary), dry_run=False)
            (backend.prefix / "user.reg").parent.mkdir(parents=True)
            (backend.prefix / "user.reg").write_text(
                "[Software\\\\America Online\\\\AOL Instant Messenger (TM)\\\\CurrentVersion\\\\Server]\n"
                '"Host"="aim.realretrolabz.com"\n'
                '"Port"=dword:00001446\n',
                encoding="utf-8",
            )

            self.assertEqual(
                backend.current_server_status(), "Server: aim.realretrolabz.com:5190"
            )

    def test_doctor_checks_the_recorded_prefix_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary), dry_run=False)
            backend.prefix.mkdir()
            backend.system32.mkdir(parents=True)
            backend.aim_dir.mkdir(parents=True)
            (backend.prefix / "system.reg").write_text(
                "#arch=win32\n"
                "[Software\\\\Microsoft\\\\Windows NT\\\\CurrentVersion\\\\MCI]\n"
                '"WaveAudio"="mciwave.dll"\n'
                "[Software\\\\Microsoft\\\\Windows NT\\\\CurrentVersion\\\\MCI32]\n"
                '"WaveAudio"="mciwave.dll"\n',
                encoding="utf-8",
            )
            (backend.prefix / "user.reg").write_text(
                "[Software\\\\Wine]\n"
                '"Version"="winxp"\n'
                "[Software\\\\Wine\\\\DllOverrides]\n"
                '"mciwave"="native,builtin"\n',
                encoding="utf-8",
            )
            (backend.prefix / "drive_c/windows/system.ini").write_text(
                "[mci]\nwaveaudio=mciwave.dll\n", encoding="utf-8"
            )
            (backend.system32 / "mfc40.dll").write_bytes(b"mfc")
            (backend.aim_dir / "aim.exe").write_bytes(b"aim")
            (backend.aim_dir / "sb.dll").write_bytes(b"sb")
            (backend.aim_dir / "aimapi.dll.disabled").write_bytes(b"aimapi")
            backend._write_state({"superbuddy_registered": True})
            backend.check_tools = Mock(return_value="wine-9.0")

            checks = {message: passed for passed, message in backend.doctor()}

            self.assertTrue(checks["Wine prefix architecture: win32"])
            self.assertTrue(checks["Wine Windows version: XP"])
            self.assertTrue(checks["mfc40 installed"])
            self.assertTrue(checks["mciwave override: native,builtin"])
            self.assertTrue(checks["MCI and MCI32 WaveAudio mappings"])
            self.assertTrue(checks["system.ini WaveAudio mapping"])
            self.assertTrue(checks["SuperBuddy registration recorded"])

    def test_optional_aol_cleanup_targets_active_and_public_desktops_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = self.make_backend(root, dry_run=False)
            active_user = backend.wine_users_directory / "wine-user"
            mapped_desktop = root / "mapped-desktop"
            current = active_user / "Desktop"
            public = backend.wine_users_directory / "Public" / "Desktop"
            other_desktop = backend.wine_users_directory / "other-user" / "Desktop"
            favorites = active_user / "Favorites"
            start_menu = (
                backend.prefix
                / "drive_c/ProgramData/Microsoft/Windows/Start Menu"
            )
            for directory in (
                active_user,
                mapped_desktop,
                public,
                other_desktop,
                favorites,
                start_menu,
            ):
                directory.mkdir(parents=True, exist_ok=True)
            current.symlink_to(mapped_desktop, target_is_directory=True)
            (backend.prefix / "user.reg").write_text(
                '"USERPROFILE"="C:\\\\users\\\\wine-user"\n',
                encoding="utf-8",
            )

            exact_name = "Free AOL & Unlimited Internet.lnk"
            current_shortcut = current / exact_name
            public_shortcut = public / exact_name
            other_shortcut = other_desktop / exact_name
            favorite_shortcut = favorites / exact_name
            start_menu_shortcut = start_menu / exact_name
            near_match = current / "Free AOL & Unlimited Internet (copy).lnk"
            for shortcut in (
                current_shortcut,
                public_shortcut,
                other_shortcut,
                favorite_shortcut,
                start_menu_shortcut,
                near_match,
            ):
                shortcut.write_bytes(b"shortcut")

            with contextlib.redirect_stdout(io.StringIO()):
                backend.remove_aol_desktop_shortcut()

            self.assertFalse(current_shortcut.exists())
            self.assertFalse(public_shortcut.exists())
            self.assertTrue(other_shortcut.is_file())
            self.assertTrue(favorite_shortcut.is_file())
            self.assertTrue(start_menu_shortcut.is_file())
            self.assertTrue(near_match.is_file())
            state = json.loads(backend.state_file.read_text(encoding="utf-8"))
            self.assertEqual(len(state["aol_desktop_shortcut_backups"]), 2)

    def test_rollback_restores_backed_up_aol_shortcut_without_overwriting_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = self.make_backend(root, dry_run=False)
            shortcut = (
                backend.wine_users_directory
                / "Public"
                / "Desktop"
                / "Free AOL & Unlimited Internet.lnk"
            )
            shortcut.parent.mkdir(parents=True)
            shortcut.write_bytes(b"original shortcut")
            with contextlib.redirect_stdout(io.StringIO()):
                backend.remove_aol_desktop_shortcut()
            self.assertFalse(shortcut.exists())

            shortcut.write_bytes(b"replacement shortcut")
            with contextlib.redirect_stdout(io.StringIO()):
                backend.restore_aol_desktop_shortcuts()
            self.assertEqual(shortcut.read_bytes(), b"replacement shortcut")

            shortcut.unlink()
            with contextlib.redirect_stdout(io.StringIO()):
                backend.restore_aol_desktop_shortcuts()
            self.assertEqual(shortcut.read_bytes(), b"original shortcut")

            shortcut.write_bytes(b"newer shortcut")
            with contextlib.redirect_stdout(io.StringIO()):
                backend.remove_aol_desktop_shortcut()
                backend.restore_aol_desktop_shortcuts()
            self.assertEqual(shortcut.read_bytes(), b"newer shortcut")

    def test_rollback_invokes_aol_shortcut_restore(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = self.make_backend(root, dry_run=False)
            (backend.prefix / "system.reg").parent.mkdir(parents=True)
            (backend.prefix / "system.reg").write_text("#arch=win32\n", encoding="utf-8")
            backend.check_tools = Mock()
            backend.stop_wine = Mock()
            backend._run = Mock()
            backend.restore_aol_desktop_shortcuts = Mock()
            backend.remove_menu_shortcut = Mock()

            with contextlib.redirect_stdout(io.StringIO()):
                backend.rollback()

            backend.restore_aol_desktop_shortcuts.assert_called_once_with()

    def test_set_server_requires_an_existing_win32_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = self.make_backend(root, dry_run=False)
            backend.aim_dir.mkdir(parents=True)
            (backend.aim_dir / "aim.exe").touch()
            backend._run = Mock()

            with self.assertRaisesRegex(BackendError, "Wine prefix not found"):
                backend.set_server(AimServerSettings("oscar.example", 4242))

            system_reg = backend.prefix / "system.reg"
            system_reg.write_text("#arch=win64\n", encoding="utf-8")
            with self.assertRaisesRegex(BackendError, "64-bit"):
                backend.set_server(AimServerSettings("oscar.example", 4242))

            system_reg.write_text("#arch=win32\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                backend.set_server(AimServerSettings("oscar.example", 4242))
            self.assertEqual(backend._run.call_count, 2)

    def test_dry_run_aol_cleanup_does_not_delete_a_shortcut(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = self.make_backend(root)
            shortcut = (
                backend.wine_users_directory
                / "Public"
                / "Desktop"
                / "Free AOL & Unlimited Internet.lnk"
            )
            shortcut.parent.mkdir(parents=True)
            shortcut.write_bytes(b"shortcut")

            with contextlib.redirect_stdout(io.StringIO()) as output:
                backend.remove_aol_desktop_shortcut()

            self.assertTrue(shortcut.is_file())
            self.assertIn("Would remove", output.getvalue())

    def test_aol_cleanup_skips_a_leaf_shortcut_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = self.make_backend(root, dry_run=False)
            target = root / "outside-prefix.lnk"
            target.write_bytes(b"shortcut target")
            shortcut = (
                backend.wine_users_directory
                / "Public"
                / "Desktop"
                / "Free AOL & Unlimited Internet.lnk"
            )
            shortcut.parent.mkdir(parents=True)
            shortcut.symlink_to(target)

            with contextlib.redirect_stdout(io.StringIO()) as output:
                backend.remove_aol_desktop_shortcut()

            self.assertTrue(shortcut.is_symlink())
            self.assertEqual(target.read_bytes(), b"shortcut target")
            self.assertFalse(backend.state_file.exists())
            self.assertIn("Skipped symbolic-link", output.getvalue())


class WineWorkflowRegressionTests(unittest.TestCase):
    def make_backend(self, root: Path) -> WineBackend:
        return WineBackend(
            load_manifest(),
            root / "prefix",
            root / "mciwave.dll",
            dry_run=True,
        )

    def test_setup_preflight_order_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary))
            calls = Mock()
            calls.attach_mock(Mock(), "check_tools")
            calls.attach_mock(Mock(), "verify_patched_dll")
            backend.check_tools = calls.check_tools
            backend.verify_patched_dll = calls.verify_patched_dll

            backend.prepare_setup()

            self.assertEqual(
                calls.mock_calls,
                [
                    call.check_tools(
                        require_winetricks=True,
                        require_wineboot=True,
                    ),
                    call.verify_patched_dll(),
                ],
            )

    def test_installer_disables_only_automatic_wine_menu_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary))
            backend._run = Mock()
            backend.stop_wine = Mock()
            installer = Path(temporary) / "aim593861.exe"

            with (
                patch.dict(os.environ, {"WINEDLLOVERRIDES": "existing=n"}),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                backend.install_aim(installer)

            backend._run.assert_called_once_with(
                ["wine", str(installer)],
                extra_env={
                    "WINEDLLOVERRIDES": "existing=n;winemenubuilder.exe="
                },
            )
            backend.stop_wine.assert_called_once_with()

    def test_wine10_selects_the_matching_default_dll(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = WineBackend(
                load_manifest(),
                root / "prefix",
                root / "mciwave-wine9-x86-aim.dll",
                auto_select_patched_dll=True,
                dry_run=True,
            )
            detected = subprocess.CompletedProcess(
                ["wine", "--version"],
                0,
                "wine-10.0 (Debian 10.0~repack-6)\n",
                "",
            )

            with (
                patch(
                    "rrlzAIM.backends.wine.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                patch(
                    "rrlzAIM.backends.wine.subprocess.run",
                    return_value=detected,
                ),
            ):
                self.assertEqual(
                    backend.check_tools(require_winetricks=False),
                    "wine-10.0 (Debian 10.0~repack-6)",
                )

            self.assertEqual(backend.wine_version_prefix, "wine-10.0")
            self.assertEqual(
                backend.patched_dll,
                root / "mciwave-wine10-x86-aim.dll",
            )

    def test_unsupported_wine_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary))
            detected = subprocess.CompletedProcess(
                ["wine", "--version"], 0, "wine-11.0\n", ""
            )

            with (
                patch(
                    "rrlzAIM.backends.wine.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                patch(
                    "rrlzAIM.backends.wine.subprocess.run",
                    return_value=detected,
                ),
                self.assertRaisesRegex(BackendError, "Wine 9.0 or 10.0"),
            ):
                backend.check_tools(require_winetricks=False)

    def test_missing_debian_wine32_is_reported_before_prefix_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary))
            detected = subprocess.CompletedProcess(
                ["wine", "--version"],
                0,
                "wine-10.0 (Debian 10.0~repack-6)\n",
                "it looks like wine32 is missing, you should install it.\n",
            )

            with (
                patch(
                    "rrlzAIM.backends.wine.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                patch(
                    "rrlzAIM.backends.wine.subprocess.run",
                    return_value=detected,
                ),
                self.assertRaisesRegex(BackendError, "sudo apt install wine32:i386"),
            ):
                backend.check_tools(require_winetricks=False)

    def test_wine_setup_operation_order_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self.make_backend(Path(temporary))
            installer = Path(temporary) / "aim593861.exe"
            calls = Mock()
            for name in (
                "create_prefix",
                "install_prerequisites",
                "install_aim",
                "apply",
            ):
                method = Mock()
                calls.attach_mock(method, name)
                setattr(backend, name, method)

            backend.setup(installer)

            self.assertEqual(
                calls.mock_calls,
                [
                    call.create_prefix(),
                    call.install_prerequisites(),
                    call.install_aim(installer),
                    call.apply(),
                ],
            )


if __name__ == "__main__":
    unittest.main()
