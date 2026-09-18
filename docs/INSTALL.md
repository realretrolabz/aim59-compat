# Installation

## Terminal release archive

The primary terminal distribution contains the manager and its versioned
patched Wine DLLs together.

```bash
./rrlzAIMlinux
```

The matching adjacent DLL is selected automatically. The manager then offers
the verified OldVersion source, a local installer, or a user-provided direct
URL.

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
./rrlzAIMlinux
```

The no-subcommand manager presents the rrlzAIM terminal menu. It records only
its own successful guided installations and does not scan or import existing
Wine prefixes. Its **Install AIM** flow chooses an AIM data directory, server,
AOL-shortcut cleanup, XDG launcher, and installer source.

When selected during guided setup, a successful installation writes a dedicated
per-prefix XDG launcher. Its PNG icon is extracted from the user's installed AIM
shortcut and executable; no AOL icon is distributed by this repository.

The default choice downloads AIM 5.9.3861 from the configured unaffiliated
OldVersion.com source. The patcher resolves the archive's current download
form, writes the installer to `~/.cache/rrlzAIM/installers/`, and verifies
its pinned SHA-256 before executing it.

Use a local installer or another direct URL instead:

```bash
./rrlzAIMlinux setup --installer /path/to/aim593861.exe
./rrlzAIMlinux setup --installer-url https://example.invalid/aim593861.exe
```

For direct commands, `--aim-prefix DIRECTORY` resolves the Wine prefix as
`DIRECTORY/prefix`; `--prefix` remains an advanced exact-prefix override. Run
`./rrlzAIMlinux setup --help` for all noninteractive and command-path options.

The terminal manager defaults to `aim.realretrolabz.com:5190`. Direct
unattended setup is deliberately conservative: it keeps AIM's existing server
preference and leaves the AOL shortcut in place unless options explicitly
request changes:

```bash
./rrlzAIMlinux setup \
  --source oldversion \
  --server realretrolabz \
  --remove-aol-desktop-shortcut \
  --yes
```

Use `--server custom --server-host HOST [--server-port PORT]` for another
server. The custom port defaults to `5190` and must be in the range 1–65535.

With AIM closed, reapply a setting after installation without rerunning the
installer:

```bash
./rrlzAIMlinux set-server --server realretrolabz
```

Saving AIM's own Server settings dialog can overwrite the external setting;
rerun `set-server` after such a save when needed.

## Uninstall AIM and delete its Wine prefix

Close AIM, then run. Without `--prefix`, this targets the managed default
prefix, `~/.local/share/rrlzAIM/prefix`:

```bash
./rrlzAIMlinux uninstall
```

After explicit confirmation, this restores the patcher-owned `aimapi.dll`
rename for AIM's prefix-local `uninstll.exe`, waits for its Wine processes, then
removes the project-owned XDG launcher and permanently deletes the complete
prefix. It keeps the prefix and launcher if the uninstaller fails, is
cancelled, or leaves `aim.exe` behind. Preview the plan with `--dry-run`; an
automated invocation requires `--non-interactive --yes`.
Deleting the prefix also discards its prefix-local rollback state, including
any saved AOL shortcut copy.

Use `--aim-prefix "$HOME/.local/share/my-aim"` for a custom parent directory;
the Wine prefix is always its `prefix` child.

If `aim.exe` is already in the selected prefix, `setup` stops before acquiring
another installer. Use `launch`, `patch-prefix`, or `uninstall` rather than
attempting an installation over the existing AIM copy.

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
./rrlzAIMlinux patch-prefix --prefix "$HOME/.wine-aim59"
```

Launch:

```bash
WINEPREFIX="$HOME/.wine-aim59" \
wine "C:\Program Files\AIM\aim.exe"
```

## Roll back project changes

```bash
./rrlzAIMlinux rollback --prefix "$HOME/.wine-aim59"
```

Rollback restores the backed-up Wine `mciwave.dll` and `system.ini`, removes
the `mciwave` override, restores `aimapi.dll` when possible, removes the
project-owned application entry and extracted icon, and records the rollback
time in the prefix state. If guided setup removed the optional AOL desktop
shortcut, rollback restores its prefix-backed copy only when the target remains
absent; an AIM server preference is intentionally left unchanged.
