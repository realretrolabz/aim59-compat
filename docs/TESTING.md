# Test matrix

## Release-blocking tests

Run against a fresh prefix created from the documented installer.

- [ ] `aim59 fetch --source oldversion` downloads the pinned installer
- [ ] downloaded installer SHA-256 matches the version manifest
- [ ] `aim59 setup` completes from a fresh terminal-created prefix
- [ ] Lutris downloads both project assets from the versioned GitHub Release
- [ ] Lutris delegates successfully to `setup --source oldversion`

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

## Regression rule

If a change affects the patched Wine DLL, repeat the 20+ sound-event test.
A single successful sound is not sufficient; an earlier failed approach
played once and then hung AIM.
