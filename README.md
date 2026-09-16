# AIM 5.9 Compatibility Patcher

Run **AOL Instant Messenger 5.9.3861** on Linux with Wine 9.0 through a
guided terminal installer or a Lutris frontend. The repository checkout also
contains a build-verified Wine 10.0 patch candidate for runtime testing.

The patcher downloads or accepts the original AIM installer, creates an
isolated 32-bit Wine prefix, installs the required legacy runtime, and applies
the prefix-local fixes needed for AIM and repeated notification sounds. It
does not replace or modify the system Wine installation.

This repository does not contain AOL/AIM program files. The installer can be
selected locally, downloaded from a user-provided URL, or retrieved from a
configured unaffiliated archive and verified against a pinned SHA-256.

## Supported configuration

The v0.1.x support target is deliberately narrow:

| Component | Supported target |
| --- | --- |
| AIM | 5.9.3861 |
| Wine | 9.0 (runtime validated); 10.0 (build verified, runtime validation pending) |
| Wine prefix | 32-bit (`win32`) |
| Windows mode | Windows XP |
| Legacy runtime | `mfc40` |
| SuperBuddy | `sb.dll` registered with `regsvr32` |
| `aimapi.dll` | renamed and disabled |
| Notification audio | version-matched patched Wine `mciwave.dll` |
| DLL override | native, then builtin |

The reference setup has been used for sign-in, buddy lists, IM send/receive,
buddy icons, chat rooms, and repeated notification sounds. Direct Connection
and file transfer depend on AIM Rendezvous networking and may require firewall
or port-forwarding configuration.

Other AIM and Wine versions are not supported unless they are tested
explicitly.

## Requirements

- Linux
- Python 3.10 or newer
- system Wine 9.0 or 10.0 with 32-bit support
- Winetricks
- `cabextract`
- a graphical session in which the AIM installer can run

On Debian, `wine32:i386` must be installed. The patcher reports the exact
package command before downloading AIM when Wine emits its missing-wine32
warning.

The terminal patcher checks Wine's version before creating or changing the
prefix. Consult [INSTALL.md](docs/INSTALL.md) for the manual known-good recipe.

## Choose an installation path

### 1. Terminal release

Download `aim59-compat-0.1.2-linux.tar.gz` from the GitHub Release, then run:

```bash
tar -xzf aim59-compat-0.1.2-linux.tar.gz
cd aim59-compat-0.1.2
./aim59 setup
```

The v0.1.2 bundle contains both versioned DLLs and selects the one that matches
the detected Wine version, so no manual `--patched-dll` argument is required.
Wine 9.0 remains runtime validated; Wine 10.0 is available as a build-validated
candidate while its repeated-sound runtime matrix is completed.

### 2. Lutris

Import `aim-5.9.3861.yml` from the GitHub Release or install it from a future
Lutris.net listing. Lutris downloads the same canonical patcher engine and
performs setup through its graphical workflow.

### 3. Native Windows

An experimental Windows 11 installed-compatibility script is available at
[`scripts/windows/install-aim59.ps1`](scripts/windows/install-aim59.ps1).
It downloads and verifies the pinned installer, runs AIM's ordinary installer,
renames `aimapi.dll` to disable it, and configures a selectable OSCAR host and
port. It is not portable and has not passed the full Windows release gate;
Windows 10 is untested. See [WINDOWS_INSTALL.md](docs/WINDOWS_INSTALL.md) for
use and rollback. A small Windows Forms wizard
([`install-aim59-gui.ps1`](scripts/windows/install-aim59-gui.ps1)) invokes the
same script backend. See [WINDOWS_ROADMAP.md](docs/WINDOWS_ROADMAP.md) for the
remaining validation work.

## Repository quick start

From a repository checkout, start the guided installer:

```bash
./aim59 setup
```

The patcher asks where the AIM installer should come from:

1. download AIM 5.9.3861 from the configured OldVersion.com page
2. select a local `aim593861.exe`
3. enter another direct HTTP or HTTPS URL

It then shows the prefix and patched DLL paths before making changes.

The defaults are:

```text
Wine prefix:     ~/.local/share/aim59-compat/prefix
Installer cache: ~/.cache/aim59-compat/installers
```

When setup finishes:

```bash
./aim59 doctor
./aim59 launch
```

## Noninteractive setup

Download the pinned installer from the configured archive:

```bash
./aim59 setup --source oldversion --yes
```

Use an installer already on disk:

```bash
./aim59 setup \
  --installer /path/to/aim593861.exe \
  --yes
```

Download from another URL:

```bash
./aim59 setup \
  --installer-url https://mirror.example/aim593861.exe \
  --yes
```

Choose a different Wine prefix:

```bash
./aim59 setup \
  --source oldversion \
  --prefix "$HOME/.wine-aim59" \
  --yes
```

For automation, combine an explicit source with `--non-interactive`. Preview
the complete action plan without creating or changing a prefix with
`--dry-run`:

