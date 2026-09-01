# References

## Lutris

Current installer documentation:

https://github.com/lutris/lutris/blob/master/docs/installers.rst

Relevant current features used by this project include:

- local installer root metadata and `script:` wrapper
- `$CACHE` for downloaded installer assets
- installer-file aliases such as `$aim59_patcher`
- `execute` commands
- DLL overrides such as `n,b`

## AIM installer archive

The optional `oldversion` source resolver uses this unaffiliated third-party
version page:

https://www.oldversion.com/software/aol-instant-messenger/aol-instant-messenger-5-9-3861/

The page URL is metadata only. The repository does not mirror its installer,
and the patcher verifies downloaded bytes against the version manifest.

## Wine

Wine source mirror, Wine 9.0 `mciwave.c`:

https://github.com/wine-mirror/wine/blob/wine-9.0/dlls/mciwave/mciwave.c

Wine project:

https://gitlab.winehq.org/wine/wine

Wine source archives:

https://dl.winehq.org/wine/source/9.0/

## Open OSCAR

Open OSCAR:

https://github.com/mk6i/open-oscar-server

Rendezvous / direct-connect documentation:

https://github.com/mk6i/open-oscar-server/blob/main/docs/RENDEZVOUS.md
