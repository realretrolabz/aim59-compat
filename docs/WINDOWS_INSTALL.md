# Windows 11 AIM 5.9 setup

This is an installed workflow for AIM 5.9.3861 on Windows 11. It is not portable:
AIM's normal installer writes program files, registry entries,
and user data to Windows. It has been used successfully in a Windows 11 guest;
Windows 10 has not been tried.

`rrlzAIM.exe` (realretrolabz AIM Manager) is the active native Windows
installer and compatibility utility. It is self-contained: it downloads or validates the original AIM
installer, verifies its pinned identity, runs it, waits for the installed files
to settle, disables `aimapi.dll`, writes the selected current-user server
setting, and can restore its DLL change. It does not ship AIM files, change
Windows compatibility mode, register `sb.dll`, or copy a Wine DLL into Windows.

The older [`install-aim59.ps1`](../scripts/windows/install-aim59.ps1) is kept
only as archived proof-of-concept source and historical test evidence. The EXE
does not locate, invoke, or require it.

## Download the release EXE (recommended)

Download `rrlzAIM.exe` and `rrlzAIM.exe.sha256` from the project's GitHub
Release. Keep the two files together, then verify the EXE before running it:

```powershell
$expected = (Get-Content .\rrlzAIM.exe.sha256).Split()[0]
$actual = (Get-FileHash .\rrlzAIM.exe -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw 'rrlzAIM.exe SHA-256 verification failed.' }
```

The release EXE is self-contained; after verification, run it directly or copy
it to a removable drive. It does not need a repository checkout or an adjacent
PowerShell script.

## Build the EXE from source (optional)

On Windows, from a repository checkout, run:

```powershell
.\scripts\windows\build-aim59-setup.ps1
```

The command uses the installed .NET Framework C# compiler and creates only:

```text
.build\windows-exe\rrlzAIM.exe
```

