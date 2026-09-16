# Windows EXE front-end handoff

Status: prepared 2026-09-13 for the next implementation thread.

## Completed before this handoff

The project owner selected an installed Windows 11 workflow for the current
prototype. The canonical implementation is
[`scripts/windows/install-aim59.ps1`](../scripts/windows/install-aim59.ps1).
It downloads the pinned AIM 5.9.3861 installer from OldVersion or accepts a
local original installer only after the same size and SHA-256 check. It runs
the normal installer, renames `aimapi.dll` to
`aimapi.dll.aim59-disabled`, and supports a reversible restore.

The script offers a server choice: use the RealRetroLabz default, leave AIM's
original server preference untouched, or set a custom OSCAR hostname and port.
It writes only AIM's current-user global connection profile; existing
per-screen-name profiles may override that setting.

`scripts/windows/install-aim59-gui.ps1` is a Windows Forms prototype. It
elevates, presents the installer and server choices, and invokes the canonical
script with explicit parameters. It deliberately contains no independent
download, hash-check, patch, registry, or rollback logic.

The launch workaround was observed once on the dedicated Windows 11 VM:
normal installation plus disabling `aimapi.dll` produced a visible, usable AIM
window. No XP compatibility setting, `sb.dll` change, or Wine file was used.
The wider Windows feature, recovery, and repeatability gates remain incomplete.

## Objective for the next thread

Replace the PowerShell GUI prototype with a user-facing Windows executable
while keeping `install-aim59.ps1` as the sole installer and patch backend.

The desired release layout is:

```text
AIM59Setup.exe
install-aim59.ps1
README.txt or equivalent
```

The executable must locate its backend next to itself and fail clearly if it is
missing. It must launch the backend elevated and display its completion or
error result. It must offer the same choices as the PowerShell prototype:

- OldVersion download or a browseable local original installer;
- RealRetroLabz default, unchanged AIM setting, or custom host/port; and
- `aimapi.dll` restore.

## Constraints

- Do not embed, download into the repository, or redistribute any AIM program
  file or installer.
- Do not reimplement download, hash validation, installation, patching,
  registry writes, or rollback in the EXE. Delegate to the backend script.
- Do not use Wine DLLs, `sb.dll` registration, or Windows XP compatibility
  settings.
- Keep the EXE source in the repository, but do not add a built `.exe` to Git.
  The repository guard currently rejects tracked executables. A future release
  package may contain the project-owned EXE only after its build and validation
  policy is deliberately updated.
- Preserve the Linux/Wine patcher and Lutris behavior.
- Keep the experimental Windows status honest. Windows 10 and the full Windows
  11 feature/recovery matrix are untested.

## Recommended implementation approach

Use a small C# Windows Forms project targeting a Windows 11-inbox .NET runtime
or package a self-contained runtime only if that is demonstrated necessary.
Prefer a straightforward side-by-side EXE plus PowerShell backend over a
single-file extractor. The next thread must check the actual Windows build and
runtime prerequisites before choosing the final target framework.

Add a reproducible build command that writes only to an ignored output
directory, then add Linux-runnable static tests and Windows runtime validation
for the actual EXE-to-backend argument forwarding and elevation behavior.

## Validation already run

- 40 Linux unit/static tests passed.
- `git diff --check` passed.
- The repository file scan found only the two allowed Wine DLLs; no AIM binary
  entered the pending change set.
- `make verify` reached its known pre-existing failure at the frozen Lutris
  release-package checksum comparison. Shell syntax, YAML, and all Python
  tests ran before that point.
- Neither PowerShell script nor a native EXE front end has yet received a
  Windows runtime test.

## Copy-ready next-thread prompt

```text
Read AGENTS.md, docs/WINDOWS_INSTALL.md, docs/WINDOWS_FINDINGS.md, and
docs/WINDOWS_EXE_HANDOFF.md. Implement only the Windows EXE front end described
there. Keep install-aim59.ps1 as the canonical backend; the EXE must delegate
all download, validation, installation, patching, server configuration, and
rollback work to that script. Do not add AIM files or a compiled EXE to Git, do
not change Linux/Wine or Lutris behavior, and do not claim broad Windows
support. Add a reproducible ignored-output build path, tests, and a Windows
runtime-validation checklist. Run the applicable repository checks and report
any existing verifier failure separately.
```
