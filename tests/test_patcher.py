from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from aim59_compat.backends.wine import WineBackend
from aim59_compat.cli import verify_installer
from aim59_compat.download import DownloadError, _OldVersionFormParser, download_direct
from aim59_compat.manifest import load_manifest


class ManifestTests(unittest.TestCase):
    def test_supported_manifest(self) -> None:
        manifest = load_manifest()
        self.assertEqual(manifest["version"], "5.9.3861")
        self.assertEqual(manifest["wine"]["version_prefix"], "wine-9.0")
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


if __name__ == "__main__":
    unittest.main()
