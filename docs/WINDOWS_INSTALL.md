# Windows 11 AIM 5.9 setup

This is an experimental installed workflow for AIM 5.9.3861 on Windows 11. It
is not portable: AIM's normal installer writes program files, registry entries,
and user data to Windows. Windows 10 and the Windows 11 feature/recovery matrix
remain untested.

`rrlzAIM.exe` (realretrolabz AIM Manager) is the active native Windows
installer and compatibility utility. It is self-contained: it downloads or validates the original AIM
installer, verifies its pinned identity, runs it, waits for the installed files
to settle, disables `aimapi.dll`, writes the selected current-user server
setting, and can restore its DLL change. It does not ship AIM files, change
Windows compatibility mode, register `sb.dll`, or copy a Wine DLL into Windows.

The older [`install-aim59.ps1`](../scripts/windows/install-aim59.ps1) is kept
only as archived proof-of-concept source and historical test evidence. The EXE
does not locate, invoke, or require it.

## Build the EXE

On Windows, from a repository checkout, run:

```powershell
.\scripts\windows\build-aim59-setup.ps1
```

The command uses the installed .NET Framework C# compiler and creates only:

```text
.build\windows-exe\rrlzAIM.exe
```

The output directory is ignored. Do not add the compiled EXE to Git, `dist/`,
a release asset, or a test fixture. The build command and source target .NET
Framework 4.8. A Windows build and runtime check is required before treating
this experimental utility as usable.

If Windows is only available in a VM, a Linux host with `mono-devel` can also
run `./scripts/build-aim59-setup-mono.sh` to create the same managed EXE in the
same ignored output directory. That cross-build is convenient for copying to
the VM, but it does not replace the Windows-native build/guest runtime check.

## Run the native setup

Copy the generated EXE to a removable drive or other test location:

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
     `%LOCALAPPDATA%\AIM59-Compat\installers` and verifies it.
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

The **Apply server setting** button applies the selected RealRetroLabz or
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

## Required Pre-AIM thumb-drive tests

These instructions are a test plan, not a claim that the native EXE has
completed Windows runtime validation. Restore the powered-off `Pre-AIM`
snapshot before every independent test run. Keep screenshots, raw logs, VM
disks, installers, installed AIM files, screen names, and other private
evidence outside Git.

1. Build the EXE and put only `rrlzAIM.exe` plus optional instructions in
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
4. On separate clean-snapshot runs, exercise RealRetroLabz, Keep, and Custom
   host/port. Confirm the stable-file wait appears after the original installer
   launches and complete the ordinary installer window.
   On one such run, opt into the AOL shortcut cleanup and confirm it removes
   only the exact named desktop shortcut from the current-user and Public
   Desktop locations when present.
5. After a reported success, confirm the observed
   `aimapi.dll.aim59-disabled` state. Use **Restore aimapi.dll**, then confirm
   `aimapi.dll` returns and the server preference is unchanged by restore.
6. With AIM closed, set RealRetroLabz or Custom and choose **Apply server
   setting**. Confirm the registry value changes without launching an
   installer. Then deliberately save AIM's own Server settings page and confirm
   it overwrites the registry value; reapply the EXE setting and record the
   observed next-launch behavior.
7. On a separate restored snapshot, choose **Uninstall AIM...**. Confirm it
   restores the tool-owned `aimapi.dll` rename before it starts only the normal
   registered AIM uninstaller, then record the observed result; do not treat it
   as an uninstaller/recovery pass without completing the full check.
8. If AIM is visibly launched, record only the observed result. Do not infer a
   full feature, sound, recovery, repeatability, Windows 10, or broad support
   pass.

## Historical PowerShell reference

The archived PowerShell proof-of-concept successfully completed one direct
Windows guest install and restore using the same two-second polling and
eight-second stable-file behavior now ported into C#. It is evidence for the
behavioral reference only; it is not the active workflow, a release dependency,
or a substitute for the required native-EXE tests.

## Current evidence boundary

The required launch workaround was observed on the dedicated Windows 11 test
VM: normal installation followed by disabling `aimapi.dll` produced a visible,
usable AIM window. The archived PowerShell workflow also completed one
install-and-rollback check. This does not establish native-EXE behavior,
release-gate features, repeatability on other Windows versions, or broad public
support.
