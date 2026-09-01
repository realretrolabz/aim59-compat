# Architecture

The terminal patcher is the canonical compatibility engine. Lutris is a
frontend for discovery, choosing the install location, and launching; it
delegates the complete setup workflow to the same engine used by the command
line.

```text
Version manifest + installer source
                 |
                 v
       AIM 5.9 patcher CLI
          /             \
  Wine backend       future Windows backend
       |
       v
prefix files + registry + recorded state
```

## Version manifest

`manifests/aim-5.9.3861.json` is the supported-version contract. It pins the
installer identity, known third-party source resolver, Wine requirements,
prefix layout, Winetricks packages, and patched `mciwave.dll` checksum.

The OldVersion source stores a stable version-page URL rather than its
short-lived download token. The downloader loads the page, submits its current
download form, saves the installer outside the repository, and accepts it only
when the pinned SHA-256 matches.

## Commands

`aim59 setup` owns the complete terminal workflow: acquire and verify the
installer, validate Wine 9.0, create a win32 prefix, install `winxp` and
`mfc40`, run the installer, and invoke the Wine compatibility backend.

`aim59 patch-prefix` applies only the compatibility operations to an existing
AIM prefix. This is the adapter boundary used by the legacy
`apply-prefix-fixes.sh` wrapper and remains useful for manual installations.

`aim59 doctor`, `launch`, and `rollback` inspect and manage the resulting
prefix. Applied state and the `system.ini` backup live in the prefix under
`.aim59-compat/`.

## Wine backend

The Wine backend:

1. validates the exact published patched-DLL checksum and marker
2. verifies that `aim.exe` and `sb.dll` exist
3. registers `sb.dll`
4. disables `aimapi.dll` by renaming it
5. backs up and replaces the prefix-local `mciwave.dll`
6. sets the native-then-builtin override and both MCI WaveAudio mappings
7. updates `system.ini`
8. records the applied state for diagnostics and rollback

The system Wine installation is never modified.

## Distribution adapters

The terminal release archive is the primary standalone distribution. It
packages an executable copy of the zip application beside the patched DLL so
`./aim59 setup` works without assembly or extra path arguments. It also
includes checksums, licenses, documentation, and the Wine source/build
materials required for the modified DLL.

The Lutris YAML downloads `aim59-patcher.pyz` and the patched Wine DLL from a
version-pinned GitHub Release. It uses Lutris file aliases to call `aim59
setup --source oldversion`; the canonical engine acquires and verifies AIM,
creates the prefix, runs the installer, and applies the Wine backend.

`scripts/build-patcher.py` packages the Python engine and manifest into the
self-contained zip application used by both the terminal archive and Lutris.
It does not contain AIM.

Future Windows 10/11 support should be implemented as a separate backend. It
may share acquisition, manifests, verification, state, and terminal UI, but it
must not inherit Wine-specific fixes or support claims without testing.
