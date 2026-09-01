# Installation

## Terminal patcher

Requirements are Python 3.10 or newer, system Wine 9.0 with 32-bit support,
Winetricks, and `cabextract`.

Start the guided setup:

```bash
./aim59 setup
```

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

The YAML downloads its patcher and Wine DLL from the project's versioned
GitHub Release. It uses Lutris file aliases rather than `$SCRIPTDIR`, which is
not available in Lutris 0.5.14.

Lutris delegates to `aim59 setup --source oldversion`. The patcher downloads
the pinned installer from the unaffiliated OldVersion archive, verifies its
SHA-256, creates the prefix, installs AIM, and applies the compatibility
changes.

The current installer is intentionally strict: it expects **system Wine 9.0**
because the included `mciwave.dll` was built and validated against Wine 9.0.

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
the `mciwave` override, restores `aimapi.dll` when possible, and records the
rollback time in the prefix state.
