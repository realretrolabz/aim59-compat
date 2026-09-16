from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "windows" / "collect-aim59-discovery.ps1"
INSTALLER_SCRIPT = ROOT / "scripts" / "windows" / "install-aim59.ps1"
GUI_SCRIPT = ROOT / "scripts" / "windows" / "install-aim59-gui.ps1"
DOCUMENTATION = ROOT / "docs" / "WINDOWS_DISCOVERY.md"
FINDINGS = ROOT / "docs" / "WINDOWS_FINDINGS.md"
INSTALL_DOCUMENTATION = ROOT / "docs" / "WINDOWS_INSTALL.md"


class WindowsDiscoveryKitStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.installer_script = INSTALLER_SCRIPT.read_text(encoding="utf-8")
        cls.gui_script = GUI_SCRIPT.read_text(encoding="utf-8")
        cls.documentation = DOCUMENTATION.read_text(encoding="utf-8")
        cls.findings = FINDINGS.read_text(encoding="utf-8")
        cls.install_documentation = INSTALL_DOCUMENTATION.read_text(encoding="utf-8")

    def test_output_directory_is_explicit_and_guarded(self) -> None:
        self.assertRegex(
            self.script,
            re.compile(
                r"\[Parameter\(Mandatory = \$true, Position = 0\)\]"
                r"\s+\[ValidateNotNullOrEmpty\(\)\]"
                r"\s+\[string\]\$OutputDirectory",
            ),
        )
        self.assertIn("OutputDirectory must be new or empty", self.script)
        self.assertIn("OutputDirectory must be outside the collector directory", self.script)
        self.assertIn("OutputDirectory must be outside the repository", self.script)
        self.assertIn("Refusing to write outside OutputDirectory", self.script)
        self.assertIn("Write-OutputArtifact", self.script)

    def test_supported_checkpoint_names_are_fixed(self) -> None:
        expected = {
            "00-clean",
            "10-after-install",
            "20-after-first-launch",
            "30-after-aim-exit",
            "40-after-uninstall-or-restore",
        }
        found = set(re.findall(r"'([0-9]{2}-[^']+)'", self.script))
        self.assertTrue(expected.issubset(found))

    def test_registry_views_are_explicit_and_unmerged(self) -> None:
        self.assertIn("[Microsoft.Win32.RegistryView]::Registry64", self.script)
        self.assertIn("[Microsoft.Win32.RegistryView]::Registry32", self.script)
        self.assertIn("OpenBaseKey($Hive, $View)", self.script)
        self.assertIn("Registry64 (64-bit view)", self.script)
        self.assertIn("Registry32 (32-bit/WOW64 view)", self.script)
        self.assertNotIn("Registry.ClassesRoot", self.script)

    def test_aim_filters_do_not_mistake_system_names_for_aim(self) -> None:
        self.assertIn("-not (Test-AimMarker $subKeyName)", self.script)
        self.assertNotIn("-notmatch '(?i)(aim|aol)'", self.script)
        self.assertIn("(?:^|[\\\\/])sb\\.dll(?:$|\\s)", self.script)
        self.assertIn("(?:^|[\\\\/])aimapi\\.dll(?:$|\\s)", self.script)

    def test_safety_contract_has_no_compatibility_mutators(self) -> None:
        forbidden = (
            "Start-Process",
            "New-ItemProperty",
            "Set-ItemProperty",
            "Remove-ItemProperty",
            "Clear-ItemProperty",
            "reg.exe add",
            "reg.exe import",
            "reg.exe export",
            "Copy-Item",
            "Move-Item",
            "Start-Transcript",
            "Set-ExecutionPolicy",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, self.script)
        self.assertNotRegex(
            self.script,
            re.compile(r"(?im)^\s*regsvr32(?:\.exe)?(?:\s|$)"),
        )

    def test_file_and_xpcs_collection_are_metadata_only(self) -> None:
        self.assertIn("Get-FileHash -LiteralPath", self.script)
        self.assertIn("[System.Diagnostics.FileVersionInfo]::GetVersionInfo", self.script)
        self.assertIn("Xpcs Registry.dat", self.script)
        self.assertIn("[System.IO.File]::ReadAllBytes($Path)", self.script)
        self.assertIn("absolutePathReferences", self.script)
        self.assertIn("SysWOW64\\regsvr32.exe", self.script)
        self.assertNotIn("WriteAllBytes", self.script)

    def test_comparison_has_separate_explicit_inputs(self) -> None:
        self.assertRegex(
            self.script,
            re.compile(
                r"\[Parameter\(Mandatory = \$true, ParameterSetName = 'Compare'\)\]"
                r"\s+\[ValidateNotNullOrEmpty\(\)\]"
                r"\s+\[string\]\$BaselineDirectory",
            ),
        )
        self.assertIn("[string]$ComparisonDirectory", self.script)
        self.assertIn("New-DiscoveryComparison", self.script)
        self.assertIn("comparison.json", self.script)

    def test_operator_documentation_covers_stage_three_and_privacy(self) -> None:
        self.assertIn("Stage 3: exact clean-VM sequence", self.documentation)
        self.assertIn("sudo virsh snapshot-list win11", self.documentation)
        self.assertIn("sudo virsh domblklist win11 --details", self.documentation)
        self.assertIn("manage-bde -status F:", self.documentation)
        self.assertIn("E:\\AIM59-Evidence\\00-clean", self.documentation)
        self.assertIn("compare-00-to-40", self.documentation)
        self.assertIn("Raw evidence stays private", self.documentation)
        self.assertIn("non-disposable host evidence", self.documentation)

    def test_sanitized_findings_record_the_failure_without_raw_evidence(self) -> None:
        self.assertIn("running in the background but", self.findings)
        self.assertIn("Stage 4 gate", self.findings)
        self.assertIn("one-variable-at-a-time", self.findings)
        self.assertNotIn("C:\\Users\\", self.findings)
        self.assertNotIn("F:\\AIM59-Input", self.findings)

    def test_windows_installer_is_pinned_reversible_and_configurable(self) -> None:
        script = self.installer_script
        self.assertIn("$InstallerSize = 8715352", script)
        self.assertIn(
            "018438bf22672ee119e864d78f838a538ed067bb76296957a00e0c1080979af1",
            script,
        )
        self.assertIn("Get-FileHash -LiteralPath $Path -Algorithm SHA256", script)
        self.assertIn("Get-OldVersionDownloadForm", script)
        self.assertIn("[string]$InstallerPath", script)
        self.assertIn("Using verified local installer", script)
        self.assertIn("Start-Process -FilePath $installer -Wait -PassThru", script)
        self.assertIn("AIM installer exited with code", script)
        self.assertIn("aimapi.dll.aim59-disabled", script)
        self.assertIn("Rename-Item -LiteralPath $original", script)
        self.assertIn("[switch]$Rollback", script)
        self.assertIn("[string]$ServerMode = 'Prompt'", script)
        self.assertIn("[string]$ServerHost", script)
        self.assertIn("[int]$ServerPort = 5190", script)
        self.assertIn("Get-AimServerChoice", script)
        self.assertIn("Keep AIM default (login.oscar.aol.com:5190)", script)
        self.assertIn("Enter another host and port", script)
        self.assertIn("$AimRegistryServerKey", script)
        self.assertIn("-Name 'Host' -PropertyType String", script)
        self.assertIn("-Name 'Port' -PropertyType DWord", script)
        self.assertNotIn("Copy-Item", script)
        self.assertNotIn("regsvr32", script.lower())

    def test_windows_installer_documentation_preserves_scope_and_rollback(self) -> None:
        documentation = self.install_documentation
        self.assertIn("not portable", documentation)
        self.assertIn("aimapi.dll.aim59-disabled", documentation)
        self.assertIn("-Rollback", documentation)
        self.assertIn("aim.realretrolabz.com:5190", documentation)
        self.assertIn("Current evidence boundary", documentation)
        self.assertIn("does not yet\nestablish all release-gate features", documentation)

    def test_windows_gui_delegates_to_the_canonical_installer_script(self) -> None:
        script = self.gui_script
        self.assertIn("install-aim59.ps1", script)
        self.assertIn("Add-Type -AssemblyName System.Windows.Forms", script)
        self.assertIn("Start-BackendProcess", script)
        self.assertIn("-ServerMode", script)
        self.assertIn("-Rollback", script)
        self.assertIn("Use aim.realretrolabz.com:5190", script)
        self.assertIn("Keep AIM's original server setting", script)
        self.assertIn("Use another server:", script)
        self.assertIn("Installer source", script)
        self.assertIn("Download the verified installer from OldVersion.com", script)
        self.assertIn("Use a local AIM 5.9.3861 installer:", script)
        self.assertIn("-InstallerPath", script)
        self.assertNotIn("Get-OldVersionDownloadForm", script)
        self.assertNotIn("Get-FileHash", script)
        self.assertNotIn("Rename-Item", script)
        self.assertNotIn("New-ItemProperty", script)


if __name__ == "__main__":
    unittest.main()
