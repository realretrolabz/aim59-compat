# AGENTS.md

## Project purpose

This repository provides a terminal-first compatibility patcher for running
**AOL Instant Messenger 5.9.3861** under Wine through the terminal-first
realretrolabz AIM Manager.

The repository must never host or redistribute AOL/AIM program files. The
patcher may acquire the installer from a user-selected local path or
third-party URL and must verify known downloads against the pinned manifest.

## Supported target for v0.1.x

- AIM: 5.9.3861
- Wine: 9.0 (runtime validated)
- Wine: 10.0 (source/build validated; runtime validation pending)
- Prefix architecture: win32
- Wine Windows version: Windows XP
- Runtime: `mfc40`
- `sb.dll`: registered with `regsvr32`
- `aimapi.dll`: renamed/disabled
- Wine `mciwave.dll`: version-matched AIM-specific Wine 9.0 or 10.0 patch
- `mciwave` override: native, then builtin
- MCI and MCI32 WaveAudio mappings: `mciwave.dll`

Do not claim support for other Wine or AIM versions without explicit testing.

## Validated Wine sound fix

AIM 5.9 opens notification WAV files through MCI `waveaudio` while passing
`MCI_OPEN_SHAREABLE`.

Wine 9.0 and 10.0's `dlls/mciwave/mciwave.c` reject that flag before the
first open.
The compatibility patch removes only that rejection. Wine's existing
`nUseCount > 0` guard remains intact.

The PE build is then changed from the embedded marker:

`Wine builtin DLL`

to the equal-length marker:

`Wine patched DLL`

so Wine does not substitute its installed builtin implementation when the
prefix copy is selected as native.

Do not replace this with the old Windows XP `mciwave.dll` experiment; that
played one sound and then caused AIM to hang.

## Repository rules

1. Never add:
   - `aim.exe`
   - AIM installers
   - AOL DLL/OCM/resource files
   - extracted AIM installation directories
2. The only prebuilt `.dll` files intentionally tracked in `binaries/` are
   the version-matched modified Wine `mciwave.dll` files.
3. Keep the Wine source patch and build instructions available whenever the
   modified Wine binary is distributed.
4. Do not silently change the supported Wine version.
5. Preserve an unpatch/restore path.
6. Direct Connection / Rendezvous is network-dependent and is not a client
   compatibility release blocker.
7. Installer downloads belong in the user's external cache, never in the
   repository, release assets, fixtures, or Git history.
8. The terminal manager is the canonical implementation. Legacy shell entry
   points must delegate prefix patching to it rather than duplicate the
   compatibility operations.

## Required validation before committing

Run:

```bash
make verify
```

Before changing or replacing the published DLL, also run:

```bash
scripts/verify-mciwave.sh binaries/mciwave-wine9-x86-aim.dll --published
scripts/verify-mciwave.sh binaries/mciwave-wine10-x86-aim.dll --published
```

For a rebuilt DLL:

```bash
make build-wine10
scripts/verify-mciwave.sh dist/mciwave-wine10-x86-aim.dll
```

Review:

```bash
git status --short
git diff --check
git diff
```

Confirm no proprietary AIM binary has entered the repository.

## Definition of done

A change is complete only when:

- shell scripts pass `bash -n`
- Python patcher tests pass
- repository guard finds no AIM binaries
- tracked patched DLL matches `checksums/SHA256SUMS`
- technical documentation matches implementation
- user-visible support claims do not exceed tested configurations

Do not push or publish releases unless explicitly requested.
