# Installation

## Terminal release archive

The primary terminal distribution contains the patcher and its versioned
patched Wine DLLs together. The v0.1.2 archive contains the runtime-validated
Wine 9 DLL and the build-validated Wine 10 candidate.

```bash
tar -xzf aim59-compat-0.1.2-linux.tar.gz
cd aim59-compat-0.1.2
./aim59 setup
```

The matching adjacent DLL is selected automatically. The patcher then offers the
verified OldVersion source, a local installer, or a user-provided direct URL.

## Repository checkout

Requirements are Python 3.10 or newer, system Wine 9.0 or 10.0 with 32-bit
support, Winetricks, and `cabextract`.

On Debian, enable the i386 architecture and install Wine's 32-bit runtime if
`wine --version` reports that `wine32` is missing:

```bash
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install wine32:i386
```

Start the guided setup:

```bash
./aim59 setup
```

Successful setup installs an `AIM.desktop` entry under the user's XDG
applications directory, replacing Wine's entry for the same AIM Start Menu
shortcut if one already exists. AIM therefore appears once in GNOME, KDE
Plasma, and other freedesktop-compatible application menus. Its PNG icon is
extracted from the user's installed AIM shortcut and executable into the
external project data directory; no AOL icon is distributed by this repository.

The default choice downloads AIM 5.9.3861 from the configured unaffiliated
OldVersion.com source. The patcher resolves the archive's current download
form, writes the installer to `~/.cache/aim59-compat/installers/`, and verifies
its pinned SHA-256 before executing it.

Use a local installer or another direct URL instead:

```bash
./aim59 setup --installer /path/to/aim593861.exe
./aim59 setup --installer-url https://example.invalid/aim593861.exe
```

Choose another prefix with `--prefix`. Run `./aim59 setup --help` for all
noninteractive and command-path options.

## Lutris

Open the Lutris installer from a repository checkout:

```bash
lutris -i lutris/aim-5.9.3861.yml
```

The YAML downloads the complete Linux bundle from the project's versioned
GitHub Release and extracts it into Lutris's temporary cache. The patcher and
both versioned DLLs therefore remain adjacent without relying on `$SCRIPTDIR`,
which is not available in Lutris 0.5.14.

Lutris delegates to `aim59 setup --source oldversion`. The patcher downloads
the pinned installer from the unaffiliated OldVersion archive, verifies its
SHA-256, creates the prefix, installs AIM, and applies the compatibility
changes.

The patcher detects system Wine 9.0 or 10.0 and selects the matching bundled
DLL. Wine 9.0 is runtime validated. Wine 10.0 remains a test candidate until
the repeated-notification-sound runtime matrix is complete.

## Manual known-good recipe

Create a dedicated 32-bit prefix:

```bash
WINEARCH=win32 WINEPREFIX="$HOME/.wine-aim59" wineboot -u
```

Install the required legacy runtime and XP mode:

```bash
WINEPREFIX="$HOME/.wine-aim59" winetricks -q winxp mfc40
```

Run your AIM installer:

```bash
WINEPREFIX="$HOME/.wine-aim59" wine /path/to/aim593861.exe
```

Register SuperBuddy:

```bash
WINEPREFIX="$HOME/.wine-aim59" \
wine regsvr32 "C:\Program Files\AIM\sb.dll"
```

Stop Wine:

```bash
WINEPREFIX="$HOME/.wine-aim59" wineserver -k
```

Disable `aimapi.dll`:

```bash
mv "$HOME/.wine-aim59/drive_c/Program Files/AIM/aimapi.dll" \
   "$HOME/.wine-aim59/drive_c/Program Files/AIM/aimapi.dll.disabled"
```

Then apply the project fixes through the canonical engine:

```bash
./aim59 patch-prefix --prefix "$HOME/.wine-aim59"
```

Launch:

```bash
WINEPREFIX="$HOME/.wine-aim59" \
wine "C:\Program Files\AIM\aim.exe"
```

## Roll back project changes

```bash
./aim59 rollback --prefix "$HOME/.wine-aim59"
```

Rollback restores the backed-up Wine `mciwave.dll` and `system.ini`, removes
the `mciwave` override, restores `aimapi.dll` when possible, removes the
project-owned application entry and extracted icon, and records the rollback
time in the prefix state.
