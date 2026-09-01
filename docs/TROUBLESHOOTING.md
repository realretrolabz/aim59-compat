# Troubleshooting

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
