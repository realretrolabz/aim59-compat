# Technical notes

## AIM notification-sound failure under Wine 9.0 and 10.0

AIM 5.9.3861 successfully opens its WAV files, but notification sounds fail
because AIM uses the legacy Windows Media Control Interface (MCI) `waveaudio`
device.

Tracing showed AIM issuing `MCI_OPEN` with a flag set that includes:

```text
MCI_OPEN_SHAREABLE
```

Wine 9.0 and Wine 10.0's `WAVE_mciOpen()` contain:

```c
if (dwFlags & MCI_OPEN_SHAREABLE)
    return MCIERR_UNSUPPORTED_FUNCTION;
```

That causes the MCI open to fail before normal playback.

## Patch

The source patch removes only that rejection.

Wine's next guard remains:

```c
if (wmw->nUseCount > 0) {
    return MCIERR_DEVICE_OPEN;
}
```

The fix therefore allows AIM's first open to carry the shareable flag without
pretending that Wine's wave MCI implementation supports actual simultaneous
sharing.

## Why the PE marker is changed

A Wine-built PE DLL contains the string:

```text
Wine builtin DLL
```

When a copy of such a DLL was placed inside the Wine prefix, Wine recognized
it as its own builtin and still selected the installed implementation.

The project changes the equal-length marker to:

```text
Wine patched DLL
```

and sets:

```text
mciwave = native,builtin
```

This makes Wine load the prefix copy as a native PE DLL while retaining a
builtin fallback.

## Required MCI mappings

Both registry paths are kept on `mciwave.dll`:

```text
HKLM\Software\Microsoft\Windows NT\CurrentVersion\MCI
HKLM\Software\Microsoft\Windows NT\CurrentVersion\MCI32
```

with:

```text
WaveAudio = mciwave.dll
```

Do not redirect WaveAudio to the Windows XP `mciwave.drv`; that is an old
Win16/NE driver and is not the validated fix.

## Failed Windows XP DLL experiment

A native Windows XP `mciwave.dll` was tested during investigation. It allowed
one AIM sound to play and then AIM became unresponsive.

The project does not use or redistribute Microsoft `mciwave` binaries.

## Linux application-menu integration

The patcher writes a standard per-user XDG desktop entry at
`$XDG_DATA_HOME/applications/aim59-compat.desktop` (defaulting to
`~/.local/share/applications/aim59-compat.desktop`). During AIM installation,
the patcher disables only Wine's automatic `winemenubuilder.exe` invocation;
the installer still creates its Windows shortcuts. This prevents Wine and the
desktop environment from creating duplicate or partially converted entries.
When patching an existing prefix, stale Wine-generated AIM entries are removed
only when their contents reference that exact prefix. The project-owned entry
launches the selected Wine executable with the exact prefix and installed
`aim.exe` paths.

For the icon, Wine's `winemenubuilder.exe -t` mode reads the AIM
installer-created shortcut and extracts the largest embedded icon from the
user's installed `aim.exe` as a PNG under
`$XDG_DATA_HOME/aim59-compat/icons/`. The repository does not contain or
download AOL artwork. Setup verifies both the PNG signature and the completed
desktop-entry contents. Rollback removes only entries marked as belonging to
the same prefix.

## AIM 5.9.6089

AIM 5.9.6089 was investigated but is not the v0.1 target. Under Wine it added
extra browser/NSS compatibility problems and a cosmetic buddy-icon-pane
rendering artifact without a demonstrated feature benefit for this project.

The supported reference client remains AIM 5.9.3861.

## Wine 10 validation status

The Wine 10.0 source patch applies cleanly, the PE32 DLL builds from the
official Wine 10.0 archive, and the structural, marker, import, checksum, and
patcher-selection tests pass. End-to-end AIM and repeated-sound validation is
still required before Wine 10 replaces or joins Wine 9 as a known-good runtime.
