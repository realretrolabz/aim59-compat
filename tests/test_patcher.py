from __future__ import annotations

import contextlib
import hashlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from aim59_compat.backends import (
    BackendTarget,
    WineBackendOptions,
    create_backend,
    select_backend_target,
)
from aim59_compat.backends.base import BackendError, SetupPresentation
from aim59_compat.backends.wine import WineBackend
from aim59_compat.cli import default_dll, main, verify_installer
from aim59_compat.download import DownloadError, _OldVersionFormParser, download_direct
from aim59_compat.manifest import load_manifest
from aim59_compat.orchestration import run_doctor, run_launch, run_rollback, run_setup


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


class ReleaseLayoutTests(unittest.TestCase):
    def test_release_checksum_policy_is_strict_only_for_release_publish(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = (root / "scripts" / "verify-release.py").read_text(encoding="utf-8")
        makefile = (root / "Makefile").read_text(encoding="utf-8")
        repository_check = (root / "scripts" / "verify-repo.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("--require-published-bundle-checksum", verifier)
        self.assertIn("if arguments.require_published_bundle_checksum:", verifier)
        self.assertIn(
            "verify-release.py --require-published-bundle-checksum", makefile
        )
        self.assertIn("python3 scripts/verify-release.py", repository_check)
        self.assertNotIn(
            "python3 scripts/verify-release.py --require-published-bundle-checksum",
            repository_check,
        )

    def test_adjacent_release_dll_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = root / "aim59"
            dll = root / "mciwave-wine9-x86-aim.dll"
            launcher.touch()
            dll.touch()
            with patch("sys.argv", [str(launcher)]):
                self.assertEqual(default_dll(), dll)

    def test_adjacent_wine10_dll_can_seed_auto_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = root / "aim59"
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
            launch_command="aim59 launch --prefix /prefix",
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
            "  Run: aim59 launch --prefix /prefix\n",
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
            launch_command="aim59 launch --prefix /prefix",
        )
        installer = Path("/external-cache/aim593861.exe")

        with (
            patch("aim59_compat.cli.create_backend", return_value=backend) as create,
            patch("aim59_compat.cli.acquire_installer", return_value=installer),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main(
                ["setup", "--installer", str(installer), "--non-interactive"],
                host_platform="linux",
            )

        self.assertEqual(result, 0)
        create.assert_called_once()
        backend.prepare_setup.assert_called_once_with()
        backend.setup.assert_called_once_with(installer)

    def test_patch_prefix_remains_wine_specific(self) -> None:
        backend = Mock()
        with (
            patch(
                "aim59_compat.cli.create_wine_backend", return_value=backend
            ) as create_wine,
            patch("aim59_compat.cli.create_backend") as create_shared,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main(["patch-prefix", "--dry-run"], host_platform="linux")

        self.assertEqual(result, 0)
        create_wine.assert_called_once()
        create_shared.assert_not_called()
        backend.check_tools.assert_called_once_with(require_winetricks=False)
        backend.apply.assert_called_once_with()

    def test_cli_rejects_mismatched_host_before_backend_construction(self) -> None:
        errors = io.StringIO()
        with (
            patch("aim59_compat.cli.create_backend") as create,
            contextlib.redirect_stderr(errors),
        ):
            result = main(["doctor"], host_platform="win32")

        self.assertEqual(result, 1)
        create.assert_not_called()
        self.assertIn("cannot run on host 'win32'", errors.getvalue())

    def test_fetch_remains_independent_of_backend_selection(self) -> None:
        installer = Path("/external-cache/aim593861.exe")
        with (
            patch("aim59_compat.cli.acquire_installer", return_value=installer),
            patch("aim59_compat.cli.select_backend_target") as select,
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
            self.assertIn("Name=AOL Instant Messenger 5.9\n", contents)
            self.assertIn('Exec=env "WINEPREFIX=', contents)
            self.assertIn("\\$test/prefix", contents)
            self.assertIn(f"Icon={application_icon}\n", contents)
            self.assertIn(f"X-AIM59-Prefix={backend.prefix}\n", contents)
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
                    "[Desktop Entry]\nX-AIM59-Prefix=/another/prefix\n",
                    encoding="utf-8",
                )
                backend.application_icon.parent.mkdir(parents=True)
                backend.application_icon.write_bytes(b"icon")
                backend.remove_menu_shortcut()
                self.assertTrue(backend.application_menu_entry.is_file())
                self.assertTrue(backend.application_icon.is_file())

                backend.application_menu_entry.write_text(
                    f"[Desktop Entry]\nX-AIM59-Prefix={backend.prefix}\n",
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
                    "aim59_compat.backends.wine.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                patch(
                    "aim59_compat.backends.wine.subprocess.run",
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
                    "aim59_compat.backends.wine.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                patch(
                    "aim59_compat.backends.wine.subprocess.run",
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
                    "aim59_compat.backends.wine.shutil.which",
                    return_value="/usr/bin/tool",
                ),
                patch(
                    "aim59_compat.backends.wine.subprocess.run",
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