```bash
./aim59 setup \
  --source oldversion \
  --prefix "$HOME/.wine-aim59" \
  --non-interactive \
  --dry-run
```

## Command reference

| Command | Purpose |
| --- | --- |
| `aim59 setup` | Acquire AIM, create a prefix, install it, and apply fixes |
| `aim59 fetch` | Acquire and verify the AIM installer without installing |
| `aim59 verify-installer` | Check a local installer's pinned identity |
| `aim59 sources` | List configured third-party installer sources |
| `aim59 patch-prefix` | Apply fixes to an existing AIM prefix |
| `aim59 doctor` | Check the expected files and patch state |
| `aim59 launch` | Start AIM from the selected prefix |
| `aim59 rollback` | Restore the prefix-local compatibility backups |

Run `./aim59 COMMAND --help` for every option.

### Download without installing

```bash
./aim59 fetch --source oldversion
```

The configured archive copy of `aim593861.exe` is pinned as:

```text
Size:    8,715,352 bytes
SHA-256: 018438bf22672ee119e864d78f838a538ed067bb76296957a00e0c1080979af1
```

The archive uses rotating download tokens. The patcher loads its stable
version page, submits the current download form, saves the result in the
external installer cache, and verifies it before Wine is allowed to execute
it.

Verify an existing installer directly:

```bash
./aim59 verify-installer /path/to/aim593861.exe
```

An unknown checksum stops by default. `--allow-unverified` exists for an
explicitly reviewed variant, but bypasses the main installer-identity safety
check.

### Patch an existing prefix

If AIM 5.9.3861 is already installed under `C:\Program Files\AIM`:

```bash
./aim59 patch-prefix --prefix "$HOME/.wine-aim59"
```

The prefix must already be 32-bit, use Wine 9.0 or 10.0, have Windows XP mode and
`mfc40` configured, and contain `aim.exe` and `sb.dll`. The legacy wrapper is
still available and delegates to the same command:

```bash
scripts/apply-prefix-fixes.sh "$HOME/.wine-aim59"
```

### Diagnose and launch

Commands use the default prefix unless `--prefix` is supplied:

```bash
./aim59 doctor --prefix "$HOME/.wine-aim59"
./aim59 launch --prefix "$HOME/.wine-aim59"
```