The output directory is ignored. Do not add the compiled EXE to Git, `dist/`,
or a test fixture. A Windows release may distribute it as a standalone asset
with a SHA-256 file; see [RELEASE.md](RELEASE.md#windows-utility-asset). The
build command and source target .NET Framework 4.8. The launcher has been used
successfully in a Windows 11 guest.

If Windows is only available in a VM, a Linux host with `mono-devel` can also
run `./scripts/build-aim59-setup-mono.sh` to create the same managed EXE in the
same ignored output directory. That cross-build is convenient for copying to
the VM, but it does not execute the EXE on Windows by itself.

## Run the native setup

Run the downloaded EXE directly, or copy a downloaded or generated EXE to a
removable drive or other test location:

```text
<drive>:\AIM59-Test\
  rrlzAIM.exe
  WINDOWS_INSTALL.md (optional instructions)
```

The EXE needs no adjacent PowerShell script. Do not put an AIM installer in the
repository or Git. A local original installer, if used, must be separately
obtained and kept outside the repository.

1. Double-click `rrlzAIM.exe` and accept the UAC prompt. Use the signed-in
   administrator account for testing: the OldVersion cache and `HKCU` server
   preference belong to the account that accepts elevation.
2. Select one installer source:
   - **Download the verified installer from OldVersion.com** downloads to
     `%LOCALAPPDATA%\rrlzAIM\installers` and verifies it.
   - **Use a local original AIM 5.9.3861 installer** opens a file picker; the
     EXE verifies the selected file before using it.
3. Select one server choice:
   - **Use `aim.realretrolabz.com:5190`**;
   - **Keep AIM's original server setting**; or
   - **Use another server** with a host and port from 1 through 65535.
   Optionally select **Remove 'Free AOL & Unlimited Internet' desktop shortcut
   after installation**. It is unchecked by default and targets only that exact
   shortcut filename on the current-user and Public Desktop.
4. Click **Install AIM**. A fresh OldVersion download displays byte progress.
   The original AIM installer opens in its own window.
5. The EXE does not rely on the original installer's launcher process exiting.
   It polls every two seconds until installed `aim.exe` and `aimapi.dll` both
   exist and remain unchanged for eight seconds. It waits at most 15 minutes.
6. After that stable-file check, the EXE stops auto-launched AIM, renames
   `aimapi.dll` to `aimapi.dll.aim59-disabled`, and applies the selected server
   setting. Read the final status/details rather than treating an installer
   window closing as success.

An installer from the cache or a browsed local file must match the pinned
8,715,352-byte SHA-256 identity. The installed `aim.exe` is not an installer
and cannot be selected for this workflow.

## Reapply a server setting

The **Apply server setting** button applies the selected realretrolabz or
Custom host/port without downloading or reinstalling AIM. Close AIM first; the
new value is intended for its next launch.

The observed AIM Server settings dialog does not immediately display the
externally applied value. Clicking **Save** in that AIM dialog writes its own
displayed/default value back to the registry immediately, overriding the EXE's
selection. Use **Apply server setting** again after such a save, or enter the
desired host and port in AIM's own dialog before saving it. **Keep AIM's
original server setting** intentionally makes no change.

## Restore the tool-owned change

Close AIM, then run `rrlzAIM.exe` as administrator and choose **Restore
aimapi.dll**. The EXE restores `aimapi.dll` only when its
`aimapi.dll.aim59-disabled` file is present and no replacement `aimapi.dll`
exists. It intentionally leaves the server preference unchanged. Use AIM's own
uninstaller if you want to remove AIM itself.

## Start AIM's normal uninstaller

With AIM closed, choose **Uninstall AIM...** and confirm the warning. The EXE
looks through the 32-bit and 64-bit `HKLM`/`HKCU` registered uninstall entries.
It accepts an AIM-marked entry when its installation location matches, or any
entry whose direct registered uninstaller executable is inside the detected AIM
installation. It then starts that exact `UninstallString` directly—without
invoking a shell. Before starting it, the EXE restores its tool-owned
`aimapi.dll.aim59-disabled` rename; it refuses to overwrite a conflicting DLL.
Complete the ordinary uninstaller in its own window. This action can remove AIM
and user data depending on the choices made there; the EXE does not infer or
report the uninstaller's eventual result.

## Optional Pre-AIM thumb-drive checks

Use these notes if you want to exercise the workflow again from the powered-off
`Pre-AIM` snapshot. Keep screenshots, raw logs, VM disks, installers, installed
AIM files, screen names, and other private evidence outside Git.

1. Download the release EXE or build it from source, then put only
   `rrlzAIM.exe` plus optional instructions in
   the removable-drive test folder.
2. Restore `Pre-AIM`, sign in as the intended administrator, run the EXE from
   the removable drive, and confirm a denied UAC prompt exits clearly without
   beginning download or installation.
   Confirm **Install AIM** begins the selected download or launches the verified
   local installer without an extra confirmation dialog.
3. On separate clean-snapshot runs, test a fresh OldVersion download and a
   separately supplied local original installer. For the OldVersion test,
   confirm visible byte progress and a clear identity/download error if one
   occurs.
4. On separate clean-snapshot runs, exercise realretrolabz, Keep, and Custom
   host/port. Confirm the stable-file wait appears after the original installer
   launches and complete the ordinary installer window.
   On one such run, opt into the AOL shortcut cleanup and confirm it removes
   only the exact named desktop shortcut from the current-user and Public
   Desktop locations when present.
5. After a reported success, confirm the observed
   `aimapi.dll.aim59-disabled` state. Use **Restore aimapi.dll**, then confirm
   `aimapi.dll` returns and the server preference is unchanged by restore.
6. With AIM closed, set realretrolabz or Custom and choose **Apply server
   setting**. Confirm the registry value changes without launching an
   installer. Then deliberately save AIM's own Server settings page and confirm
   it overwrites the registry value; reapply the EXE setting and record the
   observed next-launch behavior.
7. On a separate restored snapshot, choose **Uninstall AIM...**. Confirm it
   restores the tool-owned `aimapi.dll` rename before it starts only the normal
   registered AIM uninstaller, then record the observed result.
8. Windows 10 has not been tried. It will likely behave similarly, but use it
   at your own discretion.

## Historical PowerShell reference

The archived PowerShell proof-of-concept successfully completed one direct
Windows guest install and restore using the same two-second polling and
eight-second stable-file behavior now ported into C#. It is evidence for the
behavioral reference only; it is not the active workflow, a release dependency,
or a substitute for the native EXE.

## Windows 11 notes

The native EXE has been used repeatedly on the dedicated Windows 11 test VM.
The launch workaround was observed there: installation followed by disabling
`aimapi.dll` produced a visible, usable AIM window. The archived PowerShell
workflow also completed one install-and-rollback check.
