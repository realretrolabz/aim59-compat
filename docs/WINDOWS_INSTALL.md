# Windows 11 installed compatibility setup

This is an experimental installed compatibility workflow for AIM 5.9.3861 on
Windows 11. It is not portable: AIM's normal installer writes its own files,
registry entries, and user data to Windows.

The script downloads the original installer from OldVersion.com to an external
user cache, or accepts a user-selected original installer. It verifies the
pinned 8,715,352-byte SHA-256 identity in either case, runs the normal
interactive installer, then renames `aimapi.dll` to
`aimapi.dll.aim59-disabled`. Renaming rather than deleting makes the only
tool-owned file change reversible.

After installation it asks whether to use `aim.realretrolabz.com:5190`, keep
the original AIM setting unchanged, or enter another OSCAR host and port. The
first option is the default when you press Enter.

The script never ships AIM files, never changes Windows compatibility mode,
never registers `sb.dll`, and never copies any Wine DLL into Windows.

## Run it

1. Copy this repository or the released Windows scripts to the Windows machine.
2. Open **Windows PowerShell** with **Run as administrator**.
3. Run:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\install-aim59.ps1
   ```

   The execution-policy change is for that PowerShell window only. The AIM
   installer remains interactive; accept its normal installation location.

For a graphical wizard instead, right-click `install-aim59-gui.ps1` and choose
**Run with PowerShell**, or run:

```powershell
.\install-aim59-gui.ps1
```

The wizard elevates itself when necessary, offers the same server choices, and
also lets you download from OldVersion or browse to a local installer. It calls
`install-aim59.ps1` as its backend and does not contain a separate download,
patch, checksum, or registry implementation.

The download is cached beneath `%LOCALAPPDATA%\AIM59-Compat\installers`, not
in the repository or script directory. A cached installer is reused only when
its size and SHA-256 match the pinned identity.

A local-file selection must be the original `aim593861.exe` installer and pass
the same identity check. The installed `aim.exe` is not an installer and cannot
be used by this workflow on its own.

For an unattended selection, choose a server mode explicitly:

```powershell
.\install-aim59.ps1 -ServerMode RealRetroLabz
.\install-aim59.ps1 -ServerMode Keep
.\install-aim59.ps1 -ServerMode Custom -ServerHost example.org -ServerPort 5190
```

To use a local original installer from PowerShell:

```powershell
.\install-aim59.ps1 -InstallerPath 'D:\Downloads\aim593861.exe'
```

To use a nonstandard AIM installation directory:

```powershell
.\install-aim59.ps1 -AimDirectory 'D:\Apps\AIM'
```

## Restore the tool-owned change

Close AIM, open an elevated PowerShell window, and run:

```powershell
.\install-aim59.ps1 -Rollback
```

This restores `aimapi.dll` only when the script's
`aimapi.dll.aim59-disabled` file is present and no replacement `aimapi.dll`
exists. It intentionally leaves your AIM server preference alone. Use AIM's
own uninstaller if you want to remove AIM itself.

## Current evidence boundary

The required launch workaround was observed once on the dedicated Windows 11
test VM: normal installation followed by disabling `aimapi.dll` produced a
visible, usable AIM window. Windows XP compatibility mode and `sb.dll`
registration were not applied in that successful run. This does not yet
establish all release-gate features, repeatability on other Windows versions,
or broad public support.