`doctor` returns a failure status when required prefix files or the recorded
patch state are missing. More targeted checks are documented in
[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

### Roll back

```bash
./aim59 rollback --prefix "$HOME/.wine-aim59"
```

Rollback restores the saved prefix copy of `mciwave.dll`, restores the saved
`system.ini`, removes the Wine `mciwave` override, and renames
`aimapi.dll.disabled` back to `aimapi.dll` when possible. It also removes the
project-owned application-menu entry and extracted icon. It does not uninstall
AIM, remove the prefix, remove `mfc40`, or unregister `sb.dll`.

## How the patcher works

```text
Version manifest
      |
      +-- local installer
      +-- direct URL
      `-- known archive resolver
                  |
                  v
       download and SHA-256 verification
                  |
                  v
      Wine 9.0 or 10.0 / win32 environment check
                  |
                  v
     prefix + XP mode + mfc40 + AIM installer
                  |
                  v
          prefix compatibility backend
                  |
                  v
        AIM launcher / doctor / rollback
```

### 1. Manifest-driven installer identity

[aim-5.9.3861.json](manifests/aim-5.9.3861.json) is the supported-version
contract. It contains the installer filename, size and accepted SHA-256, Wine
requirements, prefix layout, Winetricks packages, patched DLL checksum, and
known source metadata.

Downloaded AOL files stay in the user's external cache. They are never copied
into the repository or included in project releases.

### 2. Isolated Wine environment

`setup` creates a dedicated win32 Wine prefix, selects Windows XP mode, and
installs `mfc40` with Winetricks. It then runs the verified AIM installer and
checks that `aim.exe` and `sb.dll` were installed in the expected location.

### 3. AIM compatibility changes

The Wine backend applies these prefix-local changes:

| Change | Reason |
| --- | --- |
| Register `sb.dll` | Makes AIM's SuperBuddy COM component available |
| Rename `aimapi.dll` | Avoids a Wine startup/background hang |
| Back up `mciwave.dll` | Preserves a rollback path |
| Install patched `mciwave.dll` | Allows AIM's notification WAV open request |
| Set `mciwave` to `native,builtin` | Loads the prefix DLL before Wine's builtin |
| Set MCI and MCI32 WaveAudio mappings | Routes legacy WaveAudio calls correctly |
| Update `[mci]` in `system.ini` | Preserves the legacy WaveAudio mapping |
| Install an XDG application entry | Adds AIM to the Linux application menu |

The patcher writes its state and `system.ini` backup under:

```text
<prefix>/.aim59-compat/
```

The patched DLLs are pinned as:

```text
Wine 9.0:  23c52cbf2d9ebafc05a5abe10609a0ed49652445318ae8499bba2e1788c57df0
Wine 10.0: 17ba9b95d64fde4ad2d98abdbc623edaa7a66c6f3815221a16aa1f3d0fe30dd2
```

### 4. Notification-sound fix

AIM opens notification WAV files through the legacy MCI `waveaudio` device
while passing `MCI_OPEN_SHAREABLE`. Wine 9.0 and 10.0 reject that flag before
the first open with `MCIERR_UNSUPPORTED_FUNCTION`.

The source patch removes only that early rejection. Wine's existing
`nUseCount > 0` guard remains, so a real conflicting second open is still
rejected.

The built PE DLL's embedded marker is changed from:

```text
Wine builtin DLL
```

to the equal-length marker:

```text
Wine patched DLL
```

This prevents Wine from substituting its installed builtin when the prefix
copy is selected as native. The project does not use the old Windows XP
`mciwave.dll` experiment, which played once and then caused AIM to hang.

See [TECHNICAL.md](docs/TECHNICAL.md) for the detailed investigation and the
versioned patches in [`patches/`](patches/) for the exact source changes.

## Lutris frontend

Install from the repository's single Lutris definition:

```bash
lutris -i lutris/aim-5.9.3861.yml
```

Lutris calls the canonical terminal engine through `aim59 setup --source
oldversion`. The patcher downloads the pinned AIM installer from the
unaffiliated OldVersion archive, verifies its SHA-256, checks system Wine 9.0
or 10.0, selects the matching bundled DLL, creates the win32 prefix, installs
`winxp` and `mfc40`, runs AIM's installer, and applies the compatibility
changes. The YAML does not duplicate that workflow.

The YAML downloads one project-owned implementation asset from the versioned
`v0.1.2` GitHub Release:

- `aim59-compat-0.1.2-linux.tar.gz`

The bundle contains the canonical patcher and the Wine 9.0 and Wine 10.0
patched DLLs, but it does not contain AIM. During installation, the patcher
fetches AIM directly from OldVersion into Lutris's temporary installer cache.
See [lutris/README.md](lutris/README.md) for details.

## Using the loose patcher assets

The `.pyz` and DLLs remain available as implementation assets. Terminal and
Lutris users should normally use the complete Linux archive above. To use the
loose assets directly, place the `.pyz` and both DLLs together and run:

```bash
python3 aim59-patcher.pyz setup
```

The patcher selects the matching adjacent DLL automatically.

## Build and verification

Run the repository validation suite:

```bash
make verify
```

It checks shell syntax, the Lutris YAML, Python patcher tests, the terminal
release archive, the published PE32 DLL structure and marker, checksums,
publishable Windows binaries, and diff whitespace.

Build and verify all release artifacts:

```bash
make release
```

Output:

```text
dist/aim59-compat-0.1.2-linux.tar.gz
dist/aim59-patcher.pyz
dist/mciwave-wine9-x86-aim.dll
dist/mciwave-wine10-x86-aim.dll
dist/aim-5.9.3861.yml
dist/SHA256SUMS
```

Rebuild both versioned components from source:

```bash
make build
scripts/verify-mciwave.sh dist/mciwave-wine9-x86-aim.dll
scripts/verify-mciwave.sh dist/mciwave-wine10-x86-aim.dll
```

Output:

```text
dist/mciwave-wine9-x86-aim.dll
dist/mciwave-wine10-x86-aim.dll
```

Build dependencies and the release process are documented in
[BUILD.md](docs/BUILD.md) and [RELEASE.md](docs/RELEASE.md).

## Project layout

| Path | Purpose |
| --- | --- |
| `aim59` | Repository CLI entry point |
| `aim59_compat/` | Shared orchestration, canonical Python engine, and Wine backend |
| `manifests/` | Supported-version and installer identities |
| `binaries/` | Permitted versioned prebuilt patched Wine DLLs |
| `patches/` | Corresponding versioned Wine source patches |
| `lutris/` | Local and release Lutris frontends |
| `scripts/` | Build, compatibility wrappers, and verification tools |
| `tests/` | Patcher unit tests |
| `docs/` | Architecture, installation, testing, and troubleshooting |

The architecture and future backend boundary are described in
[ARCHITECTURE.md](docs/ARCHITECTURE.md). Native Windows support is planned as
a separate backend and is not currently claimed or implemented. Windows 11 is
the initial target; Windows 10 requires its own validation.

## Licensing and third parties

Project-authored scripts and documentation are MIT licensed.

The modified Wine `mciwave.dll` and its Wine-derived source changes are
distributed under LGPL-2.1-or-later. The corresponding patch and build
instructions remain available in this repository.

AOL Instant Messenger is proprietary third-party software and is not included
or licensed by this project. OldVersion.com is an unaffiliated optional source.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for details.
