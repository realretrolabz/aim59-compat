# Architecture

The terminal manager is the canonical compatibility engine and distribution
path for Linux.

```text
Version manifest + installer source
                 |
                 v
      shared acquisition + verification
                 |
                 v
       shared command orchestration
                 |
                 v
       build-target/host selector
          /             \
  Wine backend       future native Windows backend
       |
       v
prefix files + registry + recorded state
```

The Windows backend has two possible delivery modes. The preferred mode is a
relocatable directory that requires no installation and creates no AIM- or
project-specific host registry entries. If Windows 11 testing proves that
strict portability cannot support the required AIM experience, the accepted
fallback discovers and modifies a normal AIM installation performed by the
user. Only the first mode may be called portable. The feasibility gate and
required features are defined in
[`WINDOWS_ROADMAP.md`](WINDOWS_ROADMAP.md).

## Backend boundary and build targets

`rrlzAIM/orchestration.py` owns the platform-neutral sequencing for
setup, doctor, launch, and rollback. It depends on the small
`CompatibilityBackend` protocol in `rrlzAIM/backends/base.py`. Setup
keeps backend preflight ahead of installer acquisition, then passes the
verified external installer path to the selected backend. Installer download
and identity verification do not depend on a backend.

`rrlzAIM/backends/__init__.py` selects a backend from the build target and
rejects a host/target mismatch before constructing it. The current `rrlzAIMlinux`
source and release artifact have a fixed `wine` target and accept the existing
Wine options; there is intentionally no routine user-facing backend switch.
The reserved `windows` target is recognized on a Windows host but reports that
its backend is not implemented or supported. It performs no Windows
compatibility operation.

`patch-prefix` remains outside the shared backend contract. It is an explicit
Wine-prefix adapter and is rejected outside the Wine build. This keeps the
future native backend from acquiring artificial prefix, Winetricks, patched
DLL, or Wine registry methods. `set-server` is likewise Wine-specific and
writes a selected AIM `Host` and `Port` preference without acquiring or running
the installer. `uninstall` is Wine-specific too: it runs AIM's prefix-local
uninstaller, confirms that `aim.exe` is gone, then removes only the
project-owned menu entry and that selected prefix.

## Version manifest

`manifests/aim-5.9.3861.json` is the supported-version contract. It pins the
installer identity, known third-party source resolver, Wine requirements,
prefix layout, Winetricks packages, and versioned patched `mciwave.dll` checksums.

The OldVersion source stores a stable version-page URL rather than its
short-lived download token. The downloader loads the page, submits its current
download form, saves the installer outside the repository, and accepts it only
when the pinned SHA-256 matches.

## Commands

`rrlzAIMlinux` with no subcommand opens the terminal manager. It uses a
catalog of successful guided installations rather than scanning for prefixes.
The user selects an AIM data directory and Wine uses its fixed `prefix` child.
The **Install AIM** action validates Wine, selects the matching DLL, acquires
and verifies the installer, collects server, AOL-shortcut, and XDG-launcher
choices, then creates the win32 prefix and invokes the Wine backend.

The existing ordering is preserved: Wine command/version and patched-DLL
preflight occurs before acquisition, and the selected backend receives the
installer only after acquisition and checksum verification succeeds.

`rrlzAIMlinux patch-prefix` applies only the compatibility operations to an existing
AIM prefix. This is the adapter boundary used by the legacy
`apply-prefix-fixes.sh` wrapper and remains useful for manual installations.

`rrlzAIMlinux uninstall` requires explicit confirmation (or `--non-interactive
--yes`). It temporarily restores the patcher-owned `aimapi.dll` rename for
AIM's uninstaller, waits for Wine's uninstaller processes, verifies that AIM's
executable is absent, removes the project-owned XDG entry, and recursively
deletes the selected Wine prefix. An incomplete or cancelled uninstall leaves
the entry and prefix intact.

`rrlzAIMlinux doctor`, `launch`, and `rollback` inspect and manage the resulting
prefix. Applied state and the `system.ini` backup live in the prefix under
`.rrlzAIM/`.

## Wine backend

The Wine backend:

1. selects the version-matched DLL and validates its exact checksum and marker
2. verifies that `aim.exe` and `sb.dll` exist
3. registers `sb.dll`
4. disables `aimapi.dll` by renaming it
5. backs up and replaces the prefix-local `mciwave.dll`
6. sets the native-then-builtin override and both MCI WaveAudio mappings
7. updates `system.ini`
8. extracts AIM's icon from the user's installed executable and writes a
   project-owned XDG application-menu entry
9. optionally writes the selected AIM server preference and removes only the
   exact opt-in AOL desktop shortcut after safely recording its backup
10. records the applied state for diagnostics and rollback

The system Wine installation is never modified.

## Distribution adapters

The terminal release archive is the primary standalone distribution. It
packages an executable copy of the zip application beside the patched DLLs so
`./rrlzAIMlinux` works without assembly or extra path arguments. It also
includes checksums, licenses, documentation, and the Wine source/build
materials required for the modified DLL.

`scripts/build-patcher.py` packages the Python engine and manifest into the
self-contained zip application used by the terminal archive. It does not
contain AIM.

The native Windows implementation now lives separately in the
self-contained C# `windows/AIM59Setup/` source tree; it is not a Python
backend or a Linux release artifact. It may not inherit Wine-specific
fixes. It has been guest-tested on Windows 11; Windows 10 has not been tried.
See [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md) for its Windows notes.
