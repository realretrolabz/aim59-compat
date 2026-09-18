# Native Windows EXE implementation handoff

Status: implemented and guest-tested on Windows 11. Windows 10 has not been
tried.

## Active direction

`windows/AIM59Setup/` contains the active native Windows implementation:
a small self-contained C# Windows Forms EXE targeting .NET Framework 4.8. It
does not invoke PowerShell or require files beside `rrlzAIM.exe` at runtime.
The older [`install-aim59.ps1`](../scripts/windows/install-aim59.ps1) remains
in the repository only as archived proof-of-concept and historical validation
source.

This direction supersedes the earlier thin-EXE/adjacent-PowerShell design. It
does not alter the released Linux terminal manager.

## Native workflow

The EXE requests UAC elevation, then presents:

- a fresh OldVersion download or a browsed local original AIM 5.9.3861
  installer;
- an unchecked option to remove only the exact `Free AOL & Unlimited Internet`
  desktop shortcut after installation; and
- `aim.realretrolabz.com:5190`, Keep AIM's existing server preference, or a
  custom host and port; and
- **Apply server setting**, **Restore aimapi.dll**, and **Uninstall AIM...**
  actions.

Clicking **Install AIM** starts the selected download or verified local
installer without an extra confirmation. If the setup workflow is already
running, its close warning lets the user end this utility rather than trapping
the window; any separately opened AIM installer must then be closed by the user
and compatibility changes will not finish.

For an OldVersion selection, it preserves the observed form/cookie POST flow,
downloads to `%LOCALAPPDATA%\rrlzAIM\installers`, reports byte progress,
and verifies the pinned 8,715,352-byte SHA-256 identity before launching it. A
browsed local installer receives the same identity verification. The request
path explicitly uses TLS 1.2 so a Mono-built EXE does not inherit legacy .NET
HTTPS defaults on first run.

When selected, the desktop-shortcut cleanup runs after AIM's file-settle check,
DLL rename, and server setting. It considers only the exact `.lnk` filename on
the current-user and Public Desktop, reports removals or errors, and does not
affect any other shortcut.

The original AIM installer launcher may remain alive after the visible setup
finishes, or it may exit before child installation work is done. Therefore the
EXE does not use that launcher as the completion signal. It polls every two
seconds for exactly one expected installed AIM directory containing `aim.exe`
and `aimapi.dll`; both file size and UTC write time must remain unchanged for
eight seconds before the EXE stops auto-launched AIM, renames `aimapi.dll` to
`aimapi.dll.aim59-disabled`, and writes the selected current-user server
setting. The wait has a 15-minute timeout and reports its current state.

Restore leaves the server setting unchanged and refuses to overwrite an
existing `aimapi.dll`. **Apply server setting** lets the selected external
server value be reapplied without reinstalling AIM. The observed AIM Server
settings page displays separate/stale state and writes its displayed value back
to the registry immediately on **Save**, so reapply the EXE choice after using
that page unless the desired host was saved there. **Uninstall AIM...** starts
only a normal registered uninstaller: either an AIM-marked entry whose install
location matches, or an entry whose direct uninstaller is inside the detected
AIM installation or a subdirectory. Before launching it, the EXE restores its
tool-owned `aimapi.dll` rename, refusing any conflicting DLL state. It does not
use a shell or infer the uninstaller result. No AIM files are bundled with the
EXE or committed to the repository.

## Build and copy contract

On Windows, run from a checkout:

```powershell
.\scripts\windows\build-aim59-setup.ps1
```

The reproducible build uses the installed .NET Framework C# compiler and writes
only `.build\windows-exe\rrlzAIM.exe`. `.build/` is ignored. Do not commit
the EXE, an AIM installer, installed AIM files, or private VM evidence.

For a Linux host with `mono-devel`,
`./scripts/build-aim59-setup-mono.sh` cross-builds the same managed EXE to that
ignored output. This is useful when the only Windows environment is a VM. It
does not make Mono a Windows runtime test or replace the Windows-native CI
build.

For a removable-drive test, copy only:

```text
<drive>:\AIM59-Test\
  rrlzAIM.exe
  WINDOWS_INSTALL.md (optional instructions)
```

There is deliberately no `install-aim59.ps1` beside the EXE. The missing-backend
error expected by the retired launcher design no longer applies.

## Guest-test notes

Linux static tests cover source-level UI choices, UAC, network-request and
identity-verification components, file/registry mutation boundaries, stable
completion detection, absence of PowerShell use, and the source-only build
location. They do not compile or run the EXE on Windows.

One Windows guest run of the archived PowerShell proof-of-concept completed the
installer detection workaround and rollback. It remains behavioral reference;
the native EXE is separately guest-tested. The optional fresh-snapshot notes in
[WINDOWS_INSTALL.md](WINDOWS_INSTALL.md#optional-pre-aim-thumb-drive-checks)
and [TESTING.md](TESTING.md#native-windows-setup) are available if you want to
repeat the process. Windows 10 has not been tried.

`make verify` covers the shell, Python manager, release archive, and published
Wine DLL checks. It has no external frontend checksum gate.
