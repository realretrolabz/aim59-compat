# Lutris installers

## Installer

There is one user-facing installer definition:

```bash
lutris -i lutris/aim-5.9.3861.yml
```

It downloads `aim59-patcher.pyz` and the patched Wine DLL from the project's
versioned GitHub Release. Installer commands refer to Lutris's
`$aim59_patcher` and `$mciwave_patch` file aliases, which work on Lutris
0.5.14 and newer.

Lutris calls the checkout's canonical `aim59 setup --source oldversion`
engine. It downloads the pinned AIM installer from the unaffiliated
OldVersion archive into Lutris's temporary cache, verifies it, creates the
prefix, installs AIM, and applies the compatibility fixes. The project-owned
GitHub assets do not contain AIM; the patcher retrieves it directly from the
unaffiliated OldVersion archive and verifies the pinned SHA-256.

## Current Lutris assumptions

The installer intentionally uses:

- system Wine
- Wine 9.0 check
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

The loose `.pyz` and DLL are Lutris implementation assets. Terminal users get
the first-class `aim59-compat-0.1.1-linux.tar.gz` distribution instead.

Keep this release-pinned YAML on Wine 9.0 until a release contains both
versioned DLLs and the Wine 10 repeated-sound runtime matrix is complete.
