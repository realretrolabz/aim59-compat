from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "windows" / "collect-aim59-discovery.ps1"
INSTALLER_SCRIPT = ROOT / "scripts" / "windows" / "install-aim59.ps1"
EXE_SOURCE = ROOT / "windows" / "AIM59Setup" / "Program.cs"
EXE_WORKFLOW = ROOT / "windows" / "AIM59Setup" / "NativeWorkflow.cs"
EXE_PROJECT = ROOT / "windows" / "AIM59Setup" / "AIM59Setup.csproj"
EXE_BUILD_SCRIPT = ROOT / "scripts" / "windows" / "build-aim59-setup.ps1"
EXE_MONO_BUILD_SCRIPT = ROOT / "scripts" / "build-aim59-setup-mono.sh"
DOCUMENTATION = ROOT / "docs" / "WINDOWS_DISCOVERY.md"
FINDINGS = ROOT / "docs" / "WINDOWS_FINDINGS.md"
INSTALL_DOCUMENTATION = ROOT / "docs" / "WINDOWS_INSTALL.md"
EXE_HANDOFF = ROOT / "docs" / "WINDOWS_EXE_HANDOFF.md"
RELEASE_DOCUMENTATION = ROOT / "docs" / "RELEASE.md"
README = ROOT / "README.md"
GITIGNORE = ROOT / ".gitignore"


class WindowsDiscoveryKitStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.installer_script = INSTALLER_SCRIPT.read_text(encoding="utf-8")
        cls.exe_source = EXE_SOURCE.read_text(encoding="utf-8")
        cls.exe_workflow = EXE_WORKFLOW.read_text(encoding="utf-8")
        cls.exe_project = EXE_PROJECT.read_text(encoding="utf-8")
        cls.exe_build_script = EXE_BUILD_SCRIPT.read_text(encoding="utf-8")
        cls.exe_mono_build_script = EXE_MONO_BUILD_SCRIPT.read_text(encoding="utf-8")
        cls.documentation = DOCUMENTATION.read_text(encoding="utf-8")
        cls.findings = FINDINGS.read_text(encoding="utf-8")
        cls.install_documentation = INSTALL_DOCUMENTATION.read_text(encoding="utf-8")
        cls.exe_handoff = EXE_HANDOFF.read_text(encoding="utf-8")
        cls.release_documentation = RELEASE_DOCUMENTATION.read_text(encoding="utf-8")
        cls.readme = README.read_text(encoding="utf-8")
        cls.gitignore = GITIGNORE.read_text(encoding="utf-8")

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

    def test_archived_windows_prototype_is_pinned_reversible_and_configurable(self) -> None:
        script = self.installer_script
        self.assertIn("ARCHIVED PROOF OF CONCEPT", script)
        self.assertIn("$InstallerSize = 8715352", script)
        self.assertIn(
            "018438bf22672ee119e864d78f838a538ed067bb76296957a00e0c1080979af1",
            script,
        )
        self.assertIn("Get-FileHash -LiteralPath $Path -Algorithm SHA256", script)
        self.assertIn("Get-OldVersionDownloadForm", script)
        self.assertIn("[string]$InstallerPath", script)
        self.assertIn("Using verified local installer", script)
        self.assertIn("Start-Process -FilePath $installer -PassThru", script)
        self.assertIn("AIM installer exited with code", script)
        self.assertIn("function Write-Status", script)
        self.assertIn("[Console]::Out.Flush()", script)
        self.assertNotIn("Write-Status ''", script)
        self.assertIn("function Invoke-OldVersionDownload", script)
        self.assertIn("Download progress:", script)
        self.assertIn("Invoke-OldVersionDownload -Uri $downloadUri", script)
        self.assertIn("function Wait-For-AimInstallation", script)
        self.assertIn("$InstallerCompletionTimeoutSeconds = 900", script)
        self.assertIn("$InstallerFileSettleSeconds = 8", script)
        self.assertIn("stable aim.exe and aimapi.dll files", script)
        self.assertIn("Start-Sleep -Seconds $InstallerCompletionPollSeconds", script)
        self.assertIn(
            "$resolvedAimDirectory = Wait-For-AimInstallation -RequestedDirectory $AimDirectory -InstallerProcess $installerProcess",
            script,
        )
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

    def test_windows_installer_documentation_preserves_native_scope_and_restore(self) -> None:
        documentation = self.install_documentation
        self.assertIn("not portable", documentation)
        self.assertIn("aimapi.dll.aim59-disabled", documentation)
        self.assertIn("Restore aimapi.dll", documentation)
        self.assertIn("aim.realretrolabz.com:5190", documentation)
        self.assertIn("Windows 11 notes", documentation)
        self.assertIn("used successfully in a Windows 11 guest", documentation)
        self.assertIn("does not locate, invoke, or require", documentation)
        self.assertIn("Apply server setting", documentation)
        self.assertIn("Uninstall AIM", documentation)

    def test_windows_exe_collects_choices_and_runs_the_native_workflow(self) -> None:
        source = self.exe_source
        self.assertIn("System.Windows.Forms", source)
        self.assertIn("OpenFileDialog", source)
        self.assertIn('Verb = "runas"', source)
        self.assertIn("UseShellExecute = true", source)
        self.assertIn("NativeErrorCode == 1223", source)
        self.assertIn("NativeWorkflow.Install", source)
        self.assertIn("NativeWorkflow.Restore", source)
        self.assertIn("NativeWorkflow.ApplyServer", source)
        self.assertIn("NativeWorkflow.StartUninstall", source)
        self.assertIn("Use aim.realretrolabz.com:5190", source)
        self.assertIn("Keep AIM's original server setting", source)
        self.assertIn("Use another server:", source)
        self.assertIn("Download the verified installer from OldVersion.com", source)
        self.assertIn("Use a local original AIM 5.9.3861 installer:", source)
        self.assertIn("Remove 'Free AOL && Unlimited Internet' desktop shortcut after installation", source)
        self.assertIn("removeAolDesktopShortcut.Checked", source)
        self.assertIn("Checked = false", source)
        self.assertIn("Restore aimapi.dll", source)
        self.assertIn("Apply server setting", source)
        self.assertIn("Uninstall AIM...", source)
        self.assertIn("Windows 10/11 AOL Instant Messenger installer/management tool", source)
        self.assertIn("Install AIM applies the selected server setting", source)
        self.assertIn("Saving server changes in the AIM GUI overwrites that setting", source)
        self.assertIn("select Apply Server Setting", source)
        self.assertIn(r"\r\n\r\nNote:", source)
        self.assertIn("Consolas", source)
        self.assertIn("Color.FromArgb(0, 255, 0)", source)
        self.assertIn("BackColor = Color.Black", source)
        self.assertIn("███████", source)
        self.assertIn("█████████████", source)
        self.assertIn("Location = new Point(18, 4)", source)
        self.assertIn("Size = new Size(1024, 121)", source)
        self.assertIn("ClientSize = new Size(1060, 803)", source)
        self.assertIn("Icon.ExtractAssociatedIcon(Application.ExecutablePath)", source)
        self.assertIn('ApplicationName = "realretrolabz AIM Manager"', source)
        self.assertIn("Text = Program.ApplicationName", source)
        self.assertNotIn("Start the original AIM 5.9.3861 installer now?", source)
        self.assertIn("MessageBoxButtons.YesNo", source)
        self.assertIn("Close realretrolabz AIM Manager and stop its compatibility workflow?", source)
        self.assertIn("details.AppendText(line)", source)
        self.assertIn("BeginInvoke(action)", source)
        self.assertIn("ProgressBar", source)
        self.assertIn("ReportDownloadProgressFromWorker", source)
        self.assertNotIn("DownloadEasterEgg", source)
        self.assertRegex(
            source,
            re.compile(
                r"if \(realretrolabz\.Checked\)\s*\{\s*"
                r"request\.ServerMode = ServerMode\.realretrolabz;",
                re.DOTALL,
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r"else if \(keepAIMDefault\.Checked\)\s*\{\s*"
                r"request\.ServerMode = ServerMode\.Keep;",
                re.DOTALL,
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r"request\.ServerMode = ServerMode\.Custom;\s*"
                r"request\.ServerHost = host;\s*"
                r"request\.ServerPort = port;",
                re.DOTALL,
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r"request\.InstallerSource = localInstaller\.Checked \? InstallerSource\.LocalFile : InstallerSource\.OldVersion;",
                re.DOTALL,
            ),
        )

    def test_windows_exe_has_a_native_installer_backend(self) -> None:
        workflow = self.exe_workflow
        self.assertIn('InstallerPageUrl = "https://www.oldversion.com/', workflow)
        self.assertIn("InstallerSha256", workflow)
        self.assertIn("SHA256.Create()", workflow)
        self.assertIn("HttpWebRequest", workflow)
        self.assertIn("CookieContainer", workflow)
        self.assertIn("SecurityProtocolType.Tls12", workflow)
        self.assertIn("Registry.CurrentUser.CreateSubKey", workflow)
        self.assertIn("UninstallRegistryKey", workflow)
        self.assertIn("RegistryView.Registry32", workflow)
        self.assertIn("UninstallString", workflow)
        self.assertIn("HasAimUninstallerMarker", workflow)
        self.assertIn("IsPathWithinDirectory", workflow)
        self.assertIn("RestoreAimApiForUninstall", workflow)
        self.assertIn("Restored aimapi.dll before starting AIM's uninstaller", workflow)
        self.assertIn("RemoveAolDesktopShortcut", workflow)
        self.assertIn("Free AOL & Unlimited Internet.lnk", workflow)
        self.assertIn("SpecialFolder.CommonDesktopDirectory", workflow)
        self.assertIn("File.Delete(shortcutPath)", workflow)
        self.assertIn("Searching registered AIM uninstall entries", workflow)
        self.assertIn("(?<file>.+?\\.(?:exe|com))", workflow)
        self.assertIn("RequireAimStopped", workflow)
        self.assertIn("aimapi.dll.aim59-disabled", workflow)
        self.assertIn("File.Move(original, disabled)", workflow)
        self.assertIn("File.Move(disabled, original)", workflow)
        self.assertIn("WaitForAimInstallation", workflow)
        self.assertIn("InstallerCompletionPollMilliseconds = 2000", workflow)
        self.assertIn("InstallerFileSettleSeconds = 8", workflow)
        self.assertIn("aim.exe and aimapi.dll files", workflow)
        self.assertIn("Process.Start", workflow)
        self.assertNotIn("WaitForExit()", workflow)
        self.assertNotIn("install-aim59.ps1", self.exe_source + workflow)
        self.assertNotIn("powershell.exe", self.exe_source + workflow)

    def test_windows_exe_project_and_build_output_are_source_only(self) -> None:
        self.assertIn("<OutputType>WinExe</OutputType>", self.exe_project)
        self.assertIn("<TargetFrameworkVersion>v4.8</TargetFrameworkVersion>", self.exe_project)
        self.assertIn("<AssemblyName>rrlzAIM</AssemblyName>", self.exe_project)
        self.assertIn("<ApplicationIcon>assets\\aim59-setup.ico</ApplicationIcon>", self.exe_project)
        self.assertIn("<Content Include=\"assets\\aim59-setup.ico\" />", self.exe_project)
        self.assertIn(".build\\windows-exe", self.exe_project)
        self.assertIn("windows\\AIM59Setup\\Program.cs", self.exe_build_script)
        self.assertIn("windows\\AIM59Setup\\NativeWorkflow.cs", self.exe_build_script)
        self.assertIn("windows\\AIM59Setup\\assets\\aim59-setup.ico", self.exe_build_script)
        self.assertIn(".build\\windows-exe", self.exe_build_script)
        self.assertIn("rrlzAIM.exe", self.exe_build_script)
        self.assertIn("/target:winexe", self.exe_build_script)
        self.assertIn("/win32icon:$iconPath", self.exe_build_script)
        self.assertIn("csc.exe", self.exe_build_script)
        self.assertIn("mono-csc", self.exe_mono_build_script)
        self.assertIn("windows/AIM59Setup/Program.cs", self.exe_mono_build_script)
        self.assertIn("windows/AIM59Setup/NativeWorkflow.cs", self.exe_mono_build_script)
        self.assertIn("windows/AIM59Setup/assets/aim59-setup.ico", self.exe_mono_build_script)
        self.assertIn('OUTPUT_PATH="$OUTPUT_DIRECTORY/rrlzAIM.exe"', self.exe_mono_build_script)
        self.assertIn(".build/windows-exe", self.exe_mono_build_script)
        self.assertIn("-target:winexe", self.exe_mono_build_script)
        self.assertIn("-win32icon:$ICON_PATH", self.exe_mono_build_script)
        self.assertIn("unexpected build output", self.exe_mono_build_script)
        self.assertIn("rrlzAIM.exe.sha256", self.exe_mono_build_script)
        self.assertIn(".build/", self.gitignore)
        self.assertIn("aim593861.exe", self.gitignore)
        self.assertNotIn("aim*.exe", self.gitignore)

    def test_windows_exe_documentation_keeps_validation_and_scope_honest(self) -> None:
        for documentation in (
            self.install_documentation,
            self.exe_handoff,
            self.readme,
        ):
            with self.subTest(documentation=documentation[:32]):
                self.assertIn("rrlzAIM.exe", documentation)
                self.assertIn("native", documentation.lower())
        self.assertIn("Optional Pre-AIM thumb-drive checks", self.install_documentation)
        self.assertIn("used successfully in a Windows 11 guest", self.install_documentation)
        self.assertIn("no external frontend checksum gate", self.exe_handoff)
        self.assertIn("## Windows utility asset", self.release_documentation)
        self.assertIn("rrlzAIM.exe.sha256", self.release_documentation)
        self.assertIn("install-aim59.ps1", self.release_documentation)
        archived_gui = ROOT / "scripts" / "windows" / "install-aim59-gui.ps1"
        self.assertTrue(archived_gui.exists())
        self.assertIn("ARCHIVED PROOF OF CONCEPT", archived_gui.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
