# Test matrix

## Release-blocking tests

Run against a fresh prefix created from the documented installer.

- [ ] `rrlzAIMlinux fetch --source oldversion` downloads the pinned installer
- [ ] downloaded installer SHA-256 matches the version manifest
- [ ] `rrlzAIMlinux` completes a fresh guided installation
- [ ] terminal release archive extracts and runs as `./rrlzAIMlinux`
- [ ] terminal release automatically selects its adjacent patched DLL
- [ ] AIM appears in the desktop application menu with its extracted icon
- [ ] application-menu entry launches the configured prefix
- [ ] guided terminal setup defaults to realretrolabz, accepts a Custom host,
  and uses port `5190`; direct custom-port validation rejects invalid ports
- [ ] `rrlzAIMlinux set-server` updates the selected prefix's `Host` and `Port` with
  AIM closed and does not run an installer
- [ ] `rrlzAIMlinux uninstall` requires confirmation, runs AIM's prefix-local
  uninstaller with AIM closed, waits for it to finish, and removes the
  project-owned XDG entry and prefix only after `aim.exe` is absent
- [ ] cancelling or failing that uninstaller leaves the XDG entry and prefix
  intact, including the compatibility `aimapi.dll` disablement when applicable
- [ ] on a clean prefix, the default-off AOL cleanup removes only the exact
  `Free AOL & Unlimited Internet.lnk` from the Wine user/Public Desktop when
  selected; Favorites, Start Menu, and the XDG AIM launcher remain intact
- [ ] terminal release archive contains no AOL/AIM binaries
- [ ] AIM 5.9.3861 installs
- [ ] AIM launches
- [ ] AIM signs into an Open OSCAR server
- [ ] buddy list renders
- [ ] send IM
- [ ] receive IM
- [ ] open IM window locally
- [ ] open IM window from incoming message
- [ ] buddy icon upload/download
- [ ] chat-room join/send/receive
- [ ] profile/away-message basics
- [ ] IM send sound
- [ ] IM receive sound
- [ ] sign-on sound
- [ ] sign-off sound
- [ ] repeated notification sounds (20+ events)
- [ ] AIM remains responsive after repeated sounds
- [ ] sign out / sign back in
- [ ] restart Wine prefix and repeat IM test

## Network-dependent tests

These are useful but not release blockers unless the environment is known to
be correctly configured.

- [ ] Direct Connection
- [ ] file transfer
- [ ] port-forwarded Rendezvous across NAT

## Known-good baseline

Validated target:

```text
AIM:          5.9.3861
Wine:         9.0
Architecture: win32
Windows mode: XP
Runtime:      mfc40
sb.dll:       registered
aimapi.dll:   disabled
mciwave:      patched Wine 9.0 PE32 DLL
Override:     native,builtin
```

Confirmed in the reference setup:

- normal IM send/receive
- buddy list
- buddy icons
- chat
- repeated notification sounds without hanging

## Wine 10 regression matrix

Wine 10 is runtime validated in the maintained setup. For a fresh Wine 10.0
prefix, repeat every release-blocking AIM test above with
`mciwave-wine10-x86-aim.dll` after changes to the Wine DLL or patcher. In
particular, repeat 20 or more alternating send, receive, sign-on, and sign-off
sounds.

## Regression rule

If a change affects the patched Wine DLL, repeat the 20+ sound-event test.
A single successful sound is not sufficient; an earlier failed approach
played once and then hung AIM.

## Native Windows setup

The Windows 11 workflow has been guest-tested. The following optional checks
are useful when you want to retry it from the powered-off `Pre-AIM` snapshot.
Keep installers, installed AIM files, screenshots, raw logs, VM disks, and
private evidence out of the repository.

### Static and build checks

- [x] Linux static tests cover the native C# workflow's installer identity,
  download request flow, server choices, reversible DLL rename, stable-file
  detection, UAC request, and source-only build contract.
- [x] Linux static tests confirm that the active EXE source neither locates
  nor launches `install-aim59.ps1` or `powershell.exe`.
- [ ] On Windows, run
  `.\scripts\windows\build-aim59-setup.ps1` in Windows PowerShell and confirm
  that the only compiled file is `.build\windows-exe\rrlzAIM.exe`.
- [ ] From a temporary folder containing only `rrlzAIM.exe`, confirm that it
  starts normally. It must not require an adjacent PowerShell script.

### Thumb-drive native-EXE workflow

Build the EXE, then create a removable-drive test folder containing only
project-owned files:

```text
<drive>:\AIM59-Test\
  rrlzAIM.exe
  WINDOWS_INSTALL.md (optional instructions)
```

Do not put an AIM installer in the repository or a project release. A local
test installer, if used, must be separately obtained and remain outside the
project; the EXE verifies it before use.

- [ ] Sign in as the intended administrator account, restore `Pre-AIM`, and
  run `rrlzAIM.exe` from the removable drive. Consent to UAC using that same
  account so `%LOCALAPPDATA%` cache and the `HKCU` server setting belong to it.
- [ ] Confirm denied UAC exits clearly without starting a download or
  installer.
- [ ] On separate clean-snapshot runs, test a fresh OldVersion download and a
  browsed local original installer. Confirm visible byte progress for the new
  download and clear download/identity errors when applicable.
- [ ] On separate clean-snapshot runs, test realretrolabz, Keep, and Custom
  host/port choices. Complete AIM's ordinary interactive installer. Confirm
  details report the wait for stable installed `aim.exe` and `aimapi.dll`, even
  when the original installer launcher exits early.
- [ ] On one clean-snapshot install, select the default-off **Remove 'Free AOL
  & Unlimited Internet' desktop shortcut after installation** option. Confirm
  that it removes only that exact shortcut from the current-user and Public
  Desktop when present.
- [ ] After a reported success, confirm the observed
  `aimapi.dll.aim59-disabled` state, then use **Restore aimapi.dll**. Confirm it
  restores only the tool-owned file and leaves the server preference unchanged.
- [ ] With AIM closed, test **Apply server setting** for realretrolabz and a
  Custom host/port. Confirm it changes only the server values and does not
  launch an installer. Saving AIM's own Server settings page should overwrite
  that external value; reapply the EXE setting and record the next-launch
  result.
- [ ] On a separate restored snapshot, test **Uninstall AIM...**. Confirm it
  restores its tool-owned `aimapi.dll` rename before starting only the normal
  registered AIM uninstaller, then complete any destructive choices
  deliberately.
- [ ] Windows 10 has not been tried. It will likely behave similarly, but use
  it at your own discretion.

### Historical PowerShell proof

`scripts/windows/install-aim59.ps1` is retained as archived proof-of-concept
source. It completed one direct Windows guest install and restore, including
the two-second polling/eight-second stable-file completion workaround. It is
not part of the active EXE workflow, does not need to be copied to the thumb
drive.
