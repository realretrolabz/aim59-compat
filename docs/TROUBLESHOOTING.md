# Troubleshooting

## Setup says AIM is already installed

The manager intentionally refuses to adopt a selected directory that already
contains a `prefix` child. It never scans for or takes ownership of an older
Wine installation. Direct setup also refuses to run over a prefix that already
contains `aim.exe`, preventing a later Winetricks or installer step from
stalling or overwriting the existing copy.

Use one of these commands instead. Omitting `--prefix` uses the managed default
prefix, `~/.local/share/rrlzAIM/prefix`:

```bash
./rrlzAIMlinux launch
./rrlzAIMlinux patch-prefix
./rrlzAIMlinux uninstall
```

If this was a deliberately custom prefix, add its exact path, for example
`--prefix "$HOME/.wine-aim59"`.

`uninstall` runs AIM's uninstaller and permanently deletes that prefix only
after the uninstaller succeeds and removes `aim.exe`.

## AIM never appears / hangs in the background

Confirm `aimapi.dll` is disabled:

```bash
find "$WINEPREFIX/drive_c/Program Files/AIM" \
  -maxdepth 1 -iname 'aimapi.dll*' -print
```

Expected:

```text
aimapi.dll.disabled
```

## SuperBuddy COM error

If Wine reports that the SuperBuddy class is not registered:

```bash
WINEPREFIX="$WINEPREFIX" \
wine regsvr32 "C:\Program Files\AIM\sb.dll"
```

## Missing MFC40.DLL

Install:

```bash
WINEPREFIX="$WINEPREFIX" winetricks -q mfc40
```

## AIM works but notification sounds are silent

Verify the patched DLL:

```bash
scripts/verify-mciwave.sh \
  "$WINEPREFIX/drive_c/windows/system32/mciwave.dll"
```

Check the override:

```bash
WINEPREFIX="$WINEPREFIX" \
wine reg query 'HKCU\Software\Wine\DllOverrides' /v mciwave
```

Expected:

```text
native,builtin
```

Check MCI mappings:

```bash
WINEPREFIX="$WINEPREFIX" \
wine reg query 'HKLM\Software\Microsoft\Windows NT\CurrentVersion\MCI' /v WaveAudio

WINEPREFIX="$WINEPREFIX" \
wine reg query 'HKLM\Software\Microsoft\Windows NT\CurrentVersion\MCI32' /v WaveAudio
```

Both should point to `mciwave.dll`.

## Direct Connection / file transfer

AIM Rendezvous/direct-connect features are peer-to-peer and can fail because
of NAT/firewall configuration even when the AIM client itself is working.

Consult Open OSCAR's Rendezvous documentation:

https://github.com/mk6i/open-oscar-server/blob/main/docs/RENDEZVOUS.md

Do not treat an unconfigured inbound port as proof that this Wine patch is
broken.

## Gather an MCI trace

```bash
WINEDEBUG=+loaddll,+mci,+mciwave \
WINEPREFIX="$WINEPREFIX" \
wine "$WINEPREFIX/drive_c/Program Files/AIM/aim.exe" \
2>aim-mciwave.log
```
