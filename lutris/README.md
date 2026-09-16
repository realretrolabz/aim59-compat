# Lutris installers

## Installer

There is one user-facing installer definition:

```bash
lutris -i lutris/aim-5.9.3861.yml
```

It downloads the complete Linux bundle from the project's versioned GitHub
Release using the `$aim59_bundle` file alias, extracts the patcher and both
versioned DLLs into Lutris's temporary cache, and runs the adjacent patcher.
This works on Lutris 0.5.14 and newer without relying on `$SCRIPTDIR`.

The installer uses Lutris's native Linux runner as a frontend for the user's
system Wine. Lutris.net only accepts Wine builds present in its managed runner
catalog, which does not provide the version-matched upstream Wine 9.0 or 10.0
targets. The Linux runner invokes `/usr/bin/env` with the patched prefix and
system `wine`, ensuring installation and launch use the same Wine family.

Lutris calls the checkout's canonical `aim59 setup --source oldversion`
engine. It downloads the pinned AIM installer from the unaffiliated
OldVersion archive into Lutris's temporary cache, verifies it, creates the
prefix, installs AIM, and applies the compatibility fixes. The project-owned
GitHub assets do not contain AIM; the patcher retrieves it directly from the
unaffiliated OldVersion archive and verifies the pinned SHA-256.

## Current Lutris assumptions

The installer intentionally uses:

- system Wine
- native Lutris Linux runner with the Lutris runtime disabled
- Wine 9.0 or Wine 10.0 check with version-matched DLL selection
- win32 prefix
- Winetricks `winxp mfc40`
- `regsvr32` for `sb.dll`
- disabled `aimapi.dll`
- native/builtin `mciwave` override
- MCI and MCI32 WaveAudio mappings
- XDG application-menu entry with an icon extracted from the installed AIM copy

The YAML must not duplicate acquisition, prefix creation, installation, or
the AIM-specific file and registry operations. Those belong to `aim59 setup`
so terminal and Lutris installs remain identical.

The complete `aim59-compat-0.1.2-linux.tar.gz` archive is used by both Lutris
and terminal users. Loose `.pyz` and DLL release assets remain available for
manual integration.

Wine 9.0 remains runtime validated. Keep Wine 10.0 labeled as a test candidate
until its repeated-sound runtime matrix is complete.
